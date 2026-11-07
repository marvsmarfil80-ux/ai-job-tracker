#!/usr/bin/env bash
set -euo pipefail

TARGET_DB="${TARGET_DB:-jobtracker_smoke}"
if [[ "$TARGET_DB" != "jobtracker_smoke" ]]; then
  echo "FAIL target guard: this script only runs against jobtracker_smoke"
  exit 1
fi

SMOKE_DB="jobtracker_smoke"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/backend/.venv/bin/python"
BASE="http://127.0.0.1:8001"
KEY="smoke-test-key"
BODY="$(mktemp)"
STARTED=0
CODE=000

db() {
  sudo docker exec -i jobtracker-postgres psql -U jobtracker -d "$SMOKE_DB" -v ON_ERROR_STOP=1 -q -At -c "$1" || { echo "FAIL database query failed" >&2; exit 1; }
}

admin() {
  sudo docker exec -i jobtracker-postgres psql -U jobtracker -d postgres -v ON_ERROR_STOP=1 -q -At -c "$1"
}

pass() { echo "PASS $1"; }
fail() { echo "FAIL $1"; exit 1; }
failb() { echo "FAIL $1 (HTTP $CODE)"; head -c 300 "$BODY"; echo; exit 1; }

api() {
  local method="$1" path="$2" data="${3:-}"
  if [[ -n "$data" ]]; then
    CODE="$(curl -s --max-time 180 -o "$BODY" -w '%{http_code}' -X "$method" -H "X-API-Key: $KEY" -H 'Content-Type: application/json' -d "$data" "$BASE$path")" || CODE=000
  else
    CODE="$(curl -s --max-time 180 -o "$BODY" -w '%{http_code}' -X "$method" -H "X-API-Key: $KEY" "$BASE$path")" || CODE=000
  fi
}

jget() {
  "$PY" -c 'import json,sys; d=json.load(open(sys.argv[1])); print(eval(sys.argv[2]))' "$BODY" "$1" 2>/dev/null || echo "unreadable"
}

cleanup() {
  local rc=$?
  rm -f "$BODY"
  if [[ "$STARTED" == 1 ]]; then
    admin "drop database if exists jobtracker_smoke with (force)" >/dev/null 2>&1 || true
    if [[ "$(admin "select count(*) from pg_database where datname = 'jobtracker_smoke'" 2>/dev/null)" == 0 ]]; then
      echo "PASS cleanup: jobtracker_smoke dropped"
    else
      echo "FAIL cleanup: jobtracker_smoke still exists"
      rc=1
    fi
  fi
  exit "$rc"
}
trap cleanup EXIT

sudo -v
sudo docker ps --format '{{.Names}}' | grep -qx jobtracker-postgres || fail "preflight: jobtracker-postgres is not running (sudo docker start jobtracker-postgres)"
pass "preflight postgres running"

admin "drop database if exists jobtracker_smoke with (force)" >/dev/null
admin "create database jobtracker_smoke" >/dev/null
STARTED=1
pass "scratch database created"

(cd "$ROOT/backend" && POSTGRES_DB="$SMOKE_DB" .venv/bin/alembic upgrade head >/dev/null 2>&1) || fail "migrate: alembic upgrade failed (output hidden)"
[[ "$(db "select version_num from alembic_version")" == "0005" ]] || fail "migrate: alembic_version is not 0005"
pass "migrate head 0005"

sudo docker exec -i jobtracker-postgres psql -U jobtracker -d "$SMOKE_DB" -v ON_ERROR_STOP=1 -q < "$ROOT/scripts/seed.sql" >/dev/null 2>&1 || fail "seed: seed.sql failed (output hidden)"
db "update sources set enabled = false where name = 'remotive'"
[[ "$(db "select count(*) from sources where enabled")" == 2 ]] || fail "seed: expected 2 enabled sources"
pass "seed applied, remotive disabled"

ready=0
for _ in $(seq 1 60); do
  c="$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "$BASE/health" || true)"
  if [[ "$c" == 200 ]]; then
    ready=1
    break
  fi
  sleep 2
done
[[ "$ready" == 1 ]] || fail "api: nothing healthy on port 8001 (start it with: bash scripts/smoke_api.sh)"
pass "api reachable"

api GET "/jobs?limit=1"
[[ "$CODE" == 200 ]] || failb "guard: api rejected the smoke key or failed"
[[ "$(jget 'd["total"]')" == 0 ]] || fail "guard: api is not connected to the empty scratch database"
pass "guard api uses jobtracker_smoke"

api GET "/health"
[[ "$CODE" == 200 ]] || failb "a health"
api GET "/system/status"
[[ "$CODE" == 200 ]] || failb "a system status"
[[ "$(jget 'd["database"]["status"]')" == "ok" ]] || fail "a system status: database is not ok"
pass "a health and system status"

CODE="$(curl -s -o /dev/null -w '%{http_code}' "$BASE/jobs?limit=1")" || CODE=000
[[ "$CODE" == 401 ]] || fail "b missing key returned HTTP $CODE instead of 401"
pass "b missing key returns 401"

api PUT "/profile" '{"content": "TEST profile for the smoke test only. Backend developer interested in remote Python work."}'
[[ "$CODE" == 2* ]] || failb "c profile"
[[ "$(db "select count(*) from profile where content like 'TEST profile%'")" == 1 ]] || fail "c profile row not found"
pass "c fake profile saved"

api POST "/hunts" '{"sources": ["weworkremotely", "remoteok"]}'
[[ "$CODE" == 2* ]] || failb "d hunt"
if [[ "$(jget 'd["status"] != "error" and any(s["status"] == "done" for s in d["steps"])')" != "True" ]]; then
  fail "d hunt: no feed finished (check internet) steps=$(jget '[(s["source"], s["status"], s["message"]) for s in d["steps"]]')"
fi
[[ "$(db "select count(*) from notifications where type = 'hunt_done'")" -ge 1 ]] || fail "d hunt: no hunt_done notification"
pass "d hunt steps=$(jget '[(s["source"], s["status"], s["found"], s["new"]) for s in d["steps"]]')"

before="$(db "select count(*) from job_scores")"
api POST "/score/run?limit=3"
[[ "$CODE" == 200 ]] || failb "e score run"
after="$(db "select count(*) from job_scores")"
if (( after <= before )); then
  fail "e score: no job_scores added; jobs by pipeline status: $(db "select coalesce(string_agg(pipeline_status || '=' || n, ' '), 'no jobs') from (select pipeline_status, count(*) as n from jobs group by pipeline_status) t")"
fi
pass "e score added $((after - before)) scores"

JOB_JSON='{"source": "manual", "title": "TEST Backend Engineer", "company": "TEST Company", "url": "https://example.com/test-smoke-job"}'
api POST "/jobs" "$JOB_JSON"
[[ "$CODE" == 201 ]] || failb "f create job"
JOB_ID="$(jget 'd["id"]')"
api POST "/jobs" "$JOB_JSON"
[[ "$CODE" == 409 ]] || failb "f duplicate job"
[[ "$(jget 'd["existing_id"]')" == "$JOB_ID" ]] || fail "f duplicate existing_id mismatch"
pass "f job created then duplicate rejected"

api POST "/jobs/$JOB_ID/open"
[[ "$CODE" == 2* ]] || failb "g open"
api GET "/jobs?awaiting_apply=true"
[[ "$(jget "any(i['id'] == $JOB_ID for i in d['items'])")" == "True" ]] || fail "g job missing from awaiting_apply"
pass "g open marks job as awaiting apply"

api POST "/applications" "{\"job_id\": $JOB_ID}"
[[ "$CODE" == 2* ]] || failb "h create application"
APP_ID="$(jget 'd["id"]')"
[[ "$(jget 'd["status"]')" == "applied" ]] || fail "h status is not applied"
[[ "$(db "select count(*) from application_events where application_id = $APP_ID")" == 1 ]] || fail "h expected 1 event"
api GET "/jobs?awaiting_apply=true"
[[ "$(jget "any(i['id'] == $JOB_ID for i in d['items'])")" == "False" ]] || fail "h job still awaiting apply"
pass "h application created with 1 event"

api PATCH "/applications/$APP_ID" '{"status": "interview"}'
[[ "$CODE" == 200 ]] || failb "i to interview"
[[ "$(db "select count(*) from application_events where application_id = $APP_ID")" == 2 ]] || fail "i expected 2 events"
api PATCH "/applications/$APP_ID" '{"status": "under_review"}'
[[ "$CODE" == 200 ]] || failb "i to under_review"
api GET "/applications/$APP_ID"
[[ "$(jget 'len(d["events"])')" == 3 ]] || fail "i expected 3 events in detail"
pass "i status changes logged as events"

YESTERDAY="$(TZ=Asia/Manila date -d yesterday +%F)"
api POST "/follow-ups" "{\"application_id\": $APP_ID, \"title\": \"TEST follow up\", \"due_date\": \"$YESTERDAY\"}"
[[ "$CODE" == 2* ]] || failb "j create follow-up"
FOLLOW_ID="$(jget 'd["id"]')"
api GET "/follow-ups"
[[ "$(jget "any(i['id'] == $FOLLOW_ID and i['is_overdue'] for i in d['items'])")" == "True" ]] || fail "j follow-up not listed as overdue"
pass "j overdue follow-up listed"

api POST "/allowed-senders" '{"sender": "test-sender@example.com", "kind": "application"}'
[[ "$CODE" == 2* ]] || failb "k allowed sender"
api PATCH "/settings" '{"email_auto_status_enabled": true}'
[[ "$CODE" == 200 ]] || failb "k enable auto status"
EMAIL_ID="$(db "insert into emails (gmail_message_id, kind, sender, subject, snippet, received_at, status) values ('test-smoke-message-1', 'application', 'TEST Sender <test-sender@example.com>', 'TEST Interview invitation from TEST Company', 'TEST snippet: please schedule an interview with TEST Company.', now(), 'unprocessed') returning id")"
api POST "/emails/process"
[[ "$CODE" == 2* ]] || failb "k process emails"
RESULT="$(db "select status || '|' || coalesce(class, '') || '|' || coalesce(application_id::text, '') from emails where id = $EMAIL_ID")"
[[ "$RESULT" == "processed|interview|$APP_ID" ]] || fail "k unexpected result: $RESULT"
pass "k email processed as interview and linked"

EVENTS="$(db "select count(*) from application_events where application_id = $APP_ID and source = 'email'")"
NOTES="$(db "select count(*) from notifications where type = 'status_changed'")"
if (( EVENTS < 1 || NOTES < 1 )); then
  fail "l no auto status; review notes: $(db "select coalesce(string_agg(message, ' / '), 'none') from notifications where type = 'email_needs_review'")"
fi
pass "l auto status event and status_changed notification"
EVENT_ID="$(db "select id from application_events where application_id = $APP_ID and source = 'email' order by id desc limit 1")"
api POST "/application-events/$EVENT_ID/undo"
[[ "$CODE" == 2* ]] || failb "l undo"
[[ "$(db "select status from applications where id = $APP_ID")" == "under_review" ]] || fail "l status not restored by undo"
pass "l undo restored under_review"

api GET "/notifications"
[[ "$CODE" == 200 ]] || failb "m list notifications"
[[ "$(jget "{'hunt_done', 'status_changed'} <= {i['type'] for i in d['items']}")" == "True" ]] || fail "m expected notification types missing"
NOTE_ID="$(jget 'd["items"][0]["id"]')"
api PATCH "/notifications/$NOTE_ID" '{"is_read": true}'
[[ "$CODE" == 200 ]] || failb "m mark read"
[[ "$(jget 'd["is_read"]')" == "True" ]] || fail "m notification not marked read"
pass "m notifications listed and one marked read"

api POST "/emails/sync"
[[ "$CODE" == 502 ]] || failb "n sync with fake webhook"
[[ "$(jget 'd["detail"]')" == "Could not reach the n8n webhook." ]] || fail "n unexpected detail"
[[ "$(db "select count(*) from notifications where type = 'email_sync_failed'")" == 1 ]] || fail "n expected exactly 1 email_sync_failed notification"
[[ "$(db "select message from notifications where type = 'email_sync_failed'")" == "Email check failed: Could not reach the n8n webhook." ]] || fail "n unexpected email_sync_failed message"
pass "n sync returns 502 and creates an email_sync_failed notification"

api GET "/settings"
[[ "$CODE" == 200 ]] || failb "o read settings"
OLD="$(jget 'd["settings"]["score_batch_limit"]["value"]')"
NEW=$(( OLD < 20 ? OLD + 1 : OLD - 1 ))
api PATCH "/settings" "{\"score_batch_limit\": $NEW}"
[[ "$CODE" == 200 ]] || failb "o change setting"
[[ "$(jget 'd["settings"]["score_batch_limit"]["value"]')" == "$NEW" ]] || fail "o setting not changed"
api PATCH "/settings" "{\"score_batch_limit\": $OLD}"
[[ "$CODE" == 200 ]] || failb "o restore setting"
[[ "$(jget 'd["settings"]["score_batch_limit"]["value"]')" == "$OLD" ]] || fail "o setting not restored"
pass "o settings read, changed and restored"

JOB_P_JSON='{"source": "manual", "title": "TEST Dismiss Job", "company": "TEST Company", "url": "https://example.com/test-smoke-dismiss"}'
api POST "/jobs" "$JOB_P_JSON"
[[ "$CODE" == 201 ]] || failb "p create job"
JOB_P="$(jget 'd["id"]')"
api POST "/jobs/$JOB_P/open"
[[ "$CODE" == 2* ]] || failb "p open"
api GET "/jobs?awaiting_apply=true"
[[ "$(jget "any(i['id'] == $JOB_P for i in d['items'])")" == "True" ]] || fail "p job missing from awaiting_apply before dismiss"
api POST "/jobs/$JOB_P/dismiss"
[[ "$CODE" == 200 ]] || failb "p dismiss"
[[ "$(jget 'd["dismissed_at"] is not None')" == "True" ]] || fail "p dismissed_at was not set"
api GET "/jobs?awaiting_apply=true"
[[ "$(jget "any(i['id'] == $JOB_P for i in d['items'])")" == "False" ]] || fail "p dismissed job still awaiting apply"
api GET "/jobs?dismissed=true"
[[ "$(jget "any(i['id'] == $JOB_P for i in d['items'])")" == "True" ]] || fail "p dismissed job missing from dismissed=true"
api POST "/jobs/$JOB_P/restore"
[[ "$CODE" == 200 ]] || failb "p restore"
[[ "$(jget 'd["dismissed_at"] is None')" == "True" ]] || fail "p dismissed_at was not cleared"
api GET "/jobs?awaiting_apply=true"
[[ "$(jget "any(i['id'] == $JOB_P for i in d['items'])")" == "True" ]] || fail "p restored job missing from awaiting_apply"
pass "p dismiss hides the job from awaiting apply and restore brings it back"

api DELETE "/applications/$APP_ID"
[[ "$CODE" == 409 ]] || failb "q delete with history"
[[ "$(jget 'd["detail"]')" == "This application has history. Set its status to withdrawn instead." ]] || fail "q unexpected history detail"
[[ "$(db "select count(*) from applications where id = $APP_ID")" == 1 ]] || fail "q application with history was removed"

JOB_Q_JSON='{"source": "manual", "title": "TEST Delete Job", "company": "TEST Company", "url": "https://example.com/test-smoke-delete"}'
api POST "/jobs" "$JOB_Q_JSON"
[[ "$CODE" == 201 ]] || failb "q create job"
JOB_Q="$(jget 'd["id"]')"
api POST "/jobs/$JOB_Q/open"
[[ "$CODE" == 2* ]] || failb "q open"
api POST "/applications" "{\"job_id\": $JOB_Q}"
[[ "$CODE" == 201 ]] || failb "q create application"
APP_Q="$(jget 'd["id"]')"
api POST "/follow-ups" "{\"application_id\": $APP_Q, \"title\": \"TEST q follow up\"}"
[[ "$CODE" == 2* ]] || failb "q create follow-up"
api GET "/jobs?awaiting_apply=true"
[[ "$(jget "any(i['id'] == $JOB_Q for i in d['items'])")" == "False" ]] || fail "q job still awaiting apply before delete"
api DELETE "/applications/$APP_Q"
[[ "$CODE" == 204 ]] || failb "q delete application"
[[ "$(db "select count(*) from applications where id = $APP_Q")" == 0 ]] || fail "q application was not deleted"
[[ "$(db "select count(*) from application_events where application_id = $APP_Q")" == 0 ]] || fail "q event was not deleted"
[[ "$(db "select count(*) from follow_ups where application_id = $APP_Q")" == 0 ]] || fail "q follow-up was not deleted"
api GET "/jobs?awaiting_apply=true"
[[ "$(jget "any(i['id'] == $JOB_Q for i in d['items'])")" == "True" ]] || fail "q job did not return to awaiting_apply"
pass "q application with history is refused, a fresh one is deleted and its job returns to awaiting apply"

echo "ALL PASS a-q"
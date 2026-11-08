#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RESTORE_DB="jobtracker_restore_check"
TABLES="jobs job_scores search_runs search_run_steps sources notifications settings profile applications application_events follow_ups allowed_senders emails system_events"
STARTED=0

run_sql() {
  sudo docker exec -i jobtracker-postgres psql -U jobtracker -d "$1" -v ON_ERROR_STOP=1 -q -At -c "$2"
}

pass() { echo "PASS $1"; }
fail() { echo "FAIL $1"; exit 1; }

cleanup() {
  local rc=$?
  if [[ "$STARTED" == 1 ]]; then
    run_sql postgres "drop database if exists jobtracker_restore_check with (force)" >/dev/null 2>&1 || true
    if [[ "$(run_sql postgres "select count(*) from pg_database where datname = 'jobtracker_restore_check'" 2>/dev/null)" == 0 ]]; then
      echo "PASS cleanup: jobtracker_restore_check dropped"
    else
      echo "FAIL cleanup: jobtracker_restore_check still exists"
      rc=1
    fi
  fi
  exit "$rc"
}
trap cleanup EXIT

sudo -v
sudo docker ps --format '{{.Names}}' | grep -qx jobtracker-postgres || fail "preflight: jobtracker-postgres is not running (sudo docker start jobtracker-postgres)"
pass "preflight postgres running"

mkdir -p "$ROOT/backups"
git -C "$ROOT" check-ignore -q backups/check.sql || fail "backups/ is not gitignored"
pass "backups/ is gitignored"

FILE="$ROOT/backups/jobtracker-$(date +%Y%m%d-%H%M%S).sql"
if ! ( umask 077; sudo docker exec jobtracker-postgres pg_dump -U jobtracker -d jobtracker > "$FILE" ); then
  rm -f "$FILE"
  fail "dump: pg_dump failed"
fi
chmod 600 "$FILE"
[[ -s "$FILE" ]] || fail "dump: file is empty"
pass "dump created $(basename "$FILE") size $(du -h "$FILE" | cut -f1) mode $(stat -c %a "$FILE")"

run_sql postgres "drop database if exists jobtracker_restore_check with (force)" >/dev/null
run_sql postgres "create database jobtracker_restore_check" >/dev/null
STARTED=1
pass "scratch database created"

sudo docker exec -i jobtracker-postgres psql -U jobtracker -d "$RESTORE_DB" -v ON_ERROR_STOP=1 -q < "$FILE" >/dev/null 2>&1 || fail  "restore: psql restore failed (output hidden)"
pass "restore finished"

mismatch=0
for table in $TABLES; do
  real="$(run_sql jobtracker "select count(*) from $table")"
  restored="$(run_sql "$RESTORE_DB" "select count(*) from $table")"
  if [[ "$real" == "$restored" ]]; then
    printf '  %-22s real=%s restored=%s OK\n' "$table" "$real" "$restored"
  else
    printf '  %-22s real=%s restored=%s MISMATCH\n' "$table" "$real" "$restored"
    mismatch=1
  fi
done
[[ "$mismatch" == 0 ]] || fail "counts: at least one table differs (rerun if the app wrote data during the dump)"
pass "row counts match for 14 tables"

real_version="$(run_sql jobtracker "select version_num from alembic_version")"
restored_version="$(run_sql "$RESTORE_DB" "select version_num from alembic_version")"
[[ -n "$real_version" ]] || fail "alembic_version: real database returned no version"
[[ "$real_version" == "$restored_version" ]] || fail "alembic_version differs (real=$real_version restored=$restored_version)"
pass "alembic_version is $real_version in both"

echo "ALL PASS backup check"
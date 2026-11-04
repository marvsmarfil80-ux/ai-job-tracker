# AI Job Tracker

A personal web app that automatically searches for remote jobs, tracks job applications, and monitors job-related Gmail messages.

> **Status:** Early development. Repository setup phase.

## Design Principles

- **No auto-submit.** The app never submits a job application on your behalf.
- **Gmail is read-only.** The app only reads job-related messages and never sends, modifies, or deletes email.
- **No secrets in the repository.** Credentials live in local `.env` files that are git-ignored. See `.env.example` for the required variable names.
- **Zero-cost tooling.** Only free tools and services are used.

## Planned Stack

- Backend: Python, FastAPI, PostgreSQL, Alembic
- Frontend: to be added
- Chrome extension: to be added

## Repository Layout

- `backend/` - API and database code
- `scripts/` - helper scripts
- `docs/` - documentation

## Configuration

Copy both example files and replace the placeholder values:

    cp .env.example .env
    cp groq.env.example groq.env
    chmod 600 .env groq.env

- `.env` holds PostgreSQL settings only. Docker Compose passes this whole file to the database container.
- `groq.env` holds the Groq API key. It is never passed to a container.
- `app.env` holds backend-only secrets (`API_KEY`, `N8N_WRITER_PASSWORD`, `N8N_WEBHOOK_URL`, `N8N_WEBHOOK_KEY`) and flags. It is git-ignored; see `app.env.example`. `N8N_WEBHOOK_URL` is the full production URL of the n8n webhook, including the `http://` prefix and the secret path. `N8N_WEBHOOK_KEY` is the value of the webhook header.

All env files are git-ignored. Never commit real credentials.

Setup and usage instructions will be added as the backend is built.

## Profile

The candidate profile is stored in the database (table `profile`, single row). Scoring reads only the database.

Setup:

1. Copy `profile.txt.example` to `profile.txt` and fill it in with true facts only. `profile.txt` is a local draft, is ignored by git, and is not read by the app.
2. Start the API server.
3. From the repository root, with the backend virtual environment active, run:

       source backend/.venv/bin/activate
       python scripts/set_profile.py

The script sends the draft to `PUT /profile` and prints only the status code, character count, redaction counts and warnings. It never prints the API key or the profile text.

Endpoints (all require the `X-API-Key` header):

- `GET /profile` returns `content`, `updated_at`, `char_count`, `groq_view`, `redactions` and `warnings`. An empty profile returns 200 with empty content.
- `PUT /profile` with body `{"content": "<text>"}` replaces the whole profile. The text must be 1 to 2000 characters after trimming and must not contain NUL characters. There is no PATCH or DELETE; to reset, send a new PUT.

Example (replace `<API_KEY>` with your own key, and do not paste it anywhere public):

    curl -s -H "X-API-Key: <API_KEY>" http://127.0.0.1:8000/profile

Sanitizing: the stored text is exactly what you saved. Only the sanitized text (`groq_view`) is sent to Groq.

- Email addresses are replaced with `[removed]`.
- Phone numbers (7 or more digits, with or without separators, or with a `+` country code) are replaced with `[removed]`.
- Lines starting with `Address`, `Phone`, `Mobile`, `Email`, `Contact` or `Tel` followed by `:` or `-` are removed entirely.
- URLs are kept.
- Addresses cannot be detected reliably. If the text contains words such as street, barangay or city, the response includes a warning. The text is not changed, so remove the address yourself.

Check `groq_view` after every save to confirm what will be sent to Groq.

If the profile is empty (or empty after sanitizing), scoring does not run and the API returns an error starting with `Profile is not set`.

Changing the profile does not re-score jobs that already have a score for the current prompt version. Only new jobs are scored with the new profile.

## Scoring

Jobs that pass the title filter are scored from 0 to 100 by Groq (openai/gpt-oss-20b) against the sanitized candidate profile stored in the database (see Profile).

Run: POST /score/run?limit=5 with the X-API-Key header. The limit is 1 to 20 (default 5). The request is synchronous, runs the title filter first, and scores high-priority and newest jobs first.

Daily cap: the settings key daily_score_cap limits Groq calls per UTC day. Stored scores and failed calls both count toward it.

Stop reasons: daily_cap_reached, rate_limited, groq_unavailable, groq_auth_error.

## Applications

Applications are created only by you. The app never submits an application and never decides on its own that you applied.

"Did you apply?" flow:

1. `POST /jobs/{id}/open` records that you opened the listing. It sets `opened_at` once (the first call wins and later calls do not change it). It does not create an application and does not change the pipeline status.
2. `GET /jobs?awaiting_apply=true` lists jobs that were opened and have no application yet. `awaiting_apply=false` returns all other jobs. Without the parameter, the list behaves as before.
3. If you applied, call `POST /applications`. If you did not, nothing is recorded.

Endpoints (all require the `X-API-Key` header):

- `POST /applications` with body `{"job_id": 1, "applied_at": "<ISO 8601 with timezone>", "notes": "<text>"}`. Only `job_id` is required. The status is set to `applied` and the first history event is written. `applied_at` defaults to now and cannot be more than 1 day in the future. `notes` can have up to 2000 characters. A job in any pipeline status is accepted. A second application for the same job returns 409 with `existing_id`.
- `GET /applications` supports `status`, `job_id`, `q` (searches job title and company), `limit` (default 50, maximum 200) and `offset`. The newest `applied_at` comes first. Each item includes a summary of its job.
- `GET /applications/{id}` returns the application with its `events` (status history, oldest first).
- `PATCH /applications/{id}` changes only `status` and `notes`. Any of the seven statuses can be set, because there are no transition rules yet. A status change writes a history event in the same transaction as the update. Setting the same status writes no event.

Statuses: `applied`, `under_review`, `assessment`, `interview`, `offer`, `rejected`, `withdrawn`.

Not available yet: deleting an application (use `withdrawn` instead) and a "dismissed" state for listings you did not apply to.

Example (replace `<API_KEY>` with your own key, and do not paste it anywhere public):

    curl -s -X POST -H "X-API-Key: <API_KEY>" -H "Content-Type: application/json" -d '{"job_id": 1, "notes": "Applied on the company site"}' http://127.0.0.1:8000/applications

## Follow-ups and overdue reminders

A follow-up is a simple to-do item attached to one application. It has a title, an optional due date and a status (`pending` or `completed`). The server sets `completed_at` when a follow-up becomes `completed` and clears it when it goes back to `pending`.

Endpoints (all require the `X-API-Key` header):

- `POST /follow-ups` creates a follow-up (`application_id`, `title`, optional `due_date` as `YYYY-MM-DD`).
- `GET /follow-ups` lists follow-ups. Filters: `status`, `application_id`, `overdue`, `limit`, `offset`.
- `GET /follow-ups/{id}` returns one follow-up with a short summary of its application.
- `PATCH /follow-ups/{id}` changes `title`, `due_date` (null clears it) or `status`.
- `DELETE /follow-ups/{id}` deletes a follow-up. Deleting an application is still not available.

A follow-up is overdue when it is pending and its due date is before today in the Asia/Manila time zone. A due date of today is not overdue. `is_overdue` is calculated on every response and is not stored.

Reminders: the scheduler checks for overdue follow-ups on its first tick after startup and then at most once per hour. Each overdue follow-up gets one in-app notification of type `follow_up_overdue` with the link `/follow-ups/{id}`. A follow-up is not notified again unless its due date is moved later and passes again. Completed follow-ups and follow-ups without a due date never notify. Follow-ups on rejected or withdrawn applications do not create new reminders. Notifications that already exist are kept.

The setting `followup_reminders_enabled` (default `true`) turns reminders on or off. Reminders only use the database, so they run even when `scheduler_enabled` is `false`. Hunts and scoring still run only when `scheduler_enabled` is `true`.

Example (replace `<API_KEY>` with your own key, and do not paste it anywhere public):

    curl -s -X POST -H "X-API-Key: <API_KEY>" -H "Content-Type: application/json" -d '{"application_id": 1, "title": "Email the recruiter", "due_date": "2026-11-05"}' http://127.0.0.1:8000/follow-ups
## Email processing

Email processing turns stored emails into jobs and status updates. It runs when you call it, and the email sync (see Email sync) runs it automatically after new emails are saved. This API does not fetch mail from Gmail itself; n8n does.

Each row in `emails` has a `kind` (`job_alert` or `application`) and a `status` (`unprocessed`, `processed` or `error`).

Run: `POST /emails/process?limit=10` with the `X-API-Key` header. The limit is 1 to 50 (default 10). The request is synchronous and handles the oldest unprocessed emails first. Each email is its own transaction, so one failure does not stop the others. Only one run can happen at a time; a second request returns 409. The response lists `requested`, `processed`, `jobs_created`, `jobs_duplicate`, `classified`, `auto_status_changed`, `needs_review`, `errored`, `skipped_by_cap`, `stopped_reason` and the `cap`.

Job alerts (`job_alert`): the HTML is read with the Python standard library only. No AI is used and nothing in the email is opened or fetched. Only LinkedIn job links are accepted. Jobs are created with source `linkedin_email`, priority 1, pipeline status `new` and no description, and duplicates are skipped by normalized URL. After a successful parse the stored HTML is cleared. If the layout is not recognized, the email is marked `error` and the HTML is kept so you can inspect it.

Application emails (`application`): only the sender, the subject and a snippet are sent to Groq, each cut to 200 characters. The email body is never sent. Groq must answer with JSON containing only `class` (`confirmation`, `interview`, `assessment`, `info_request`, `rejection`, `offer` or `unknown`) and an integer `confidence` from 0 to 100. Anything else is invalid. Two invalid answers in a row mark the email as `error`. An `unknown` email is marked processed with no class, no notification and no change to any application.

Linking: an email is linked to an application when the job company appears as a whole word in the subject or snippet. Withdrawn applications and company names shorter than 3 characters are ignored. If there is not exactly one match, nothing is linked and an `email_needs_review` notification is created. You can link or unlink by hand with `PATCH /emails/{id}` and body `{"application_id": 1}` or `{"application_id": null}`. This never changes the application status.

Automatic status change: the status changes only when all of these are true:

- `email_auto_status_enabled` is `true`.
- The email is linked to exactly one application.
- The sender address matches an enabled allowed sender of kind `application`.
- `confidence` is at least `email_auto_status_min_confidence`.
- The change is forward, or a rejection, and the current status is not `rejected`, `offer` or `withdrawn`.

Mapping: `interview` sets `interview`, `assessment` sets `assessment`, `rejection` sets `rejected` and `offer` sets `offer`. `confirmation` never changes the status. `info_request` only creates a review notification. Otherwise a review notification explains the reason and the status is not changed. The change, its history event (source `email`) and the `status_changed` notification are written in one transaction.

Undo: `POST /application-events/{id}/undo` restores the previous status. It works only for events created by an email, only while that event is still the latest event of the application, and only once. The undo is recorded as a new event with source `undo`.

Allowed senders: `GET /allowed-senders`, `POST /allowed-senders` (`sender` as one exact email address and `kind`) and `PATCH /allowed-senders/{id}` (`enabled` only). There is no delete; disable a sender instead.

Reading emails: `GET /emails` supports `kind`, `status`, `class`, `linked`, `limit` and `offset`, newest first. `GET /emails/{id}` returns one email. The stored HTML body is never returned.

Settings: `email_auto_status_enabled` (default `true`), `email_auto_status_min_confidence` (50 to 100, default 85) and `email_classify_daily_cap` (1 to 100, default 30). The cap counts Groq email calls per UTC day and is separate from `daily_score_cap`. When the cap is reached, application emails stay `unprocessed` and job alerts are still processed. Rate limits, Groq outages and bad API keys stop the run and leave the current email `unprocessed`.

Example (replace `<API_KEY>` with your own key, and do not paste it anywhere public):

    curl -s -X POST -H "X-API-Key: <API_KEY>" "http://127.0.0.1:8000/emails/process?limit=5"

## Email sync

Email sync copies new Gmail messages into the `emails` table and then runs email processing on them. n8n only imports emails. Every decision is made by the Python backend.

How it works:

1. `POST /emails/sync` (header `X-API-Key`, no body) creates a row in `search_runs` and a step row with source `email` and status `running`. It then calls the n8n webhook with the run id and a `since` timestamp.
2. n8n reads the enabled allowed senders, asks Gmail for matching messages newer than `since` (at most 100), and inserts them into `emails` with status `unprocessed`. Messages that are already stored are skipped by `gmail_message_id`. n8n then writes the result (`found`, `new` and a `message`) to the step row and sets its status to `done`.
3. The backend waits in a background task and checks the step every 5 seconds. When the step is `done`, it runs email processing (up to 100 emails; the Groq daily cap still applies), closes the run and sets `total_new` to the number of new jobs created from LinkedIn job alerts. A `hunt_done` notification is created only when there is at least one new email or one new job.

Responses of `POST /emails/sync`:

- `202` with `{"run_id": 1}`: the sync was started.
- `401`: missing or wrong API key.
- `409`: an email sync is already running.
- `502`: n8n could not be reached or did not answer with a 2xx status.
- `503`: `N8N_WEBHOOK_URL` or `N8N_WEBHOOK_KEY` is not set.

`since` is the start time of the last email run whose step is `done`, minus 1 hour so that nothing is missed. On the first sync it is now minus `email_sync_lookback_days`. The format is ISO 8601 in UTC.

Errors are never silent. If n8n reports an error, or does not finish within `email_sync_timeout_seconds`, the step and the run are marked `error` and a line is written to `system_events` (component `email_sync`, with no email content). A stale check marks old `running` email syncs as `error` at the start of every sync and every scheduler email tick, for example after the backend restarted while waiting. Emails that stay `unprocessed` are handled by the next run. If email processing is busy (a hunt holds the same lock), the run ends with no new jobs and the emails wait for the next sync.

Settings: `email_sync_lookback_days` (1 to 30, default 7, used only for the first sync), `email_sync_timeout_seconds` (60 to 900, default 300) and `email_sync_interval_minutes` (15 to 1440, default 120).

Scheduler: the `email_sync` job runs every `email_sync_interval_minutes`, only when `scheduler_enabled` is `true`. It waits for n8n in its own thread, so hunts and scoring are not blocked. Email runs do not count for the hunt interval. Email runs are stored in `search_runs`, so they also appear in `GET /hunts`.

Role of n8n and its limits: n8n is only the email importer. It connects to Gmail with a credential that has the `gmail.readonly` scope only, and to PostgreSQL with the limited role `n8n_writer`. That role can:

- read `allowed_senders`;
- insert into `emails`, but read only the `gmail_message_id` column of it (it cannot read the subject, snippet or HTML, and it cannot read `jobs`);
- never update or delete `emails`;
- insert into `system_events` and `search_run_steps`;
- update only the result columns (`status`, `found`, `new`, `message`) of step rows whose status is still `running` (row-level security).

Only the sender, the subject, a snippet cut to 200 characters and, for job alerts only, the HTML are stored. Set both n8n workflows to not save execution data, so email content is not kept inside n8n.

While the Google OAuth app is in Testing mode, the Gmail refresh token expires about every 7 days, and the Gmail credential in n8n must be reconnected.

Example (replace `<API_KEY>` with your own key, and do not paste it anywhere public):

    curl -s -X POST -H "X-API-Key: <API_KEY>" http://127.0.0.1:8000/emails/sync
    
## Test database

Tests run against a separate database named `jobtracker_test` in the same PostgreSQL container, and refuse to run against any other database.

Create it once (from the repository root):

    sudo docker exec -i jobtracker-postgres psql -U jobtracker -d jobtracker -c "CREATE DATABASE jobtracker_test;"

Apply the migrations to it:

    cd backend
    source .venv/bin/activate
    POSTGRES_DB=jobtracker_test alembic upgrade head

Run the tests:

    pytest -q

Run migrations on the real database with plain `alembic upgrade head` (no `POSTGRES_DB` override). Do not run downgrades on the real database.

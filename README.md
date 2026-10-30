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
- `app.env` holds backend-only secrets (`API_KEY`, `N8N_WRITER_PASSWORD`) and flags. It is git-ignored; see `app.env.example`.

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

Not available yet: deleting an application (use `withdrawn` instead), a "dismissed" state for listings you did not apply to, and notifications for status changes.

Example (replace `<API_KEY>` with your own key, and do not paste it anywhere public):

    curl -s -X POST -H "X-API-Key: <API_KEY>" -H "Content-Type: application/json" -d '{"job_id": 1, "notes": "Applied on the company site"}' http://127.0.0.1:8000/applications

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

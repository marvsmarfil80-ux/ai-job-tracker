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

Both files are git-ignored. Never commit real credentials.

Setup and usage instructions will be added as the backend is built.

## Scoring

Jobs that pass the title filter are scored from 0 to 100 by Groq (openai/gpt-oss-20b) against a local candidate profile.

Setup: copy profile.txt.example to profile.txt and fill it in with true facts only. profile.txt is ignored by git and must stay under 4000 characters.

Run: POST /score/run?limit=5 with the X-API-Key header. The limit is 1 to 20 (default 5). The request is synchronous, runs the title filter first, and scores high-priority and newest jobs first.

Daily cap: the settings key daily_score_cap limits Groq calls per UTC day. Stored scores and failed calls both count toward it.

Stop reasons: daily_cap_reached, rate_limited, groq_unavailable, groq_auth_error.

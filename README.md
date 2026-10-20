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

Copy `.env.example` to `.env` and replace the placeholder values:

    cp .env.example .env

Setup and usage instructions will be added as the backend is built.

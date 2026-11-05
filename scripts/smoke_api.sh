#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../backend"

export POSTGRES_DB="jobtracker_smoke"
export API_KEY="smoke-test-key"
export N8N_WRITER_PASSWORD="smoke-test-password"
export N8N_WEBHOOK_URL="http://127.0.0.1:9/smoke"
export N8N_WEBHOOK_KEY="smoke-test-webhook-key"
export GROQ_API_KEY="mock"
export GROQ_MOCK="true"
export SCORE_INTERVAL_SECONDS="0"
export SCHEDULER_THREAD_ENABLED="false"

exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 --workers 1

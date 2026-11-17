# AI Job Tracker Frontend: DeepSeek Brain
Paste this at the top of every new DeepSeek chat, then paste the phase prompt.

## Role
You write frontend code for ONE phase at a time. You cannot see my repo. Only what I paste is true. Never invent files, endpoints, fields, props, flags or libraries. If something is missing, ask one short question.

## Project
Personal web app (localhost, single user) that finds remote jobs, scores them with AI, and tracks applications and job emails. The backend is done (FastAPI). The frontend lives in frontend/: Vite, React, TypeScript, Tailwind CSS, React Router. Desktop-first, one light theme, Inter font, indigo accent #4F46E5. Plain Tailwind only: no UI kit, no shadcn/ui, no Radix. No new library unless I approve its name and version.

## App hard rules (the UI must show them)
- No auto-submit of applications. Opening a listing is NOT "applied". After opening, ask "Did you apply?" and create an Application only when I click Yes.
- The AI only suggests (score, verdict, reason, red flags). Render reason and red flags as plain text, never as HTML.
- Notifications are in-app only.
- Every job from a feed shows "via <source>" with a link to the original listing.
- A resume draft is never saved automatically. I press Save.
- All UI text is English. Times come from the backend in UTC and are shown in Asia/Manila.
- Errors arrive as {"detail": ...}. Show the message only. 409 = conflict or already running. 429 = busy or daily limit. 502/503 = service problem.
- Slow actions (Run Hunt can take about 152 seconds) need a loading state and a long timeout.

## Forbidden
- Touching anything outside frontend/. The backend, env files, and ~/projects/n8n are off limits.
- Reading, printing or asking for any secret or env file. The browser never holds X-API-Key: the Vite dev proxy adds it.
- git commit, git push, npm install. I run those myself.
- Going beyond the phase scope. Extras are suggestions with one question, never silently included.

## Output format
- Start with a plan of at most 6 lines.
- Then complete files only, never diffs or snippets. One block per file in this exact form:
FILE: frontend/src/path/Name.tsx (NEW or EXISTING)
followed by one code block with the full file.
- No comments in code. English only in code and UI text.
- For an EXISTING file I will paste its current content. Return the full new file.
- End every answer with a STATUS block (below). Never claim the build passes: I run npm run build and report the real result.

## STATUS block
Phase / Done (cumulative, file path plus one line each) / Not done / Decisions not in the brief / Doubts / Next step.

## If your answer is cut off
I will write "continue from FILE: <path>". Continue from that file without repeating earlier files.

## If I paste a HANDOFF
Read it first and continue from its "Next step". Do not redo anything listed as Done.

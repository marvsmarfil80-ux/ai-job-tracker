# Privacy Policy

Last updated: 2026-11-04

AI Job Tracker is a personal, self-hosted tool. It is built and used by one person (the repository owner) to find remote jobs, track job applications and organize job-related email. It is not a hosted service, and nobody else signs in to it.

## What the app accesses

The app connects to one Gmail account through the read-only scope `https://www.googleapis.com/auth/gmail.readonly`. It can only read email. It cannot send, modify, label or delete anything.

It reads only messages from sender addresses that the owner has explicitly added to an allowlist. All other email is ignored.

## What the app stores

For each allowlisted message, the app stores in the owner's own PostgreSQL database:

- the sender, the subject and a short snippet (at most 200 characters);
- for job alert emails only, the HTML body, which is deleted right after the job links are extracted.

The database runs on the owner's computer. The app does not store attachments.

## What is sent to third parties

For application-related emails, the sender, the subject and the snippet (each cut to at most 200 characters) are sent to Groq to classify the email (for example interview or rejection). The email body is never sent. Nothing else from Gmail is sent to any third party.

## What the app does not do

- It does not sell, share or publish email data.
- It does not use email data for advertising.
- It does not use email data to train AI models.
- It does not submit job applications on the owner's behalf.
- No person reads the stored email data other than the owner.

## Google API Services User Data Policy

The use of information received from Google APIs adheres to the Google API Services User Data Policy, including the Limited Use requirements.

## Retention and deletion

Stored data stays in the owner's database until the owner deletes it. Access can be revoked at any time from the Google Account permissions page.

## Contact

Questions can be raised through the issues page of this repository.
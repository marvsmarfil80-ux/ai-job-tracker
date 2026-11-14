import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.resume import ResumeDraftOut
from app.security import require_api_key
from app.services.groq_client import get_groq_client
from app.services.resume import MAX_PDF_BYTES, run_resume_draft

router = APIRouter(
    prefix="/profile/resume", tags=["resume"], dependencies=[Depends(require_api_key)]
)


@router.post("/draft", response_model=ResumeDraftOut)
async def draft_resume(
    request: Request,
    db: Session = Depends(get_db),
    client: httpx.Client = Depends(get_groq_client),
):
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Only PDF files are supported.")

    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="The PDF is too large.")

    collected = bytearray()
    async for chunk in request.stream():
        if not chunk:
            continue
        if len(collected) + len(chunk) > MAX_PDF_BYTES:
            raise HTTPException(status_code=413, detail="The PDF is too large.")
        collected.extend(chunk)

    return await run_in_threadpool(run_resume_draft, db, client, bytes(collected))
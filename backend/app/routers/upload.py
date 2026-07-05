import os
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException

router = APIRouter(tags=["upload"])

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
):
    allowed_types = {
        "image/jpeg", "image/png", "image/webp", "image/gif",
        "video/mp4", "video/webm", "video/quicktime",
        "audio/mpeg", "audio/wav", "audio/webm",
        "application/pdf",
    }
    if file.content_type and file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"File type {file.content_type} not allowed")

    ext = Path(file.filename or "file").suffix if file.filename else ""
    unique_name = f"{uuid.uuid4().hex}{ext}"
    upload_dir = Path("/data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / unique_name
    content = await file.read()
    file_path.write_bytes(content)
    return {
        "url": f"/data/uploads/{unique_name}",
        "filename": file.filename or unique_name,
        "size": len(content),
        "content_type": file.content_type,
    }

"""路径B: Face swap + voice clone - async API.

Accepts uploads, creates a task, dispatches to Celery worker.
Returns immediately with task_id for polling.
"""
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from ..config import settings
from ..database import get_db
from ..models.task import Task, TaskStatus

router = APIRouter()


@router.post("/remake")
async def start_remake(
    original_video: UploadFile = File(..., description="Original video to remake"),
    source_face: Optional[UploadFile] = File(None, description="New face image"),
    voice_sample: Optional[UploadFile] = File(None, description="Voice sample for cloning"),
    face_prompt: str = Form("", description="Prompt for face generation"),
    narration_text: str = Form("", description="Narration text (empty=Whisper extract)"),
    enhance_face: bool = Form(True, description="Apply face enhancement"),
    remove_watermark: bool = Form(False, description="Remove TL/BR watermarks after processing"),
    user_id: int = Form(1, description="User ID"),
    db: AsyncSession = Depends(get_db),
):
    """Submit a video remake job (async).

    Returns task_id immediately. Poll GET /remake/{task_id} for status.
    """
    # Create task
    task = Task(
        user_id=user_id,
        title=f"Video Remake - {original_video.filename}",
        status=TaskStatus.PENDING,
        progress=0,
        input_data={"pipeline": "path_b", "original_filename": original_video.filename},
        config={"enhance_face": enhance_face, "face_prompt": face_prompt, "remove_watermark": remove_watermark},
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    task_id = task.id

    # Save uploaded files
    task_dir = f"{settings.output_dir}/tasks/{task_id}"
    os.makedirs(task_dir, exist_ok=True)

    video_path = f"{task_dir}/original_video.mp4"
    with open(video_path, "wb") as f:
        f.write(await original_video.read())

    face_path = ""
    if source_face:
        face_path = f"{task_dir}/source_face.png"
        with open(face_path, "wb") as f:
            f.write(await source_face.read())

    voice_path = ""
    if voice_sample:
        voice_path = f"{task_dir}/voice_sample.wav"
        with open(voice_path, "wb") as f:
            f.write(await voice_sample.read())

    # Update task input_data with file paths
    inp = dict(task.input_data or {})
    inp["video_path"] = video_path
    inp["face_path"] = face_path
    inp["voice_sample_path"] = voice_path
    inp["narration_text"] = narration_text
    task.input_data = inp
    await db.commit()

    # Dispatch to Celery worker
    from ..workers.tasks.remake_task import run_video_remake
    run_video_remake.delay(task_id, user_id)

    return {
        "task_id": task_id,
        "status": "pending",
        "message": "Remake job submitted. Poll GET /remake/{task_id} for progress.",
    }


@router.get("/remake/{task_id}")
async def get_remake_status(
    task_id: int,
    user_id: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Get status of a remake task."""
    q = select(Task).where(Task.id == task_id, Task.user_id == user_id)
    result = await db.execute(q)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id": task_id,
        "status": task.status.value,
        "progress": task.progress,
        "output_data": task.output_data,
        "error_message": task.error_message,
    }

@router.post("/remake/watermark-remove")
async def remove_watermark(
    video: UploadFile = File(..., description="Video to remove watermarks from"),
    tl_x1: int = Form(4, description="TL watermark x start"),
    tl_y1: int = Form(6, description="TL watermark y start"),
    tl_x2: int = Form(469, description="TL watermark x end"),
    tl_y2: int = Form(222, description="TL watermark y end"),
    br_x1: int = Form(388, description="BR watermark x start"),
    br_y1: int = Form(1097, description="BR watermark y start"),
    br_x2: int = Form(716, description="BR watermark x end"),
    br_y2: int = Form(1271, description="BR watermark y end"),
    reference_frame: int = Form(400, description="Clean background reference frame"),
    output_fps: int = Form(15, description="Output video frame rate"),
    user_id: int = Form(1, description="User ID"),
    db: AsyncSession = Depends(get_db),
):
    """Remove TL and BR watermarks from a video using hybrid blend + inpainting.

    Upload a video file. Returns task_id for polling.
    Process: per-frame multi-pass inpaint with brightness adjacency expansion.
    """
    task = Task(
        user_id=user_id,
        title=f"Watermark Removal - {video.filename}",
        status=TaskStatus.PENDING,
        progress=0,
        input_data={
            "pipeline": "watermark_remove",
            "original_filename": video.filename,
            "tl": {"x1": tl_x1, "y1": tl_y1, "x2": tl_x2, "y2": tl_y2},
            "br": {"x1": br_x1, "y1": br_y1, "x2": br_x2, "y2": br_y2},
            "reference_frame": reference_frame,
            "output_fps": output_fps,
        },
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    task_id = task.id

    # Save video
    task_dir = f"{settings.output_dir}/tasks/{task_id}"
    os.makedirs(task_dir, exist_ok=True)
    video_path = f"{task_dir}/input_video.mp4"
    with open(video_path, "wb") as f:
        f.write(await video.read())

    inp = dict(task.input_data or {})
    inp["video_path"] = video_path
    task.input_data = inp
    await db.commit()

    # Dispatch to Celery
    from ..workers.tasks.remake_task import run_watermark_removal
    run_watermark_removal.delay(task_id, user_id)

    return {
        "task_id": task_id,
        "status": "pending",
        "message": "Watermark removal job submitted. Poll GET /remake/{task_id} for progress.",
    }

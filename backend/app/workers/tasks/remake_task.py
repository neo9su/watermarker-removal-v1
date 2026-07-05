"""Celery task: Path B - face swap + voice clone video remake (sync DB)."""
import os
from ..celery_app import celery_app


@celery_app.task(bind=True, max_retries=1, time_limit=1800, soft_time_limit=1740)
def run_video_remake(self, task_id: int, user_id: int = 1):
    """Run Path B: face swap + TTS re-narration (fully sync).

    Time limit: 30 minutes.
    """
    return _remake_sync(task_id, user_id)


def _remake_sync(task_id, user_id):
    from sqlalchemy import select
    from ...db_sync_for_celery import get_session
    from ...models.task import Task, TaskStatus
    from ...config import settings
    from ...services.face_swap_service import face_swap_service
    from sqlalchemy.orm.attributes import flag_modified

    db = get_session()
    try:
        q = select(Task).where(Task.id == task_id, Task.user_id == user_id)
        task = db.execute(q).scalar_one_or_none()
        if not task:
            return {"error": f"Task {task_id} not found"}

        try:
            task.status = TaskStatus.PROCESSING
            task.progress = 5
            db.commit()

            od = dict(task.output_data or {})
            task_dir = f"{settings.output_dir}/tasks/{task_id}"
            os.makedirs(task_dir, exist_ok=True)

            input_data = task.input_data or {}
            video_path = input_data.get("video_path", f"{task_dir}/original_video.mp4")
            face_path = input_data.get("face_path", f"{task_dir}/source_face.png")
            narration_text = input_data.get("narration_text", "")
            enhance_face = (task.config or {}).get("enhance_face", True)

            # Step 0: Auto-extract face from source video if no face uploaded
            face_path_is_valid = (
                face_path
                and os.path.exists(face_path)
                and os.path.getsize(face_path) > 1000
            )
            if not face_path_is_valid and video_path and os.path.exists(video_path):
                from ...services.face_swap_service import extract_face_from_video
                extracted = extract_face_from_video(
                    video_path, f"{task_dir}/auto_extracted_face.png", num_samples=8
                )
                if extracted:
                    face_path = extracted
                    inp = dict(task.input_data or {})
                    inp["face_path"] = face_path
                    inp["face_source"] = "auto_extracted_from_video"
                    task.input_data = inp
                    flag_modified(task, "input_data")
                    db.commit()
                    od["auto_extracted_face"] = face_path

            if not face_path or not os.path.exists(face_path):
                raise RuntimeError(
                    "No source face available. Please upload a face image, "
                    "or ensure the source video contains a detectable face."
                )

            # Step 1: Face swap (sync via subprocess)
            task.progress = 10
            db.commit()

            swapped_path = f"{task_dir}/swapped_video.mp4"
            face_swap_service.swap_face(
                source_face_path=face_path,
                target_video_path=video_path,
                output_path=swapped_path,
                enhancer=enhance_face,
            )
            od["swapped_video"] = swapped_path
            task.progress = 80
            task.output_data = od
            flag_modified(task, "output_data")
            db.commit()

            # Step 2: TTS narration (optional, currently no-op placeholder)
            if narration_text:
                # Mark the video as the final result (skip audio mix for now)
                od["video_path"] = swapped_path
                od["tts_skipped"] = True
            else:
                od["video_path"] = swapped_path

            # Done
            task.status = TaskStatus.COMPLETED
            task.progress = 100
            task.output_data = od
            flag_modified(task, "output_data")
            db.commit()

            return {
                "task_id": task_id,
                "status": "completed",
                "video_path": od["video_path"],
            }

        except Exception as e:
            try:
                task.status = TaskStatus.FAILED
                task.error_message = str(e)[:500]
                task.output_data = dict(task.output_data or {})
                flag_modified(task, "output_data")
                db.commit()
            except Exception:
                pass
            return {"task_id": task_id, "status": "failed", "error": str(e)[:500]}
    finally:
        db.close()

# ─── Watermark Removal Task ──────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=1, time_limit=3600, soft_time_limit=3540)
def run_watermark_removal(self, task_id: int, user_id: int = 1):
    """Remove watermarks from a video via hybrid blend+inpaint.

    Time limit: 60 minutes.
    """
    from ...services.watermark_removal_service import watermark_removal_service
    from sqlalchemy import select
    from ...db_sync_for_celery import get_session
    from ...models.task import Task, TaskStatus
    from ...config import settings
    import os

    db = get_session()
    try:
        q = select(Task).where(Task.id == task_id, Task.user_id == user_id)
        task = db.execute(q).scalar_one_or_none()
        if not task:
            return {"error": f"Task {task_id} not found"}

        task.status = TaskStatus.PROCESSING
        task.progress = 5
        db.commit()

        task_dir = f"{settings.output_dir}/tasks/{task_id}"
        os.makedirs(task_dir, exist_ok=True)

        input_data = task.input_data or {}
        video_path = input_data.get("video_path", f"{task_dir}/input_video.mp4")
        output_path = f"{task_dir}/output.mp4"

        tl = input_data.get("tl", {"x1": 20, "y1": 91, "x2": 272, "y2": 162})
        br = input_data.get("br", {"x1": 449, "y1": 1185, "x2": 702, "y2": 1258})
        output_fps = input_data.get("output_fps", 15)

        # Convert tl/br dicts to service format
        tl_svc = {"y1": tl["y1"], "y2": tl["y2"], "x1": tl["x1"], "x2": tl["x2"]}
        br_svc = {"y1": br["y1"], "y2": br["y2"], "x1": br["x1"], "x2": br["x2"]}

        # Run watermark removal
        result_path = watermark_removal_service.remove_watermark(
            input_path=video_path,
            output_path=output_path,
            fps=output_fps,
            tl=tl_svc,
            br=br_svc,
        )

        # Mark complete
        od = dict(task.output_data or {})

        od["video_url"] = f"/api/v1/remake/files/{task_id}/output.mp4"
        task.output_data = od
        task.status = TaskStatus.COMPLETED
        task.progress = 100
        db.commit()

        return {"status": "completed", "output": result_path}

    except Exception as e:
        db.rollback()
        task.status = TaskStatus.FAILED
        task.error_message = str(e)
        db.commit()
        raise
    finally:
        db.close()

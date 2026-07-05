"""Face swap service using FaceFusion on GPU server (10.190.0.222).

Pipeline:
  1. Upload source face + target video to GPU server
  2. Run FaceFusion headless-run (face_swapper + face_enhancer)
  3. Download result

Requires:
  - SSH access to neo@10.190.0.222 (keyless)
  - FaceFusion conda env 'facefusion' on server
  - Model: inswapper_128 + gfpgan_1.4
"""
import asyncio
import shlex
import os
import tempfile
import uuid
from typing import Optional

def extract_face_from_video_sync(video_path: str, output_path: str, num_samples: int = 5) -> Optional[str]:
    """Extract the largest detected face from a video using insightface.

    Returns path to saved face image, or None if no face found.
    """
    try:
        import cv2
        import subprocess
        from insightface.app import FaceAnalysis

        # Sample N frames evenly across the video
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames == 0:
            cap.release()
            return None

        sample_indices = [int(total_frames * i / num_samples) for i in range(num_samples)]

        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=0, det_size=(640, 640))

        best_face = None
        best_area = 0

        for idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                continue
            faces = app.get(frame)
            for face in faces:
                if face.det_score < 0.5:
                    continue
                x1, y1, x2, y2 = face.bbox.astype(int)
                area = (x2 - x1) * (y2 - y1)
                if area > best_area:
                    best_area = area
                    best_face = (face, frame, x1, y1, x2, y2)

        cap.release()

        if best_face is None:
            return None

        _, frame, x1, y1, x2, y2 = best_face
        # Add some padding
        h, w = frame.shape[:2]
        pad = 20
        x1 = max(0, x1 - pad)
        y1 = max(0, y1 - pad)
        x2 = min(w, x2 + pad)
        y2 = min(h, y2 + pad)
        crop = frame[y1:y2, x1:x2]

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cv2.imwrite(output_path, crop)
        return output_path

    except Exception as e:
        print(f"[extract_face_from_video_sync] error: {e}")
        return None


async def extract_face_from_video(video_path: str, output_path: str, num_samples: int = 5) -> Optional[str]:
    """Async wrapper."""
    import asyncio
    return await asyncio.to_thread(extract_face_from_video_sync, video_path, output_path, num_samples)

from ..config import settings



class FaceSwapService:
    """In-container face swap using insightface inswapper — no SSH/FaceFusion needed."""

    def swap_face(self, source_face_path: str, target_video_path: str,
                  output_path: str, enhancer: bool = False,
                  enhancer_blend: float = 0.8) -> str:
        from .direct_face_swapper import DirectFaceSwapper
        swapper = DirectFaceSwapper()
        return swapper.detect_and_swap(source_face_path, target_video_path, output_path)

    def extract_face_from_video(self, video_path: str, output_path: str,
                                min_confidence: float = 0.5) -> str:
        import cv2
        from insightface.app import FaceAnalysis
        from onnxruntime import get_available_providers
        providers = [("CPUExecutionProvider", {})]
        detector = FaceAnalysis(name="buffalo_l", providers=providers)
        detector.prepare(ctx_id=0, det_size=(320, 320))
        cap = cv2.VideoCapture(video_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        step = max(1, total // 20)
        best_conf = min_confidence
        for frame_idx in range(0, total, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                continue
            faces = detector.get(frame)
            if faces and faces[0].det_score >= best_conf:
                best_conf = faces[0].det_score
                cv2.imwrite(output_path, frame)
        cap.release()
        if not os.path.exists(output_path):
            raise RuntimeError(f"No face detected (confidence>={min_confidence})")
        return output_path

face_swap_service = FaceSwapService()

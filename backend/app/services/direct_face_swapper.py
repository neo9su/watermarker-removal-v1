"""Direct insightface face swap — runs inside celery container, no SSH/FaceFusion."""
import os
import cv2
import numpy as np
import onnxruntime
import insightface
from insightface.app import FaceAnalysis
from insightface.model_zoo import get_model


class DirectFaceSwapper:
    """Run face swap directly in-container using insightface + inswapper onnx model."""

    MODEL_PATH = "/mnt/disk3/facefusion/.assets/models/inswapper_128.onnx"

    def __init__(self):
        self.swapper = None
        self.detector = None
        self._loaded = False

    def _ensure_loaded(self):
        if self._loaded:
            return
        providers = [("CPUExecutionProvider", {})]
        self.swapper = get_model(self.MODEL_PATH)
        self.detector = FaceAnalysis(
            name="buffalo_l",
            providers=providers,
        )
        # Use smaller det_size to handle cropped/partial faces better
        self.detector.prepare(ctx_id=0, det_size=(320, 320))
        self._loaded = True
        print("[DirectFaceSwapper] Model loaded")

    def detect_and_swap(self, source_face_path: str, target_video_path: str, output_video_path: str) -> str:
        """Detect face from source image, apply to every frame of target video, save result."""
        self._ensure_loaded()

        # 1. Get source face embedding
        src_img = cv2.imread(source_face_path)
        if src_img is None:
            raise FileNotFoundError(f"Cannot read source face: {source_face_path}")
        src_faces = self.detector.get(src_img)
        if not src_faces:
            # Retry with smaller det_size for tiny/partial source images
            self.detector.prepare(ctx_id=0, det_size=(160, 160))
            src_faces = self.detector.get(src_img)
            self.detector.prepare(ctx_id=0, det_size=(320, 320))
        if not src_faces:
            raise RuntimeError("No face detected in source image (even at det_size=160)")
        src_face = src_faces[0]
        print(f"[DirectFaceSwapper] Source face: {src_face.bbox}, score={src_face.det_score:.3f}")

        # 2. Process video frame by frame
        cap = cv2.VideoCapture(target_video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {target_video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        print(f"[DirectFaceSwapper] Video: {width}x{height}, {fps}fps, {total}frames")

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))

        count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Detect faces in target frame
            faces = self.detector.get(frame)
            if faces:
                # Swap all detected faces using source face
                for face in faces:
                    frame = self.swapper.get(frame, face, src_face, paste_back=True)

            out.write(frame)
            count += 1
            if count % 100 == 0:
                print(f"[DirectFaceSwapper] Processed {count}/{total} frames")

        cap.release()
        out.release()
        cv2.destroyAllWindows()
        print(f"[DirectFaceSwapper] Done: {count} frames -> {output_video_path}")
        return output_video_path

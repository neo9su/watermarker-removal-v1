"""Image upscale service using ComfyUI's RealESRGAN x4 model."""
import asyncio
import os
import time
import uuid
from typing import Optional

import httpx
from ..config import settings


class UpscaleService:
    """Upscales images using ComfyUI's ImageUpscaleWithModel node + RealESRGAN_x4plus."""

    def __init__(self):
        self.comfyui_url = getattr(settings, "comfyui_url", "http://10.190.0.222:8188").rstrip("/")
        self.timeout = 120.0
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def upscale_image(self, input_path: str, output_path: str, scale: int = 4) -> str:
        """Upscale a single image using ComfyUI workflow."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        image_name = await self._upload_image(input_path)
        if not image_name:
            raise RuntimeError("Failed to upload image to ComfyUI")
        workflow = self._build_upscale_workflow(image_name)
        prompt_id = await self._queue_prompt(workflow)
        if not prompt_id:
            raise RuntimeError("Failed to queue upscale workflow")
        result_data = await self._wait_for_result(prompt_id)
        if not result_data:
            raise RuntimeError("Upscale workflow failed or timed out")
        await self._download_result(result_data, output_path)
        return output_path

    async def _upload_image(self, image_path: str) -> str:
        """Upload an image to ComfyUI's input directory."""
        filename = f"upscale_input_{uuid.uuid4().hex[:8]}.png"
        client = self._get_client()
        with open(image_path, "rb") as f:
            files = {"image": (filename, f, "image/png")}
            data = {"subfolder": "", "type": "input"}
            resp = await client.post(f"{self.comfyui_url}/upload/image", files=files, data=data)
            if resp.status_code == 200:
                result = resp.json()
                return result.get("name", filename)
        return ""

    def _build_upscale_workflow(self, image_name: str) -> dict:
        """Build a ComfyUI workflow for upscaling."""
        return {
            "1": {"class_type": "LoadImage", "inputs": {"image": image_name}},
            "2": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": "RealESRGAN_x4plus.pth"}},
            "3": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["2", 0], "image": ["1", 0]}},
            "4": {"class_type": "SaveImage", "inputs": {"images": ["3", 0], "filename_prefix": "upscaled"}},
        }

    async def _queue_prompt(self, workflow: dict) -> str:
        """Queue a workflow prompt in ComfyUI."""
        client = self._get_client()
        resp = await client.post(f"{self.comfyui_url}/prompt", json={"prompt": workflow})
        if resp.status_code == 200:
            return resp.json().get("prompt_id", "")
        return ""

    async def _wait_for_result(self, prompt_id: str) -> Optional[dict]:
        """Poll ComfyUI history until the prompt completes."""
        start = time.time()
        client = self._get_client()
        while time.time() - start < self.timeout:
            await asyncio.sleep(2)
            try:
                resp = await client.get(f"{self.comfyui_url}/history/{prompt_id}")
                if resp.status_code == 200:
                    history = resp.json()
                    if prompt_id in history:
                        outputs = history[prompt_id].get("outputs", {})
                        for node_id, node_output in outputs.items():
                            if "images" in node_output:
                                return node_output["images"][0]
            except Exception:
                pass
        return None

    async def _download_result(self, image_info: dict, output_path: str):
        """Download the upscaled image from ComfyUI."""
        filename = image_info.get("filename", "")
        subfolder = image_info.get("subfolder", "")
        img_type = image_info.get("type", "output")
        params = {"filename": filename, "subfolder": subfolder, "type": img_type}
        client = self._get_client()
        resp = await client.get(f"{self.comfyui_url}/view", params=params)
        if resp.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(resp.content)
        else:
            raise RuntimeError(f"Failed to download upscaled image: {resp.status_code}")

    async def check_connectivity(self) -> bool:
        """Check if ComfyUI is reachable."""
        try:
            client = self._get_client()
            resp = await client.get(f"{self.comfyui_url}/system_stats")
            return resp.status_code == 200
        except Exception:
            return False


# Singleton
upscale_service = UpscaleService()

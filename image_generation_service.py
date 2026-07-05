"""Image generation service using the SD API server (http://10.190.0.222:7860)."""
import asyncio
import base64
import json
import os
from typing import Optional
import httpx
from ..config import settings


class ImageGenerationService:
    """Generates images from storyboard descriptions using SD API at port 7860.

    The SD server runs realisticVisionV51 model for photorealistic product images.
    """

    def __init__(self):
        self.base_url = settings.sd_api_url.rstrip("/")
        self.api_timeout = 120.0  # 2 min per image

    async def generate_scene_image(
        self,
        prompt: str,
        output_path: str,
        negative_prompt: str = "nsfw, ugly, deformed, text, watermark",
        width: int = 768,
        height: int = 768,
        steps: int = 20,
        cfg_scale: float = 7.0,
    ) -> str:
        """Generate a single image from text prompt and save to disk.

        Args:
            prompt: Image description (from storyboard visual_description).
            output_path: Where to save the image.
            negative_prompt: Things to avoid.
            width, height: Image dimensions (recommended 768x768 for square).
            steps: Sampling steps (20=balanced, 30=higher quality).
            cfg_scale: Classifier-free guidance scale (7=balanced).

        Returns:
            Path to saved image file, or empty string on failure.
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "steps": steps,
            "width": width,
            "height": height,
            "cfg_scale": cfg_scale,
            "batch_size": 1,
            "sampler_name": "Euler a",
        }

        async with httpx.AsyncClient(timeout=self.api_timeout) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/sdapi/v1/txt2img",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.TimeoutException:
                raise TimeoutError(f"SD API timed out after {self.api_timeout}s")
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"SD API returned {e.response.status_code}: {e.response.text[:200]}")
            except Exception as e:
                raise RuntimeError(f"SD API error: {e}")

        images = data.get("images", [])
        if not images:
            raise RuntimeError("SD API returned no images")

        # Decode and save the first image
        img_bytes = base64.b64decode(images[0])
        with open(output_path, "wb") as f:
            f.write(img_bytes)

        return output_path

    async def generate_scenes_batch(
        self,
        scenes: list[dict],
        output_dir: str,
        task_id: str = "",
    ) -> list[str]:
        """Generate images for all scenes in a storyboard.

        Args:
            scenes: List of scene dicts, each with 'visual_description', 'scene_number'.
            output_dir: Directory to save generated images.
            task_id: Optional task ID for organizing output.

        Returns:
            List of paths to generated images.
        """
        scenes_dir = os.path.join(output_dir, "scenes")
        os.makedirs(scenes_dir, exist_ok=True)

        image_paths = []
        for i, scene in enumerate(scenes):
            description = scene.get("visual_description", "")
            scene_num = scene.get("scene_number", i + 1)

            if not description:
                image_paths.append("")
                continue

            output_path = os.path.join(scenes_dir, f"scene_{scene_num:04d}.png")

            try:
                # Style-appropriate prompt enhancement
                enhanced_prompt = self._enhance_prompt(description)
                await self.generate_scene_image(
                    prompt=enhanced_prompt,
                    output_path=output_path,
                    width=768,
                    height=768,
                    steps=20,
                )
                image_paths.append(output_path)
            except Exception as e:
                print(f"Scene {scene_num} image generation failed: {e}")
                image_paths.append("")

        return image_paths

    def _enhance_prompt(self, description: str) -> str:
        """Enhance storyboard descriptions for better SD results."""
        # Add quality tags if not already present
        quality_tags = "masterpiece, best quality, highly detailed, cinematic lighting"
        if description.endswith((".", "!", "?")):
            return f"{description[:-1]}, {quality_tags}."
        return f"{description}, {quality_tags}"

    async def check_connectivity(self) -> bool:
        """Check if SD API is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/")
                return resp.status_code == 200
        except Exception:
            return False


# Singleton
image_gen_service = ImageGenerationService()

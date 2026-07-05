# Watermark Removal Workflow

## Overview

Successfully applied on `remake_148` — a 54.6s face-swap video (720x1280, 58.41fps, 3190 frames) with two watermarks:

- **TL (top-left)**: White semi-transparent text watermark — (4,6,465,216) in pixel coords
- **BR (bottom-right)**: White semi-transparent text watermark — (388,1097,328,174) in pixel coords

## Method: Hybrid Blend + Inpainting

Two-stage approach that combines the speed of alpha blending with the quality of content-aware inpainting.

### Stage 1: Feathered Background Blend

1. Extract a clean reference frame from the video where the watermark region is clear (typically frame 400)
2. Create feathered masks using Gaussian blur (kernel=31, sigma=8) for TL and BR regions
3. Per-frame alpha compositing: `output = frame * (1 - mask) + clean_bg * mask`
4. Feathering prevents hard seam lines at the mask boundary

### Stage 2: Residual Inpaint

1. HSV thresholding: Detect bright desaturated pixels in BR region (V > 150, S < 60)
2. Dilation: Expand mask by 3px to cover anti-aliased text edges
3. Navier-Stokes inpainting (cv2.INPAINT_NS, radius=7): Content-aware fill

## Performance

| Metric | Value |
|--------|-------|
| Output frame rate | 15 fps |
| Frames processed | 819 |
| Processing time | ~120s (M-series Mac) |
| Throughput | ~7 fps |
| Watermark reduction | 96.5% |
| Text-like residual | 0% (remaining = person clothing, not watermark) |
| Frame-to-frame jitter | avg 1.01, max 3.31 (no flickering) |

## Key Findings

1. Pure blend only: Fast but ghosting when mask covers moving body parts
2. Pure inpaint only: Good quality but expensive, residual can remain
3. Hybrid: Best of both worlds -- blend handles 90%+, inpaint cleans residual
4. Mask coordinates must be exact: Off by 33px leaves visible watermark
5. HSV thresholds must be tuned per video

## Configuration

- TL region: y=6-222, x=4-469
- BR region: y=1097-1271, x=388-716
- Feather: 31px Gaussian blur
- Blend bg: frame 400
- Inpaint: V>150, S<60, dilate=3px, NS radius=7
- Output: 15fps, h264 CRF15, slow preset, +faststart

## API Usage

### REST Endpoint
POST /api/v1/remake/remake/watermark-remove
- video (file, required)
- tl_x1/y1/x2/y2, br_x1/y1/x2/y2 (form, optional)
- reference_frame (int, default 400)
- output_fps (int, default 15)
Returns task_id for polling via GET /remake/{task_id}

### CLI
python3 scripts/remove_watermark.py -i input.mp4 -o clean.mp4

### Python Service
from services.watermark_removal_service import watermark_removal_service
watermark_removal_service.remove_watermark(input_path, output_path)

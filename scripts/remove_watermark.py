#!/usr/bin/env python3
"""Standalone CLI for watermark removal using hybrid blend + inpainting.

Usage:
    python3 scripts/remove_watermark.py --input video.mp4 --output clean.mp4 \\
        --tl-x1 4 --tl-y1 6 --tl-x2 469 --tl-y2 222 \\
        --br-x1 388 --br-y1 1097 --br-x2 716 --br-y2 1271 \\
        --fps 15 --reference-frame 400
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.app.services.watermark_removal_service import watermark_removal_service


def main():
    parser = argparse.ArgumentParser(description="Remove watermarks from video")
    parser.add_argument("--input", "-i", required=True, help="Input video path")
    parser.add_argument("--output", "-o", required=True, help="Output video path")

    # TL watermark
    parser.add_argument("--tl-x1", type=int, default=4)
    parser.add_argument("--tl-y1", type=int, default=6)
    parser.add_argument("--tl-x2", type=int, default=469)
    parser.add_argument("--tl-y2", type=int, default=222)

    # BR watermark
    parser.add_argument("--br-x1", type=int, default=388)
    parser.add_argument("--br-y1", type=int, default=1097)
    parser.add_argument("--br-x2", type=int, default=716)
    parser.add_argument("--br-y2", type=int, default=1271)

    parser.add_argument("--fps", type=int, default=15, help="Output FPS")
    parser.add_argument("--reference-frame", type=int, default=400)
    parser.add_argument("--feather", type=int, default=31)
    parser.add_argument("--v-thresh", type=int, default=150)
    parser.add_argument("--s-max", type=int, default=60)
    parser.add_argument("--inpaint-radius", type=int, default=7)
    parser.add_argument("--crf", type=int, default=15)
    parser.add_argument("--preset", default="slow")

    args = parser.parse_args()

    tl = {"y1": args.tl_y1, "y2": args.tl_y2, "x1": args.tl_x1, "x2": args.tl_x2}
    br = {"y1": args.br_y1, "y2": args.br_y2, "x1": args.br_x1, "x2": args.br_x2}

    print(f"Removing watermarks from {args.input}")
    print(f"  TL: ({tl[x1]},{tl[y1]})-({tl[x2]},{tl[y2]})")
    print(f"  BR: ({br[x1]},{br[y1]})-({br[x2]},{br[y2]})")
    print(f"  Output: {args.output} @ {args.fps}fps")

    watermark_removal_service.remove_watermark(
        input_path=args.input,
        output_path=args.output,
        fps=args.fps,
        tl=tl,
        br=br,
        reference_frame=args.reference_frame,
        feather=args.feather,
        v_thresh=args.v_thresh,
        s_max=args.s_max,
        inpaint_radius=args.inpaint_radius,
        crf=args.crf,
        preset=args.preset,
    )
    print("Done!")


if __name__ == "__main__":
    main()

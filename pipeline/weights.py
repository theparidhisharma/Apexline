"""Weight resolution: use the fine-tuned checkpoint automatically if present.

Drop your Colab-trained file at  weights/apexline_yolov8n_ft.pt  and every
entry point (runner CLI, server ingest, eval) picks it up with zero config.
Delete/rename it to fall back to zero-shot COCO yolov8n.pt.
"""
from __future__ import annotations

from pathlib import Path

FT_PATH = Path("weights/apexline_yolov8n_ft.pt")
FT_SEG_PATH = Path("weights/apexline_yolov8n_seg_ft.pt")
ZERO_SHOT = "yolov8n.pt"


def resolve_weights(requested: str | None = None) -> str:
    """'auto'/None -> fine-tuned if it exists, else zero-shot COCO."""
    if requested and requested != "auto":
        return requested
    if FT_PATH.exists():
        return str(FT_PATH)
    return ZERO_SHOT


def weights_info() -> dict:
    w = resolve_weights()
    return {"weights": w,
            "fine_tuned": w == str(FT_PATH),
            "classes": "single 'racecar' class (fine-tuned)" if w == str(FT_PATH)
                       else "COCO {car, truck, motorcycle} merged (zero-shot)"}

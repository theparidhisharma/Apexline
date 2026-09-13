"""SEE / detect — YOLO wrapper. Model id + confidence live in config, not code.

Checkpoint strategy (free, no training on the critical path):
  v0 (default)  : yolov8n.pt zero-shot, COCO classes {car, truck, motorcycle}
  v1 (if fine-tuned in Colab): weights/apexline_yolov8n_ft.pt (single class 'racecar')
  seg (optional): yolov8n-seg.pt when bbox-bottom footprint proves too crude
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np

COCO_VEHICLE_IDS = {2: "car", 3: "motorcycle", 7: "truck"}  # kart/open-wheel recall needs the merge


@dataclass
class Detection:
    frame_idx: int
    track_id: int
    xyxy: tuple[float, float, float, float]
    conf: float
    mask: np.ndarray | None = None  # polygon points (N,2) in image px if seg model


class Detector:
    def __init__(self, weights: str = "yolov8n.pt", conf: float = 0.25,
                 imgsz: int = 960, device: str | None = None,
                 classes: list[int] | None = None):
        from ultralytics import YOLO  # lazy import: keeps server importable without torch
        self.model = YOLO(weights)
        self.is_seg = weights.endswith("-seg.pt") or "seg" in Path(weights).stem
        self.conf = conf
        self.imgsz = imgsz
        self.device = device  # None -> auto; "mps" on MacBook, "cpu" on the i7
        # Class filter is decided by what the checkpoint actually predicts,
        # not by its filename. COCO-pretrained -> merge {car, motorcycle,
        # truck}. Any fine-tune (single 'racecar' class, or any custom name
        # set) -> no filter: every prediction is a vehicle by construction.
        if classes is not None:
            self.classes = classes
        else:
            names = getattr(self.model, "names", {}) or {}
            is_coco = names.get(2) == "car" and names.get(7) == "truck"
            self.classes = list(COCO_VEHICLE_IDS) if is_coco else None

    def track_video(self, source: str, sample_stride: int = 3) -> Iterator[list[Detection]]:
        """Stream per-frame detections with persistent ByteTrack IDs.

        sample_stride=3 on a 30fps source -> 10 fps effective sampling, the
        CPU-honest rate. Yields [] for skipped frames so downstream timing
        stays aligned to the source clock.
        """
        results = self.model.track(
            source=source, stream=True, persist=True, tracker="bytetrack.yaml",
            conf=self.conf, imgsz=self.imgsz, device=self.device,
            classes=self.classes, verbose=False, vid_stride=sample_stride,
        )
        for frame_idx, r in enumerate(results):
            out: list[Detection] = []
            if r.boxes is not None and r.boxes.id is not None:
                ids = r.boxes.id.int().tolist()
                confs = r.boxes.conf.tolist()
                boxes = r.boxes.xyxy.tolist()
                masks = r.masks.xy if (self.is_seg and r.masks is not None) else [None] * len(ids)
                for tid, cf, box, mk in zip(ids, confs, boxes, masks):
                    out.append(Detection(frame_idx, tid, tuple(box), cf,
                                         np.asarray(mk) if mk is not None else None))
            yield out

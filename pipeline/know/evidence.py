"""KNOW / evidence — clip cutting with overlay burn-in + SHA-256 manifest.

Every incident gets a +-3 s clip with the boundary polyline burned in, hashed
at creation. Nothing is deletable, only decided. No shell-string interpolation
into ffmpeg args (list-form subprocess only).
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import cv2
import numpy as np


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cut_clip(source: str, t_start_ms: int, t_end_ms: int, out_path: str,
             pad_s: float = 3.0) -> str:
    start = max(t_start_ms / 1000.0 - pad_s, 0.0)
    dur = (t_end_ms - t_start_ms) / 1000.0 + 2 * pad_s
    cmd = ["ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", source,
           "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "veryfast",
           "-an", "-movflags", "+faststart", out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    return sha256_file(out_path)


def burn_overlay(clip_path: str, boundary_px: np.ndarray | None, out_path: str,
                 label: str = "") -> str:
    """Re-encode a clip with the boundary polyline + label on every frame.

    IMPORTANT: the final file must be H.264 — cv2's mp4v (MPEG-4 Part 2) does
    NOT play in browser <video> tags, which made evidence clips look
    "missing" in the console. We draw with cv2 to a temp file, then transcode
    with ffmpeg to H.264 +faststart, and hash the FINAL artifact.
    boundary_px may be None (VLM engine has no homography): label-only burn.
    """
    tmp = str(Path(out_path).with_suffix(".tmp.mp4"))
    cap = cv2.VideoCapture(clip_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    vw = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    pts = (boundary_px.astype(np.int32).reshape(-1, 1, 2)
           if boundary_px is not None else None)
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if pts is not None:
            cv2.polylines(frame, [pts], False, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.polylines(frame, [pts], False, (60, 60, 220), 1, cv2.LINE_AA)
        if label:
            cv2.putText(frame, label, (16, h - 20), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (240, 240, 240), 2, cv2.LINE_AA)
        vw.write(frame)
    cap.release(); vw.release()
    subprocess.run(["ffmpeg", "-y", "-i", tmp, "-c:v", "libx264",
                    "-preset", "veryfast", "-pix_fmt", "yuv420p", "-an",
                    "-movflags", "+faststart", out_path],
                   check=True, capture_output=True)
    Path(tmp).unlink(missing_ok=True)
    return sha256_file(out_path)

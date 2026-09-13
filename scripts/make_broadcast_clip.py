"""Broadcast-look demo clip: perspective trackside camera, TV graphics,
multiple liveries, EXACT calibration — the ground truth still scripted.

This replaces the flat side-view synth with something that reads as real
trackside coverage: elevated 3/4 camera with true perspective (so the
distance-dependent ±error bands actually vary on screen), red-white kerb,
white boundary line, gravel strip, sponsor hoardings, a broadcast bug and
timing strip burned in, three hue-shifted liveries of a real car sprite.

Choreography (6 passes over the same corner exit):
  P1 clean · P2 tyre ON the line (LEGAL, must not flag) · P3 deep violation
  P4 marginal violation · P5 mid violation · P6 two cars, leader violates
=> exactly 4 violations. Every violation is approached gradually, so the
live FORESEE predictor has a trend to fire on BEFORE the crossing.

Usage:
  python scripts/make_broadcast_clip.py [--car-png sprite.png] [--fetch-sample]
  python -m pipeline.runner --video data/clips_src/broadcast.mp4 \
      --calibration data/calibrations/corner_broadcast.json
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np

W, H = 1280, 720
FPS = 25
# world frame (metres): x along the track 0..44, y lateral; boundary at y=0,
# INSIDE the track is y>0 (matches the pipeline's sign convention).
XM, Y_IN, Y_OUT = 44.0, 11.0, -7.0
TD_SCALE = 30  # top-down texture px per metre


def homographies():
    """world(m) -> image(px), built through a top-down texture warp."""
    # top-down texture pixel of world (x,y):  u = x*s, v = (Y_IN - y)*s
    td_w, td_h = int(XM * TD_SCALE), int((Y_IN - Y_OUT) * TD_SCALE)
    world_to_td = np.array([[TD_SCALE, 0, 0],
                            [0, -TD_SCALE, Y_IN * TD_SCALE],
                            [0, 0, 1]], np.float64)
    # camera trapezoid: far edge (y=Y_IN) short & high, near edge (y=Y_OUT) wide & low
    src = np.float32([[0, 0], [td_w, 0], [td_w, td_h], [0, td_h]])
    dst = np.float32([[338, 186], [1010, 152], [1560, 705], [-260, 760]])
    td_to_img = cv2.getPerspectiveTransform(src, dst).astype(np.float64)
    world_to_img = td_to_img @ world_to_td
    return world_to_td, td_to_img, world_to_img, (td_w, td_h)


def render_topdown(td_w: int, td_h: int) -> np.ndarray:
    s = TD_SCALE
    rng = np.random.default_rng(11)
    img = np.zeros((td_h, td_w, 3), np.uint8)

    def band(y0, y1, color):
        v0, v1 = int((Y_IN - y1) * s), int((Y_IN - y0) * s)
        img[max(v0, 0):min(v1, td_h)] = color

    band(0.0, Y_IN, (40, 42, 47))                       # asphalt
    band(-4.2, 0.0, (56, 58, 64))                       # asphalt run-off (modern)
    band(-2.1, -1.1, (150, 96, 30))                     # painted blue strip
    band(Y_OUT, -4.2, (120, 150, 168))                  # gravel trap
    band(Y_OUT, Y_OUT + 1.2, (52, 110, 42))             # grass beyond
    img = cv2.add(img, rng.integers(0, 12, (td_h, td_w, 1), np.uint8).repeat(3, 2))
    # kerb just outside the line (0 .. -0.9 m), 1.5 m stripes
    v0, v1 = int(Y_IN * s), int((Y_IN + 0.9) * s)
    for i, u in enumerate(range(0, td_w, int(1.5 * s))):
        cv2.rectangle(img, (u, v0), (u + int(1.5 * s), v1),
                      (60, 60, 210) if i % 2 == 0 else (235, 235, 235), -1)
    # white boundary line at y=0, 12 cm
    lv = int(Y_IN * s)
    cv2.rectangle(img, (0, lv - int(0.06 * s) - 1), (td_w, lv + int(0.06 * s) + 1),
                  (246, 246, 246), -1)
    # inner white line far side + pit-straight dashes
    cv2.rectangle(img, (0, int(0.35 * s)), (td_w, int(0.35 * s) + 3), (220, 220, 220), -1)
    # sponsor hoardings along the far barrier (top of texture)
    for i, txt in enumerate(["APEXLINE", "TRACKSHIFT", "SEE·KNOW·FORESEE", "PLAKSHA GP"]):
        u = 40 + i * int(td_w / 4.1)
        cv2.rectangle(img, (u, 2), (u + int(td_w / 4.6), int(0.3 * s)), (24, 22, 20), -1)
        cv2.putText(img, txt, (u + 14, int(0.24 * s)), cv2.FONT_HERSHEY_DUPLEX,
                    0.62, (240, 240, 240), 1, cv2.LINE_AA)
    # faint straight-ahead rubber lines on the racing line
    for k in range(3):
        vv = int((Y_IN - (1.1 + 0.28 * k)) * s)
        cv2.line(img, (0, vv), (td_w, vv), (33, 35, 39), 3, cv2.LINE_AA)
    return img


def livery_variants(sprite: np.ndarray) -> list[np.ndarray]:
    outs = [sprite]
    for hshift in (35, 95):
        s2 = sprite.copy()
        hsv = cv2.cvtColor(s2[:, :, :3], cv2.COLOR_BGR2HSV)
        hsv[:, :, 0] = (hsv[:, :, 0].astype(int) + hshift) % 180
        s2[:, :, :3] = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        outs.append(s2)
    return outs


def paste(canvas, sprite, cx, cy, width_px):
    h0, w0 = sprite.shape[:2]
    w1 = max(int(width_px), 8)
    h1 = max(int(h0 * w1 / w0), 6)
    sp = cv2.resize(sprite, (w1, h1), interpolation=cv2.INTER_AREA)
    x0, y0 = int(cx - w1 / 2), int(cy - h1)
    x1, y1 = x0 + w1, y0 + h1
    if x1 <= 0 or x0 >= canvas.shape[1] or y1 <= 0 or y0 >= canvas.shape[0]:
        return
    sx0, sy0 = max(0, -x0), max(0, -y0)
    x0, y0 = max(0, x0), max(0, y0)
    roi = canvas[y0:y1, x0:x1]
    sp = sp[sy0:sy0 + roi.shape[0], sx0:sx0 + roi.shape[1]]
    a = sp[:, :, 3:4].astype(np.float32) / 255.0
    roi[:] = (sp[:, :, :3] * a + roi * (1 - a)).astype(np.uint8)


def broadcast_garnish(frame, t_total_s, lap):
    # red channel bug
    cv2.rectangle(frame, (28, 24), (66, 52), (0, 6, 225), -1)
    cv2.putText(frame, "APX", (32, 44), cv2.FONT_HERSHEY_DUPLEX, .55, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.rectangle(frame, (66, 24), (238, 52), (18, 18, 24), -1)
    cv2.putText(frame, f"RACE  LAP {lap}/24", (76, 44), cv2.FONT_HERSHEY_DUPLEX, .5,
                (235, 235, 235), 1, cv2.LINE_AA)
    # timing strip
    ov = frame.copy()
    cv2.rectangle(ov, (28, H - 58), (470, H - 26), (14, 14, 18), -1)
    cv2.addWeighted(ov, .82, frame, .18, 0, frame)
    mm, ss = int(t_total_s // 60), t_total_s % 60
    cv2.putText(frame, f"T10 CAM  ·  {mm:02d}:{ss:05.2f}  ·  TRACK LIMITS MONITOR",
                (40, H - 37), cv2.FONT_HERSHEY_DUPLEX, .48, (225, 225, 225), 1, cv2.LINE_AA)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--car-png", default="data/clips_src/car_sprite.png")
    ap.add_argument("--fetch-sample", action="store_true")
    ap.add_argument("--out", default="data/clips_src/broadcast.mp4")
    ap.add_argument("--seconds-per-pass", type=float, default=5.2)
    a = ap.parse_args()

    if a.fetch_sample or not Path(a.car_png).exists():
        from make_synthetic_clip import fetch_sample_sprite  # noqa
        a.car_png = fetch_sample_sprite()
    sprite = cv2.imread(a.car_png, cv2.IMREAD_UNCHANGED)
    assert sprite is not None and sprite.shape[2] == 4, "need an RGBA sprite"
    liveries = livery_variants(sprite)

    w2td, td2img, w2img, (td_w, td_h) = homographies()
    td = render_topdown(td_w, td_h)
    warped = cv2.warpPerspective(td, td2img, (W, H))
    mask = cv2.warpPerspective(np.full(td.shape[:2], 255, np.uint8), td2img, (W, H))
    # backdrop: dusk sky gradient + grandstand/tree silhouette
    bg = np.zeros((H, W, 3), np.uint8)
    for r in range(H):
        k = r / H
        bg[r] = (int(96 + 30 * k), int(74 + 26 * k), int(52 + 22 * k))
    cv2.rectangle(bg, (0, 118), (W, 168), (34, 30, 28), -1)          # grandstand band
    for u in range(0, W, 26):                                        # crowd noise
        cv2.circle(bg, (u + (u // 26 % 3) * 7, 132 + (u // 26 % 4) * 8), 3,
                   (60 + u % 90, 55 + (u * 7) % 80, 70 + (u * 13) % 60), -1)
    bg[mask > 0] = warped[mask > 0]

    def to_px(x, y):
        p = w2img @ np.array([x, y, 1.0])
        return p[0] / p[2], p[1] / p[2]

    def scale_at(x, y):
        (u0, v0), (u1, _v1) = to_px(x - 0.5, y), to_px(x + 0.5, y)
        return math.hypot(u1 - u0, 0.0)  # px per metre along track

    CAR_LEN = 5.4
    vign = np.zeros((H, W), np.float32)
    cv2.circle(vign, (W // 2, H // 2), int(W * .72), 1.0, -1)
    vign = cv2.GaussianBlur(vign, (0, 0), 180)[..., None]

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    vw = cv2.VideoWriter(a.out, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    n = int(a.seconds_per_pass * FPS)

    # lateral profile: start mid-track (y=3.2), sweep toward apex, exit wide
    passes = [  # (min_y at exit, second car?, label)
        (+2.2, None, "P1 clean"),
        (+0.02, None, "P2 tyre on line — LEGAL"),
        (-1.55, None, "P3 deep violation"),
        (-0.42, None, "P4 marginal violation"),
        (-1.05, None, "P5 mid violation"),
        (-1.35, 1, "P6 two cars — leader violates"),
    ]
    rng = np.random.default_rng(5)
    frame_i = 0
    for pi, (y_min, second, _label) in enumerate(passes):
        wobble = rng.normal(0, .03, n)
        for f in range(n):
            t = f / (n - 1)
            frame = bg.copy()
            x = -5.0 + t * (XM + 10.0)
            # smooth approach to y_min then recover (guarantees a trend to predict on)
            phase = math.sin(math.pi * min(1.0, max(0.0, (t - 0.06) / 0.82)))
            y = 3.2 - (3.2 - y_min) * phase ** 1.5 + wobble[f]
            entries = []
            if second is not None:
                x2 = x - 9.5
                y2 = 3.0 - 1.1 * phase  # stays legal, inside
                entries.append((x2, y2, liveries[1]))
            entries.append((x, y, liveries[0] if second is None else liveries[2]))
            entries.sort(key=lambda e: e[1], reverse=True)  # far (big y) first
            for (ex, ey, sp) in entries:
                u, v = to_px(ex, ey)
                wpx = CAR_LEN * scale_at(ex, ey)
                sh = frame.copy()
                cv2.ellipse(sh, (int(u), int(v) - 2), (int(wpx * .34), int(wpx * .055)),
                            0, 0, 360, (16, 16, 18), -1)
                cv2.addWeighted(sh, .3, frame, .7, 0, frame)
                paste(frame, sp, u, v, wpx)
            frame = (frame.astype(np.float32) * (0.82 + 0.18 * vign)).astype(np.uint8)
            broadcast_garnish(frame, (frame_i) / FPS, 12 + pi // 3)
            vw.write(frame)
            frame_i += 1
    vw.release()
    import subprocess
    tmp = a.out + ".h264.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", a.out, "-c:v", "libx264", "-preset",
                    "veryfast", "-pix_fmt", "yuv420p", "-an", "-movflags",
                    "+faststart", tmp], check=True, capture_output=True)
    Path(tmp).replace(a.out)

    calib = {
        "H": np.linalg.inv(w2img).tolist(),          # px -> world (metres)
        "boundary_world": [[x, 0.0] for x in np.arange(0.0, XM + 0.01, 2.0)],
        "residual_px": 0.0,
        "boundary_reference": "white_line",
        "zone_polygon_px": None,
        "note": "broadcast-look scene — homography exact by construction",
    }
    Path("data/calibrations").mkdir(parents=True, exist_ok=True)
    Path("data/calibrations/corner_broadcast.json").write_text(json.dumps(calib))
    print(f"wrote {a.out} ({frame_i} frames) + data/calibrations/corner_broadcast.json")
    print("ground truth: P1 clean · P2 tyre-on-line LEGAL · P3 deep · P4 marginal ·"
          " P5 mid · P6 leader (2 cars)  => exactly 4 violations, all predictable")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    main()

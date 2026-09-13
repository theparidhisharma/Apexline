"""Generate a synthetic trackside demo clip + EXACT calibration for it.

When you can't get real footage that runs, make footage where you control the
ground truth. This renders a fixed-camera corner-exit scene (asphalt, kerb,
white boundary line, grass) and drives a car through it three times:

  pass 1 — clean, comfortably inside the line
  pass 2 — marginal, tyre ON the line (must NOT flag: tyre-on-line is legal)
  pass 3 — clear violation, all four wheels beyond the line

Because we built the scene, the pixel→metre homography is known exactly, so
the script also writes a perfect calibration JSON. Ground truth = the script
itself: pass 3 is the only violation. If the pipeline flags exactly one
incident here, your geometry is provably correct — that's a demo beat, not
just a fallback.

Detection realism: a procedurally drawn car may or may not trip YOLO. For
reliable detection, pass --car-png with any side-view car photo cutout
(transparent background PNG — free ones are all over the web, or cut your own
from a photo you took). The script composites it to scale.

Usage:
  python scripts/make_synthetic_clip.py                       # drawn car
  python scripts/make_synthetic_clip.py --car-png mycar.png   # real car cutout
  python -m pipeline.runner --video data/clips_src/synth.mp4 \
         --calibration data/calibrations/corner_synth.json
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
PX_PER_M = 32.0          # exact ground-plane scale we render at
LINE_Y = 470             # boundary line row (px). Below = outside (grass side)
CAR_LEN_M, CAR_H_PX = 4.6, 110


def render_background() -> np.ndarray:
    img = np.zeros((H, W, 3), np.uint8)
    img[:] = (34, 38, 44)                              # asphalt
    noise = np.random.default_rng(7).integers(0, 14, (H, W, 1), dtype=np.uint8)
    img = cv2.add(img, np.repeat(noise, 3, axis=2))
    img[LINE_Y + 8:, :] = (36, 92, 40)                 # grass
    g = np.random.default_rng(3).integers(0, 22, (H - LINE_Y - 8, W, 1), dtype=np.uint8)
    img[LINE_Y + 8:, :, 1] = cv2.add(img[LINE_Y + 8:, :, 1], g[:, :, 0])
    # red-white kerb strip just inside the line
    for x in range(0, W, 64):
        color = (46, 46, 200) if (x // 64) % 2 == 0 else (235, 235, 235)
        cv2.rectangle(img, (x, LINE_Y - 14), (x + 64, LINE_Y - 4), color, -1)
    cv2.rectangle(img, (0, LINE_Y - 4), (W, LINE_Y + 8), (245, 245, 245), -1)  # white line
    # distance boards for visual interest
    for i, x in enumerate((180, 560, 940)):
        cv2.rectangle(img, (x, 60), (x + 120, 130), (30, 30, 30), -1)
        cv2.putText(img, f"{150 - i * 50}", (x + 22, 112), cv2.FONT_HERSHEY_DUPLEX, 1.4,
                    (240, 240, 240), 2, cv2.LINE_AA)
    return img


def draw_car(canvas: np.ndarray, cx: int, cy: int, car_png: np.ndarray | None):
    """cy = bottom (contact patch) centreline of the car."""
    if car_png is not None:
        h0, w0 = car_png.shape[:2]
        w1 = int(CAR_LEN_M * PX_PER_M)
        h1 = max(1, int(h0 * w1 / w0))
        car = cv2.resize(car_png, (w1, h1), interpolation=cv2.INTER_AREA)
        x0, y0 = cx - w1 // 2, cy - h1
        x1, y1 = x0 + w1, y0 + h1
        if x1 <= 0 or x0 >= W:
            return
        sx0, sy0 = max(0, -x0), max(0, -y0)
        x0, y0 = max(0, x0), max(0, y0)
        roi = canvas[y0:y1, x0:x1]
        car = car[sy0:sy0 + roi.shape[0], sx0:sx0 + roi.shape[1]]
        if car.shape[2] == 4:
            a = car[:, :, 3:4].astype(np.float32) / 255.0
            roi[:] = (car[:, :, :3] * a + roi * (1 - a)).astype(np.uint8)
        else:
            roi[:] = car
        return
    # procedural side-profile car (photoreal it is not; YOLO may still bite)
    L = int(CAR_LEN_M * PX_PER_M)
    x0, y_top = cx - L // 2, cy - CAR_H_PX
    body = np.array([
        (x0, cy - 34), (x0 + 8, cy - 58), (x0 + int(L * .22), cy - 66),
        (x0 + int(L * .34), cy - CAR_H_PX + 6), (x0 + int(L * .68), cy - CAR_H_PX + 4),
        (x0 + int(L * .84), cy - 62), (x0 + L, cy - 52), (x0 + L, cy - 30),
        (x0 + L - 10, cy - 22), (x0 + 10, cy - 22),
    ], np.int32)
    cv2.ellipse(canvas, (cx, cy - 6), (L // 2, 12), 0, 0, 360, (18, 20, 22), -1)  # shadow
    cv2.fillPoly(canvas, [body], (28, 24, 190))
    cv2.fillPoly(canvas, [np.array([
        (x0 + int(L * .30), cy - 62), (x0 + int(L * .37), cy - CAR_H_PX + 12),
        (x0 + int(L * .64), cy - CAR_H_PX + 10), (x0 + int(L * .72), cy - 60),
    ], np.int32)], (140, 190, 210))
    for wx in (x0 + int(L * .22), x0 + int(L * .78)):
        cv2.circle(canvas, (wx, cy - 20), 22, (12, 12, 14), -1)
        cv2.circle(canvas, (wx, cy - 20), 10, (90, 90, 96), -1)
    cv2.rectangle(canvas, (x0 + L - 6, cy - 50, ), (x0 + L, cy - 40), (60, 200, 250), -1)


SAMPLE_URL = ("https://raw.githubusercontent.com/udacity/"
              "CarND-Vehicle-Detection/master/test_images/test1.jpg")


def fetch_sample_sprite(out="data/clips_src/car_sprite.png") -> str:
    """Download an open test image (Udacity CarND, MIT-licensed repo), find the
    strongest car with YOLO, GrabCut an alpha matte, save a sprite. Disclosed
    in DISCLOSURES.md. Needs internet once; the sprite is then cached."""
    if Path(out).exists():
        return out
    import urllib.request
    from ultralytics import YOLO
    tmp = "/tmp/apexline_sample_car.jpg"
    urllib.request.urlretrieve(SAMPLE_URL, tmp)
    img = cv2.imread(tmp)
    boxes = YOLO("yolov8n.pt")(img, conf=0.3, verbose=False)[0].boxes
    b = max(boxes, key=lambda b: float(b.conf))
    x0, y0, x1, y1 = [int(v) for v in b.xyxy[0]]
    m = 6
    x0, y0 = max(0, x0 - m), max(0, y0 - m)
    x1, y1 = min(img.shape[1], x1 + m), min(img.shape[0], y1 + m)
    crop = img[y0:y1, x0:x1]
    mask = np.zeros(crop.shape[:2], np.uint8)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(crop, mask, (3, 3, crop.shape[1] - 6, crop.shape[0] - 6),
                bgd, fgd, 5, cv2.GC_INIT_WITH_RECT)
    alpha = np.where((mask == 2) | (mask == 0), 0, 255).astype(np.uint8)
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(out, np.dstack([crop, alpha]))
    return out


def cut_sprite_from(photo: str, out="data/clips_src/car_sprite.png") -> str:
    """Cut a car sprite from any photo: strongest YOLO vehicle box + GrabCut
    alpha. Use a frame from your OWN fine-tune dataset so the demo car is one
    your trained model provably detects."""
    from ultralytics import YOLO
    img = cv2.imread(photo)
    assert img is not None, f"could not read {photo}"
    r = YOLO("yolov8n.pt")(img, conf=0.2, verbose=False)[0]
    assert len(r.boxes), "no vehicle found in that photo — try a clearer side view"
    b = max(r.boxes, key=lambda b: float(b.conf))
    x0, y0, x1, y1 = [int(v) for v in b.xyxy[0]]
    m = 6
    x0, y0 = max(0, x0 - m), max(0, y0 - m)
    x1, y1 = min(img.shape[1], x1 + m), min(img.shape[0], y1 + m)
    crop = img[y0:y1, x0:x1]
    mask = np.zeros(crop.shape[:2], np.uint8)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(crop, mask, (3, 3, crop.shape[1] - 6, crop.shape[0] - 6),
                bgd, fgd, 5, cv2.GC_INIT_WITH_RECT)
    alpha = np.where((mask == 2) | (mask == 0), 0, 255).astype(np.uint8)
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(out, np.dstack([crop, alpha]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--car-png", help="side-view car cutout with alpha (recommended)")
    ap.add_argument("--fetch-sample", action="store_true",
                    help="auto-download an open car image and cut a sprite from it")
    ap.add_argument("--cut-from", metavar="PHOTO",
                    help="cut the sprite from YOUR photo (e.g. an image from your "
                         "Roboflow F1 training set, so your fine-tune recognises it)")
    ap.add_argument("--out", default="data/clips_src/synth.mp4")
    ap.add_argument("--seconds-per-pass", type=float, default=5.0)
    a = ap.parse_args()

    car_png = None
    if a.cut_from and not a.car_png:
        a.car_png = cut_sprite_from(a.cut_from)
        print("sprite:", a.car_png)
    if a.fetch_sample and not a.car_png:
        a.car_png = fetch_sample_sprite()
        print("sprite:", a.car_png)
    if a.car_png:
        car_png = cv2.imread(a.car_png, cv2.IMREAD_UNCHANGED)
        assert car_png is not None, f"could not read {a.car_png}"

    bg = render_background()
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    vw = cv2.VideoWriter(a.out, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    n = int(a.seconds_per_pass * FPS)

    # pass offsets are of the CONTACT PATCH row vs the line: negative = inside
    passes = [
        (-70, None, "P1 clean — comfortably inside"),
        (-2,  None, "P2 tyre ON the line — LEGAL, must not flag"),
        (+55, None, "P3 clear violation — deep, all four wheels out"),
        (+14, None, "P4 marginal violation — just beyond the band"),
        (+34, None, "P5 mid violation — decisive but shallower"),
        (+48, -85,  "P6 two cars — leader violates under pressure"),
    ]
    for offset, second, _label in passes:
        for f in range(n):
            frame = bg.copy()
            t = f / (n - 1)
            cx = int(-160 + t * (W + 320))
            drift = int(offset * math.sin(math.pi * min(1.0, t * 1.6)) ** 2)
            if second is not None:  # trailing car stays legal, inside
                cx2 = cx - 340
                drift2 = int(second * math.sin(math.pi * min(1.0, t * 1.6)) ** 2 * 0.4)
                draw_car(frame, cx2, LINE_Y - 60 + drift2 // 4, car_png)
            draw_car(frame, cx, LINE_Y + drift, car_png)
            vw.write(frame)
    vw.release()

    # EXACT calibration: ground plane is the image plane at PX_PER_M scale.
    # World frame: x along the line (m), y positive INTO the track (inside).
    Hm = [[1.0 / PX_PER_M, 0.0, 0.0],
          [0.0, -1.0 / PX_PER_M, LINE_Y / PX_PER_M],
          [0.0, 0.0, 1.0]]
    boundary = [[x / PX_PER_M, 0.0] for x in range(0, W + 1, 64)]
    calib = {"H": Hm, "boundary_world": boundary, "residual_px": 0.0,
             "boundary_reference": "white_line", "zone_polygon_px": None,
             "note": "synthetic scene — homography exact by construction"}
    Path("data/calibrations").mkdir(parents=True, exist_ok=True)
    Path("data/calibrations/corner_synth.json").write_text(json.dumps(calib))

    print(f"wrote {a.out} ({3 * n} frames @ {FPS} fps) and data/calibrations/corner_synth.json")
    print("ground truth: P1 clean · P2 tyre-on-line (LEGAL) · P3 deep violation ·"
          " P4 marginal violation · P5 mid violation · P6 leader violates (2 cars)"
          " -> expect exactly 4 flagged incidents")
    print("run: python -m pipeline.runner --video", a.out,
          "--calibration data/calibrations/corner_synth.json")


if __name__ == "__main__":
    main()

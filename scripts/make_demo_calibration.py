"""Generate a synthetic fallback calibration so the pipeline runs before the
wizard has been used. Assumes a straight boundary along y=0 with the track on
the +y side and ~1:50 px:m near-field scale. Replace with a real calibration
the moment you have one — this exists so nothing blocks."""
import sys
sys.path.insert(0, ".")
import numpy as np
from pipeline.see.calibrate import CornerCalibration, fit_homography

image_points = [[100, 600], [1180, 600], [1000, 380], [280, 380]]
world_points = [[0, 0], [22, 0], [20, 14], [2, 14]]
H, res = fit_homography(image_points, world_points)
boundary_world = [[x, 0.0] for x in range(0, 24, 2)]
CornerCalibration(H, boundary_world, res).save("data/calibrations/corner_1.json")
print(f"Fallback calibration written (residual {res:.2f} px).")

"""
Live Kalibr AprilGrid detection preview.
Uses Kalibr's own aslam_cameras_april detector — required for the
checkerboard-embedded AprilGrid format that generic detectors can't handle.

SPACE  — save frame (only when enough tags detected)
Q/ESC  — quit

Usage: python3 detect.py [/dev/videoN]   default: /dev/video0
"""
import sys, os, time
import cv2
import numpy as np

sys.path.insert(0, '/opt/kalibr/devel/lib/python3/dist-packages')
sys.path.insert(0, '/opt/kalibr/src/kalibr/aslam_offline_calibration/kalibr/python')

import aslam_cv as acv
import aslam_cameras_april as acv_april


def open_camera(camera_index="/dev/video0", width=1280, height=480, fps=120):
    cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    cap.set(cv2.CAP_PROP_FOURCC, fourcc)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    if not cap.isOpened():
        raise RuntimeError("Error: Could not open webcam.")
    actual_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    actual_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    actual_fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    actual_fourcc_str = "".join([chr((actual_fourcc >> 8 * i) & 0xFF) for i in range(4)])
    print(f"Opened: {actual_w}x{actual_h} @ {actual_fps} fps, codec={actual_fourcc_str}")
    return cap, int(actual_w), int(actual_h)


# --- target parameters (must match april_6x10_40mm.yaml) ---
TAG_ROWS    = 6
TAG_COLS    = 10
TAG_SIZE    = 0.052
TAG_SPACING = 0.3077
MIN_TAGS    = int(max(TAG_ROWS, TAG_COLS) + 1)   # 11

SAVE_DIR = os.environ.get("CAPTURE_DIR") or "/data_out/debug/cam0"
_arg     = sys.argv[1] if len(sys.argv) > 1 else "/dev/video2"
DEVICE   = f"/dev/video{_arg}" if _arg.isdigit() else _arg

os.makedirs(SAVE_DIR, exist_ok=True)

# --- open camera ---
cap, W, H = open_camera(DEVICE, width=1280, height=720, fps=120)

# --- build Kalibr detector ---
opts = acv_april.AprilgridOptions()
opts.minTagsForValidObs  = MIN_TAGS
opts.showExtractionVideo = False
grid = acv_april.GridCalibrationTargetAprilgrid(
    TAG_ROWS, TAG_COLS, TAG_SIZE, TAG_SPACING, opts)

proj     = acv.DistortedPinholeProjection(800.0, 800.0, W/2.0, H/2.0, W, H)
geom     = acv.DistortedPinholeCameraGeometry(proj)
det_opts = acv.GridDetectorOptions()
det_opts.imageStepping          = False
det_opts.plotCornerReprojection = False
det_opts.filterCornerOutliers   = False
detector = acv.GridDetector(geom, grid, det_opts)

print(f"Detector ready. MIN_TAGS={MIN_TAGS}. SPACE=save, Q=quit.")
saved  = 0
first  = True

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    if first:
        print(f"Frame shape: {frame.shape}")
        first = False

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    ok, obs = detector.findTargetNoTransformation(gray)

    n = 0
    if obs is not None:
        corners = obs.getCornersImageFrame()
        if corners is not None and len(corners) > 0:
            n = len(corners) // 4
            for pt in corners:
                cv2.circle(frame, (int(pt[0]), int(pt[1])), 4,
                           (0, 255, 0) if ok else (0, 140, 255), -1)

    color  = (0, 255, 0) if ok else (0, 140, 255)
    status = f"Tags: {n}/{MIN_TAGS}  Saved: {saved}  "
    status += "SPACE=save" if ok else "move closer / adjust angle"
    status += "  Q=quit"
    cv2.putText(frame, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)

    cv2.imshow("AprilGrid detect", frame)
    key = cv2.waitKey(1) & 0xFF
    if key in (ord('q'), 27):
        break
    elif key == ord(' ') and ok:
        path = os.path.join(SAVE_DIR, f"{time.time_ns()}.png")
        cv2.imwrite(path, gray)
        saved += 1
        print(f"saved {path}")

cap.release()
cv2.destroyAllWindows()
print(f"Done. {saved} images saved to {SAVE_DIR}/")

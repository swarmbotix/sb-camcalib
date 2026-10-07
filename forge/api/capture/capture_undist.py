"""
Live undistorted preview using calibration from calib-camchain.yaml.
  SPACE  — save undistorted frame to cam0_undist/
  Q/ESC  — quit

Usage: python3 capture_undist.py [/dev/videoN]   default: /dev/video0
"""
import sys, os, time
import cv2
import numpy as np


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
    return cap


# --- calibration params from calib-camchain.yaml ---
fx, fy = 1425.657299, 1425.688157
cx, cy = 639.708900,  416.647552
k1, k2 = -0.509663,   0.293682
p1, p2 =  -0.000767,   0.000536

K    = np.array([[fx,  0, cx],
                 [ 0, fy, cy],
                 [ 0,  0,  1]], dtype=np.float64)
dist = np.array([k1, k2, p1, p2], dtype=np.float64)

W, H = 1280, 720

# Precompute undistortion maps once
new_K, roi = cv2.getOptimalNewCameraMatrix(K, dist, (W, H), alpha=0, newImgSize=(W, H))
map1, map2 = cv2.initUndistortRectifyMap(K, dist, None, new_K, (W, H), cv2.CV_16SC2)

print(f"New K after undistortion:\n{new_K}")

SAVE_DIR = os.environ.get("CAPTURE_DIR") or "/data_out/debug/cam0_undist"
os.makedirs(SAVE_DIR, exist_ok=True)

_arg   = sys.argv[1] if len(sys.argv) > 1 else "/dev/video0"
DEVICE = f"/dev/video{_arg}" if _arg.isdigit() else _arg

cap   = open_camera(DEVICE, width=W, height=H, fps=120)
saved = 0

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    undist = cv2.remap(frame, map1, map2, interpolation=cv2.INTER_LINEAR)

    cv2.putText(frame,  "Original",    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    cv2.putText(undist, "Undistorted", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    cv2.putText(undist, f"Saved: {saved}  SPACE=save  Q=quit",
                (10, H - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    cv2.imshow("Undistorted preview", np.vstack([frame, undist]))
    key = cv2.waitKey(1) & 0xFF
    if key in (ord('q'), 27):
        break
    elif key == ord(' '):
        path = os.path.join(SAVE_DIR, f"{time.time_ns()}.png")
        cv2.imwrite(path, undist)
        saved += 1
        print(f"saved {path}")

cap.release()
cv2.destroyAllWindows()
print(f"Done. {saved} undistorted images in {SAVE_DIR}/")

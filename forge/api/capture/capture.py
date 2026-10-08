"""
Live capture for Kalibr calibration.
  SPACE  — save frame
  Q/ESC  — quit

Images are saved as nanosecond timestamps (required by kalibr_bagcreater).
Usage: python3 capture.py [/dev/videoN]   default: /dev/video0
"""
import cv2, time, os, sys


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


SAVE_DIR = os.environ.get("CAPTURE_DIR") or "/output/debug/cam0"
_arg     = sys.argv[1] if len(sys.argv) > 1 else "/dev/video0"
DEVICE   = f"/dev/video{_arg}" if _arg.isdigit() else _arg

os.makedirs(SAVE_DIR, exist_ok=True)

cap   = open_camera(DEVICE, width=1280, height=720, fps=120)
saved = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    display = frame.copy()
    cv2.putText(display, f"Saved: {saved}  SPACE=capture  Q=quit",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.imshow("Capture", display)

    key = cv2.waitKey(1) & 0xFF
    if key in (ord('q'), 27):
        break
    elif key == ord(' '):
        ts   = time.time_ns()
        path = os.path.join(SAVE_DIR, f"{ts}.png")
        cv2.imwrite(path, frame)
        saved += 1
        print(f"  saved {path}")

cap.release()
cv2.destroyAllWindows()
print(f"Done. {saved} images in {SAVE_DIR}/")

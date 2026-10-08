"""
AprilTag + ArUco detection from camera stream (no Kalibr dependency).
  AprilTag: pupil-apriltags  (pip install pupil-apriltags)
  ArUco:    cv2.aruco        (bundled with opencv-contrib, or opencv-python >= 4.x)

Colours: AprilTag = green,  ArUco = cyan

SPACE  — save frame to cam0/
Q/ESC  — quit

Usage:
  python3 april_detector.py [/dev/videoN | N]
  python3 april_detector.py --family tag25h9 --aruco-dict 4x4_100
  python3 april_detector.py --no-april   # ArUco only
  python3 april_detector.py --no-aruco   # AprilTag only
"""
import sys, os, time, argparse
import cv2
import numpy as np
from timer_tictok import TimerTicTok

try:
    import pupil_apriltags as apriltag
    _APRIL_AVAILABLE = True
except ImportError:
    _APRIL_AVAILABLE = False

# ArUco dict name → OpenCV constant
ARUCO_DICTS = {
    "4x4_50":   cv2.aruco.DICT_4X4_50,
    "4x4_100":  cv2.aruco.DICT_4X4_100,
    "4x4_250":  cv2.aruco.DICT_4X4_250,
    "4x4_1000": cv2.aruco.DICT_4X4_1000,
    "5x5_50":   cv2.aruco.DICT_5X5_50,
    "6x6_50":   cv2.aruco.DICT_6X6_50,
}

COLOR_APRIL = (0, 255, 0)    # green
COLOR_ARUCO = (255, 255, 0)  # cyan


def open_camera(device="/dev/video0", width=1280, height=720, fps=120):
    cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    cap.set(cv2.CAP_PROP_FOURCC, fourcc)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera: {device}")
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps_actual = cap.get(cv2.CAP_PROP_FPS)
    fc = int(cap.get(cv2.CAP_PROP_FOURCC))
    fc_str = "".join([chr((fc >> 8 * i) & 0xFF) for i in range(4)])
    print(f"Opened: {w}x{h} @ {fps_actual} fps, codec={fc_str}")
    return cap, w, h


def draw_april(frame, det):
    corners = det.corners.astype(int)
    for i in range(4):
        cv2.line(frame, tuple(corners[i]), tuple(corners[(i + 1) % 4]), COLOR_APRIL, 2)
    cx, cy = det.center.astype(int)
    cv2.circle(frame, (cx, cy), 4, COLOR_APRIL, -1)
    cv2.putText(frame, f"A{det.tag_id}", (cx - 12, cy - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_APRIL, 2)


def draw_aruco(frame, corners, ids):
    if ids is None:
        return
    cv2.aruco.drawDetectedMarkers(frame, corners, ids, COLOR_ARUCO)


def parse_args():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("device", nargs="?", default="/dev/video0")
    p.add_argument("--family", default="tag36h11",
                   choices=["tag36h11", "tag25h9", "tag16h5",
                            "tagCircle21h7", "tagCircle49h12",
                            "tagCustom48h12", "tagStandard41h12",
                            "tagStandard52h13"])
    p.add_argument("--aruco-dict", default="4x4_50", choices=list(ARUCO_DICTS.keys()),
                   dest="aruco_dict")
    p.add_argument("--threads", type=int, default=2)
    p.add_argument("--quad-decimate", type=float, default=2.0, dest="quad_decimate")
    p.add_argument("--width",    type=int, default=1280)
    p.add_argument("--height",   type=int, default=720)
    p.add_argument("--fps",      type=int, default=120)
    p.add_argument("--no-april", action="store_true", dest="no_april")
    p.add_argument("--no-aruco", action="store_true", dest="no_aruco")
    args, _ = p.parse_known_args()
    if args.device.isdigit():
        args.device = f"/dev/video{args.device}"
    return args


def main():
    args = parse_args()

    use_april = not args.no_april
    use_aruco = not args.no_aruco

    if use_april and not _APRIL_AVAILABLE:
        sys.exit("pupil-apriltags not found: pip install pupil-apriltags")

    SAVE_DIR = os.environ.get("CAPTURE_DIR") or "/output/debug/cam0"
    os.makedirs(SAVE_DIR, exist_ok=True)

    cap, W, H = open_camera(args.device, args.width, args.height, args.fps)

    april_det = None
    if use_april:
        april_det = apriltag.Detector(
            families=args.family,
            nthreads=args.threads,
            quad_decimate=args.quad_decimate,
        )

    aruco_det = None
    if use_aruco:
        aruco_dict   = cv2.aruco.getPredefinedDictionary(ARUCO_DICTS[args.aruco_dict])
        aruco_params = cv2.aruco.DetectorParameters()
        aruco_det    = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)

    modes = []
    if use_april: modes.append(f"april={args.family}")
    if use_aruco: modes.append(f"aruco={args.aruco_dict}")
    print(f"Detector ready  {', '.join(modes)}  SPACE=save  Q=quit")

    saved = 0
    first = True
    timer = TimerTicTok()

    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        timer.update()

        if first:
            print(f"Frame shape: {frame.shape}")
            first = False

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        n_april = 0
        if april_det is not None:
            april_dets = april_det.detect(gray)
            n_april = len(april_dets)
            for det in april_dets:
                draw_april(frame, det)

        n_aruco = 0
        if aruco_det is not None:
            ac, ai, _ = aruco_det.detectMarkers(gray)
            n_aruco = len(ai) if ai is not None else 0
            draw_aruco(frame, ac, ai)

        status = f"dt:{timer.dt:.3f}s  "
        if use_april: status += f"April({args.family}):{n_april}  "
        if use_aruco: status += f"ArUco({args.aruco_dict}):{n_aruco}  "
        status += f"Saved:{saved}  SPACE=save  Q=quit"
        any_det = (n_april + n_aruco) > 0
        cv2.putText(frame, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (0, 255, 0) if any_det else (0, 140, 255), 2)

        cv2.imshow("AprilTag + ArUco detect", frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), 27):
            break
        elif key == ord(' '):
            path = os.path.join(SAVE_DIR, f"{time.time_ns()}.png")
            cv2.imwrite(path, gray)
            saved += 1
            print(f"saved {path}  (april={n_april} aruco={n_aruco})")

    cap.release()
    cv2.destroyAllWindows()
    print(f"Done. {saved} images saved to {SAVE_DIR}/")


if __name__ == "__main__":
    main()

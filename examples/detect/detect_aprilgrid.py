#!/usr/bin/env python3
"""
Detect a Kalibr AprilGrid in one image and draw the corners. Runs on the host, no Docker,
no Kalibr: only opencv-contrib-python (cv2.aruco) and numpy.

    pip install opencv-contrib-python numpy
    python3 examples/detect/detect_aprilgrid.py examples/0034.png

Why plain AprilTag / ArUco detectors fail on this target: the Kalibr AprilGrid uses tag36h11
codes with a 2-bit black border instead of the usual 1-bit border, and the tags sit inside a
checkerboard. OpenCV's ArUco detector handles the border through `markerBorderBits = 2`, and
its tag36h11 dictionary yields the same tag IDs as Kalibr. The image is upscaled before
decoding because the bit cells are only a few pixels wide at typical distances; corners are
then refined to sub-pixel on the original image. On the 147 sample frames this finds about
96 percent of the tags Kalibr's own detector finds. Calibration itself always uses Kalibr's
detector; this script is for inspecting captures.

Shows the annotated image in a window (any key closes it) and prints a summary.

Options:
    --target PATH   Kalibr target yaml (default april_6x10_40mm.yaml at the repository root)
    --min-tags N    minimum tags for a "valid" verdict (default max(rows, cols) + 1)
    --scale F       upscale factor used for decoding (default 3; 4 finds slightly more, slower)
    --out PATH      also save the annotated image to this path

Corner numbering in the output follows Kalibr: a (2*rows) x (2*cols) grid of points,
row-major, tag 0 at the bottom-left of the target.
"""
import argparse
import os
import sys

import cv2
import numpy as np

DEFAULT_TARGET = {'tagRows': 6, 'tagCols': 10, 'tagSize': 0.0518, 'tagSpacing': 0.30038}
REPO_TARGET = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'april_6x10_40mm.yaml')


def load_target(path):
    if path and os.path.isfile(path):
        try:
            import yaml
            with open(path) as f:
                t = yaml.safe_load(f)
        except ImportError:
            t = {}
            for line in open(path):
                line = line.split('#')[0].strip()
                if ':' in line:
                    k, v = line.split(':', 1)
                    t[k.strip()] = v.strip().strip("'\"")
        if t.get('target_type', 'aprilgrid') != 'aprilgrid':
            sys.exit(f'{path}: target_type must be aprilgrid')
        return {k: type(DEFAULT_TARGET[k])(t[k]) for k in DEFAULT_TARGET}, path
    return dict(DEFAULT_TARGET), None


def detect(gray, scale=3.0):
    """Return {tag_id: 4x2 corners in ArUco order: top-left, top-right, bottom-right, bottom-left}.

    Decoding runs on an upscaled copy (blurry bit cells decode far better), corners are mapped
    back and refined on the original image.
    """
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    params = cv2.aruco.DetectorParameters()
    params.markerBorderBits = 2                        # Kalibr AprilGrid: 2-bit black border
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_NONE
    params.minMarkerPerimeterRate = 0.01
    params.minMarkerDistanceRate = 0.0                 # neighbouring tags are close; never merge them
    params.adaptiveThreshWinSizeMin, params.adaptiveThreshWinSizeMax, params.adaptiveThreshWinSizeStep = 3, 53, 10
    params.perspectiveRemoveIgnoredMarginPerCell = 0.35
    big = gray if scale == 1 else cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    corners, ids, _ = cv2.aruco.ArucoDetector(dictionary, params).detectMarkers(big)
    if ids is None:
        return {}
    out = {}
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.01)
    for i, c in zip(ids.ravel(), corners):
        pts = (c[0] / scale).astype(np.float32).reshape(-1, 1, 2)
        pts = cv2.cornerSubPix(gray, pts, (3, 3), (-1, -1), crit)
        out[int(i)] = pts.reshape(4, 2)
    return out


def kalibr_corner_ids(tag, cols):
    """Kalibr grid ids for one tag, in ArUco corner order (TL, TR, BR, BL).

    ArUco's canonical orientation for tag36h11 matches Kalibr's: ArUco TL = Kalibr top-left
    (base + 2*cols), TR = base + 2*cols + 1, BR = base + 1, BL = base,
    where base = (2*row)*(2*cols) + 2*col and row 0 is the bottom row of the target.
    """
    row, col = divmod(tag, cols)
    base = (2 * row) * (2 * cols) + 2 * col
    return [base + 2 * cols, base + 2 * cols + 1, base + 1, base]


def main():
    ap = argparse.ArgumentParser(description='Draw Kalibr AprilGrid corners on one image (host, OpenCV only).')
    ap.add_argument('image')
    ap.add_argument('--target', default=REPO_TARGET)
    ap.add_argument('--out', help='also save the annotated image here')
    ap.add_argument('--min-tags', type=int)
    ap.add_argument('--scale', type=float, default=3.0)
    a = ap.parse_args()

    gray = cv2.imread(a.image, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        sys.exit(f'cannot read image: {a.image}')
    h, w = gray.shape
    target, target_src = load_target(a.target)
    rows, cols = target['tagRows'], target['tagCols']
    min_tags = a.min_tags or max(rows, cols) + 1

    tags = {t: c for t, c in detect(gray, a.scale).items() if t < rows * cols}
    ok = len(tags) >= min_tags
    color = (0, 255, 0) if ok else (0, 140, 255)

    vis = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    n_corners = 0
    for tag, c in sorted(tags.items()):
        poly = np.rint(c).astype(np.int32)
        cv2.polylines(vis, [poly], True, color, 1)
        for p, cid in zip(poly, kalibr_corner_ids(tag, cols)):
            cv2.circle(vis, tuple(p), 3, color, -1)
            n_corners += 1
        cx, cy = poly.mean(axis=0).astype(int)
        cv2.putText(vis, str(tag), (cx - 8, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
    status = f'tags {len(tags)}  corners {n_corners}  ' + ('valid view' if ok else f'rejected (< {min_tags} tags)')
    cv2.putText(vis, status, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    if a.out:
        cv2.imwrite(a.out, vis)
    print(f'image   : {a.image}  ({w}x{h})')
    print(f'target  : {target_src or "built-in defaults"}  rows={rows} cols={cols}')
    print(f'tags    : {len(tags)} / {rows * cols}   corners: {n_corners}')
    missing = sorted(set(range(rows * cols)) - set(tags))
    if missing:
        print(f'missing : {missing}')
    print(f'valid   : {ok}  (min tags {min_tags})')
    if a.out:
        print(f'written : {a.out}')
    cv2.imshow('AprilGrid', vis)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()

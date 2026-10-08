#!/usr/bin/env python3
"""Stage a input folder into the layout kalibr_bagcreater expects.

    <stage>/cam0/<ns>.png
    <stage>/camN/<ns>.png
    <stage>/imu0.csv            (copied through when present)

Frames are symlinked (never copied or modified). File names are rewritten to
nanosecond timestamps:

  * index naming  (0000.png ...):  ts = 1e9 + index * 1e8   (0.1 s per frame, synthetic)
    Identical indices across cameras therefore get identical timestamps, which is
    how Kalibr pairs synchronised multi-camera frames.
  * timestamp naming (>= 13 digit integer): name is kept as-is.

Subsampling: keep every STEP-th frame, then cap at MAX_FRAMES (evenly spread).
The same selection is applied to every camera so pairs stay aligned.

Usage:
    stage_frames.py <folder> <stage_dir> [--step N] [--max-frames N] [--flat]
"""
import argparse
import os
import re
import shutil
import sys

IMG_EXT = ('.png', '.jpg', '.jpeg', '.bmp')
CAM_RE = re.compile(r'^cam(\d+)$')


def list_images(d):
    return sorted(f for f in os.listdir(d)
                  if os.path.splitext(f)[1].lower() in IMG_EXT
                  and os.path.isfile(os.path.join(d, f)))


def select(names, step, max_frames):
    kept = names[::max(1, step)]
    if max_frames and len(kept) > max_frames:
        # evenly spread indices over the kept list
        idx = [round(i * (len(kept) - 1) / (max_frames - 1)) for i in range(max_frames)] if max_frames > 1 else [0]
        kept = [kept[i] for i in sorted(set(idx))]
    return kept


def ts_for(name):
    stem, _ = os.path.splitext(name)
    if len(stem) >= 13:
        return int(stem)
    return 10**9 + int(stem) * 10**8


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder')
    ap.add_argument('stage')
    ap.add_argument('--step', type=int, default=1)
    ap.add_argument('--max-frames', type=int, default=0)
    ap.add_argument('--flat', action='store_true', help='images sit directly in <folder>; treat as cam0')
    a = ap.parse_args()

    if os.path.isdir(a.stage):
        shutil.rmtree(a.stage)
    os.makedirs(a.stage)

    if a.flat:
        cams = [('cam0', a.folder)]
    else:
        cams = sorted(((e, os.path.join(a.folder, e)) for e in os.listdir(a.folder)
                       if CAM_RE.match(e) and os.path.isdir(os.path.join(a.folder, e))),
                      key=lambda t: int(CAM_RE.match(t[0]).group(1)))
    if not cams:
        sys.exit('stage_frames: no cam folders found')

    ref_names = list_images(cams[0][1])
    kept = select(ref_names, a.step, a.max_frames)
    kept_set = set(kept)

    for cam, srcdir in cams:
        dst = os.path.join(a.stage, cam)
        os.makedirs(dst)
        names = [n for n in list_images(srcdir) if n in kept_set]
        for n in names:
            ext = os.path.splitext(n)[1].lower()
            link = os.path.join(dst, f'{ts_for(n):019d}{ext}')
            os.symlink(os.path.abspath(os.path.join(srcdir, n)), link)
        print(f'  {cam}: staged {len(names)} / {len(list_images(srcdir))} frames')

    imu = os.path.join(a.folder, 'imu0.csv')
    if os.path.isfile(imu):
        shutil.copy(imu, os.path.join(a.stage, 'imu0.csv'))
        with open(imu) as f:
            n = sum(1 for _ in f) - 1
        print(f'  imu0.csv: {n} samples')


if __name__ == '__main__':
    main()

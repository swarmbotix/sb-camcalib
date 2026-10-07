#!/usr/bin/env python3
"""Inspect a calibration case folder and describe it as JSON.

A *case* is a folder with this layout:

    <case>/
      cam0/ *.png|*.jpg|*.bmp     required (or flat images directly in <case>/, treated as cam0)
      cam1/ ... camN/             optional; same frame count and identical file names as cam0
      imu0.csv                    optional; timestamp_ns, wx, wy, wz, ax, ay, az
      imu0.yaml                   required when imu0.csv is present (Kalibr IMU noise yaml)
      target.yaml                 optional; overrides the default target
      calib.yaml                  optional; per-case defaults for calibration options

Frame naming:
    index     0000.png, 0001.png ...            -> timestamps are synthesised from the index
    timestamp <nanoseconds>.png (>= 13 digits)  -> timestamps are used as-is (required for IMU)

Usage:
    inspect_case.py <case_dir>            prints JSON description
    inspect_case.py <case_dir> --strict   exit 1 on any error (missing cam0, mismatch, ...)
"""
import json
import os
import re
import sys

IMG_EXT = ('.png', '.jpg', '.jpeg', '.bmp')
CAM_RE = re.compile(r'^cam(\d+)$')


def list_images(d):
    return sorted(f for f in os.listdir(d)
                  if os.path.splitext(f)[1].lower() in IMG_EXT
                  and os.path.isfile(os.path.join(d, f)))


def naming_of(names):
    """Return 'timestamp' if every stem is an integer with >= 13 digits, else 'index' / 'other'."""
    stems = [os.path.splitext(n)[0] for n in names]
    if all(s.isdigit() for s in stems):
        return 'timestamp' if all(len(s) >= 13 for s in stems) else 'index'
    return 'other'


def inspect(case):
    info = {
        'case': case,
        'cams': [],           # list of {name, dir, count, naming}
        'flat': False,        # images directly in case dir, treated as cam0
        'imu_csv': None,
        'imu_yaml': None,
        'target_yaml': None,
        'calib_yaml': None,
        'mode': None,         # mono | joint | imu
        'errors': [],
        'warnings': [],
    }
    if not os.path.isdir(case):
        info['errors'].append(f'not a directory: {case}')
        return info

    entries = os.listdir(case)
    cam_dirs = sorted(
        (int(CAM_RE.match(e).group(1)), e) for e in entries
        if CAM_RE.match(e) and os.path.isdir(os.path.join(case, e)))

    if cam_dirs:
        expected = list(range(len(cam_dirs)))
        got = [i for i, _ in cam_dirs]
        if got != expected:
            info['errors'].append(f'camera folders must be contiguous cam0..camN, found {[e for _, e in cam_dirs]}')
        for _, e in cam_dirs:
            d = os.path.join(case, e)
            names = list_images(d)
            info['cams'].append({'name': e, 'dir': d, 'count': len(names), 'naming': naming_of(names),
                                 'names': names})
    else:
        names = list_images(case)
        if names:
            info['flat'] = True
            info['cams'].append({'name': 'cam0', 'dir': case, 'count': len(names),
                                 'naming': naming_of(names), 'names': names})
        else:
            info['errors'].append('no cam0/ folder and no images in case folder')

    for c in info['cams']:
        if c['count'] == 0:
            info['errors'].append(f"{c['name']}: no images")
        if c['naming'] == 'other':
            info['errors'].append(f"{c['name']}: file names must be integers (frame index or ns timestamp)")

    # multi-camera consistency: same count and identical names (sync by name)
    if len(info['cams']) > 1:
        ref = info['cams'][0]
        for c in info['cams'][1:]:
            if c['count'] != ref['count']:
                info['errors'].append(f"frame count mismatch: {ref['name']}={ref['count']} {c['name']}={c['count']}")
            elif c['names'] != ref['names']:
                info['errors'].append(f"file names differ between {ref['name']} and {c['name']} (frames must be synced by name)")
            if c['naming'] != ref['naming']:
                info['errors'].append(f"naming scheme differs between {ref['name']} and {c['name']}")

    for fn, key in (('imu0.csv', 'imu_csv'), ('imu0.yaml', 'imu_yaml'),
                    ('target.yaml', 'target_yaml'), ('calib.yaml', 'calib_yaml')):
        p = os.path.join(case, fn)
        if os.path.isfile(p):
            info[key] = p

    if info['imu_csv']:
        if not info['imu_yaml']:
            info['errors'].append('imu0.csv present but imu0.yaml (noise parameters) missing')
        if info['cams'] and info['cams'][0]['naming'] != 'timestamp':
            info['errors'].append('IMU calibration needs real nanosecond timestamps as image file names')
        info['mode'] = 'imu'
    elif len(info['cams']) == 1:
        info['mode'] = 'mono'
    elif len(info['cams']) > 1:
        info['mode'] = 'joint'

    for c in info['cams']:
        if 0 < c['count'] < 20:
            info['warnings'].append(f"{c['name']}: only {c['count']} frames; 30 to 60 well-spread frames recommended")

    # do not dump full name lists into the JSON
    for c in info['cams']:
        c['first'] = c['names'][0] if c['names'] else None
        c['last'] = c['names'][-1] if c['names'] else None
        del c['names']
    return info


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    strict = '--strict' in sys.argv
    if len(args) != 1:
        sys.exit(__doc__)
    info = inspect(args[0])
    print(json.dumps(info, indent=2))
    if strict and info['errors']:
        sys.exit(1)


if __name__ == '__main__':
    main()

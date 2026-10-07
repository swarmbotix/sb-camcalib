#!/usr/bin/env python3
"""Arrange Kalibr outputs into the camcalib output layout and write manifest.json.

Kalibr writes everything next to the bag, prefixed by the bag basename:
    calib-camchain.yaml  calib-results-cam.txt  calib-report-cam.pdf
    calib-camchain-imucam.yaml  calib-imu.yaml  calib-results-imucam.txt  calib-report-imucam.pdf

This script rearranges them into:
    <out>/cam<k>/camchain.yaml        per-camera slice (intrinsics only, plus T_cn_cnm1 for k>0)
    <out>/rig/{camchain.yaml,results-cam.txt,report-cam.pdf}     when N >= 2
    <out>/imu/{camchain-imucam.yaml,imu.yaml,results-imucam.txt,report-imucam.pdf}
    <out>/manifest.json

For N == 1 the full camera result goes to cam0/ and rig/ is not created.

Usage:
    split_camchain.py <out_dir> <bag_basename> --manifest '<json string>'
"""
import argparse
import json
import os
import shutil
import sys

import yaml


def move(src, dst):
    if os.path.isfile(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        return dst
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('bagtag', help='bag basename without extension, e.g. calib')
    ap.add_argument('--manifest', default='{}', help='JSON with run metadata to merge into manifest.json')
    a = ap.parse_args()

    out = a.out
    pre = os.path.join(out, a.bagtag)
    manifest = json.loads(a.manifest)
    manifest.setdefault('outputs', {})

    camchain_path = pre + '-camchain.yaml'
    if not os.path.isfile(camchain_path):
        sys.exit(f'split_camchain: {camchain_path} not found (camera calibration failed?)')

    with open(camchain_path) as f:
        chain = yaml.safe_load(f)
    cams = sorted(chain.keys(), key=lambda k: int(k[3:]))
    n = len(cams)
    manifest['num_cameras'] = n

    nan = any('nan' in json.dumps(chain[c]).lower() for c in cams)
    manifest['nan_in_camchain'] = nan

    if n == 1:
        move(camchain_path, os.path.join(out, 'cam0', 'camchain.yaml'))
        move(pre + '-results-cam.txt', os.path.join(out, 'cam0', 'results-cam.txt'))
        move(pre + '-report-cam.pdf', os.path.join(out, 'cam0', 'report-cam.pdf'))
        manifest['outputs']['cam0'] = 'cam0/camchain.yaml'
    else:
        for c in cams:
            d = os.path.join(out, c)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, 'camchain.yaml'), 'w') as f:
                yaml.safe_dump({c: chain[c]}, f, default_flow_style=None)
            manifest['outputs'][c] = f'{c}/camchain.yaml'
        move(camchain_path, os.path.join(out, 'rig', 'camchain.yaml'))
        move(pre + '-results-cam.txt', os.path.join(out, 'rig', 'results-cam.txt'))
        move(pre + '-report-cam.pdf', os.path.join(out, 'rig', 'report-cam.pdf'))
        manifest['outputs']['rig'] = 'rig/camchain.yaml'
    move(pre + '-poses-cam0.csv', os.path.join(out, 'rig' if n > 1 else 'cam0', 'poses-cam0.csv'))

    # IMU stage outputs (optional)
    imucam = pre + '-camchain-imucam.yaml'
    if os.path.isfile(imucam):
        move(imucam, os.path.join(out, 'imu', 'camchain-imucam.yaml'))
        move(pre + '-imu.yaml', os.path.join(out, 'imu', 'imu.yaml'))
        move(pre + '-results-imucam.txt', os.path.join(out, 'imu', 'results-imucam.txt'))
        move(pre + '-report-imucam.pdf', os.path.join(out, 'imu', 'report-imucam.pdf'))
        move(pre + '-poses-imucam-imu0.csv', os.path.join(out, 'imu', 'poses-imucam-imu0.csv'))
        manifest['outputs']['imu'] = 'imu/camchain-imucam.yaml'

    with open(os.path.join(out, 'manifest.json'), 'w') as f:
        json.dump(manifest, f, indent=2)
    print(json.dumps(manifest['outputs'], indent=2))
    if nan:
        print('!! NaN in camchain: re-run with --focal <px>', file=sys.stderr)
        sys.exit(3)


if __name__ == '__main__':
    main()

---
name: calib-rig
description: Calibrate N synchronised cameras (stereo is N=2) jointly with ./camcalib (Kalibr in Docker), producing intrinsics per camera plus inter-camera extrinsics T_cn_cnm1 in rig/camchain.yaml. Use when the user has cam0..camN folders, asks for stereo / multi-camera / rig / extrinsic / baseline calibration, or wants each camera calibrated independently from one capture.
---

# Multi-camera rig calibration (N >= 2)

One Kalibr run estimates all intrinsics and the chain of extrinsics between consecutive
cameras. Mono is the same code path with N=1; use the `calib-mono` skill for that.

## 1. Check the input folder

```
<folder>/
  cam0/0000.png ...       required
  cam1/0000.png ...       same frame count AND identical file names as cam0
  cam2/ ... camN/         contiguous numbering, no gaps
  target.yaml             optional, overrides april_6x10_40mm.yaml
  calib.yaml              optional, per-folder defaults (examples/calib.yaml)
```

Identical file name across `cam*/` means the same capture instant. Index names become
synthetic timestamps (0.1 s per frame); ns-timestamp names (>= 13 digits) are used as is.
All cameras must use the same naming scheme. Kalibr still accepts views in which only a
subset of cameras sees the target.

Validate:

```bash
./camcalib inspect <folder>
```

Errors that must be fixed in the capture, not by renaming blindly: `frame count mismatch`,
`file names differ`, non-contiguous `cam*` folders, mixed naming schemes.

## 2. Models and target

One model for all cameras or one per camera, in `cam0..camN` order:

```bash
--models pinhole-radtan                      # all cameras
--models pinhole-equi pinhole-radtan         # cam0 fisheye, cam1 normal
```

Target resolution: `--target` > `<folder>/target.yaml` > `april_6x10_40mm.yaml`. Check
`tagSize` and `tagSpacing` against the printed grid.

## 3. Run

```bash
./camcalib <folder>                                   # joint: intrinsics + extrinsics
./camcalib <folder> --models pinhole-equi             # fisheye rig
./camcalib <folder> --step 2 --max-frames 60          # thin frames
./camcalib <folder> --approx-sync 0.02                # time tolerance between cameras [s]
./camcalib <folder> --independent                     # N separate mono runs, no extrinsics
./camcalib <folder> --dry-run
```

Use `--independent` only when the user does not need extrinsics, or when cameras were not
truly synchronised but share file names.

## 4. Read the result

Joint mode:

```
<folder>/calib/
  cam0/camchain.yaml      cam0 intrinsics
  cam1/camchain.yaml      cam1 intrinsics + T_cn_cnm1 (cam0 -> cam1)
  camK/camchain.yaml      camK intrinsics + T_cn_cnm1 (camK-1 -> camK)
  rig/camchain.yaml       full Kalibr camchain, all cameras, all T_cn_cnm1
  rig/results-cam.txt     reprojection error per camera, baselines, views used
  rig/report-cam.pdf      plots
  input.json  manifest.json  log.txt
```

Independent mode: each `cam<k>/` holds a full standalone calibration (`camchain.yaml`,
`results-cam.txt`, `report-cam.pdf`), and `rig/` is absent.

Extrinsics convention: `T_cn_cnm1` is a 4x4 homogeneous matrix mapping points from camera
n-1 into camera n. For camera 2 expressed in camera 0: `T_c2_c0 = T_c2_c1 * T_c1_c0`.
Camera frame: X right, Y down, Z forward. The translation column of `T_cn_cnm1` is the
baseline in metres; for a stereo pair its norm is the baseline length.

Report to the user: per-camera intrinsics and reprojection error, baseline (translation)
and rotation between cameras, views used, and `nan_in_camchain` from `manifest.json`.

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| `frame count mismatch` / `file names differ` | fix the capture; names must be identical across `cam*/` |
| `nan` in camchain | `--focal <px>` (per rig, one value), or collect more tilted views |
| extrinsics implausible | too few views seen by all cameras; add 20 to 30 shared views at different depths |
| few views used | `--mi-tol -1`, or more diverse frames |
| one camera far worse than the others | add frames seen only by that camera covering its outer edges |
| run failed | `<folder>/calib/log.txt`; `calib.bag` is kept on failure |

Capture guidance: 30 to 60 frames per camera with full coverage, plus 20 to 30 frames
visible to all cameras at several depths for the extrinsics.

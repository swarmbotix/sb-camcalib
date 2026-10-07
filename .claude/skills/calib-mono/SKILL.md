---
name: calib-mono
description: Calibrate the intrinsics of a single camera from a folder of AprilGrid images using ./camcalib (Kalibr in Docker). Use when the user has one camera, one image folder, or asks for mono / single-camera / intrinsic calibration, lens distortion parameters, or a camchain.yaml for one camera.
---

# Single-camera (mono) calibration

Runs Kalibr `kalibr_calibrate_cameras` on one camera through `./camcalib`. Output is the
camera matrix, distortion coefficients, reprojection statistics and a PDF report.

## 1. Check the case folder

Expected layout (either form):

```
<case>/cam0/0000.png 0001.png ...      frame index names
<case>/cam0/<ns>.png ...               or nanosecond timestamps (>= 13 digits)
<case>/*.png                           or images directly in <case>/ (treated as cam0)
```

Rules: png/jpg/jpeg/bmp, read as 8-bit grayscale, all frames the same resolution, file
stems must be integers. Optional files: `target.yaml` (overrides `april_6x10_40mm.yaml`),
`calib.yaml` (per-case defaults, see `examples/calib.yaml`).

Validate before calibrating:

```bash
./camcalib inspect <case>
```

Fix every line under `errors` before continuing. Typical: non-integer file stems, mixed
resolutions, no images found.

## 2. Confirm the target

Default target is `april_6x10_40mm.yaml` at the repository root (6x10 AprilGrid, 40 mm tags).
If the user printed a different grid, or the printed tag size differs, copy the yaml into
the case as `target.yaml` and set `tagSize` (metres) and `tagSpacing` (gap / tag size).
Checkerboard and circlegrid are also accepted by Kalibr; Charuco is not.

## 3. Pick the camera model

| Lens | `--models` |
|---|---|
| normal, up to ~120 deg FOV | `pinhole-radtan` (default) |
| fisheye / wide angle | `pinhole-equi` (first choice), `ds-none`, `eucm-none` |
| omnidirectional | `omni-radtan`, `omni-none` |

## 4. Run

```bash
./camcalib <case>                                  # defaults, results in <case>/calib/
./camcalib <case> --models pinhole-equi            # fisheye
./camcalib <case> --step 2 --max-frames 60         # thin a long capture
./camcalib <case> --out /path/to/out               # custom output folder
./camcalib <case> --dry-run                        # print the plan only
```

Runtime: minutes for 30 to 60 frames. The first run pulls a ~7 GB image.

## 5. Read the result

```
<case>/calib/
  cam0/camchain.yaml      intrinsics: camera_model, intrinsics [fu fv pu pv], distortion_model, distortion_coeffs, resolution
  cam0/results-cam.txt    reprojection error mean / std per camera, number of views used
  cam0/report-cam.pdf     plots: corner coverage, reprojection errors, polar error
  case.json               inspect output
  manifest.json           mode, models, step, focal init, target, kalibr commit, date, nan_in_camchain
  log.txt                 full Kalibr log
```

Report to the user: model, intrinsics, distortion coefficients, reprojection error
(mean and std in px) and views used. Good: mean below ~0.3 px for a 1 to 2 MP camera with
sharp frames. Flag `nan_in_camchain: true` in `manifest.json` as a failed run.

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| `nan` in camchain | focal init failed. `--focal <px>`, roughly `width / (2 tan(hfov/2))`. Also check tilt diversity. |
| very few views used, high error | `--mi-tol -1` to keep near-duplicate views, or collect more diverse frames |
| garbage corners | mixed resolutions in the folder; remove the odd frames |
| run failed | read `<case>/calib/log.txt`; `calib.bag` is kept on failure |

Data-quality guidance for recapture: 30 to 60 sharp frames, target filling corners and
edges of the image, 30 to 45 degree tilt about both axes, several distances, some roll.

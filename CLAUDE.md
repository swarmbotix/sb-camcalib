# sb_kalibr

Camera calibration in a box. [Kalibr](https://github.com/ethz-asl/kalibr) (ROS Noetic) is built
into a Docker image (`swarmbotix/sb_kalibr:latest`, pulled on first use); the host script
`camcalib` runs it on one input folder and writes results to `<folder>/calib/`. The image holds
no data and no target; everything dataset-specific is mounted at run time.

Mode is inferred from the folder, never from a flag: camera count = number of `cam*/`
subfolders, IMU stage = presence of `imu0.csv`. Flags only modify how a mode runs.

## Where to look

| Need | Go to |
|---|---|
| Calibrate one camera | skill `calib-mono` |
| Calibrate a stereo / N-camera rig | skill `calib-rig` |
| Calibrate cameras + IMU | skill `calib-imu`, background in `docs/imu.md` |
| Exact input rules and output file layout | `docs/input-format.md` |
| Install, all `camcalib` options, env vars, container mounts | `docs/commands.md` |
| Live capture tools, camera models, targets, capture guidance | `docs/capture-and-targets.md` |
| Edit `forge/api`, rebuild or publish the image, failure modes, license | `docs/development.md` |
| User-facing quick start | `README.md` |

## Every supported operation

| # | Input folder contains | Mode | Command | Key outputs |
|---|---|---|---|---|
| 1 | `cam0/` with index names (`0000.png`) | mono | `./camcalib FOLDER` | `cam0/{camchain.yaml,results-cam.txt,report-cam.pdf}` |
| 2 | `cam0/` with ns names (`1700000000033000000.png`) | mono | same | same |
| 3 | images directly in `FOLDER/`, no `cam0/` | mono (flat) | same | same |
| 4 | `cam0/ .. camN/`, identical file names | joint: intrinsics + extrinsics | `./camcalib FOLDER` | `rig/camchain.yaml` (`T_cn_cnm1`), `cam<k>/camchain.yaml` slices, `rig/{results-cam.txt,report-cam.pdf}` |
| 5 | `cam0/ .. camN/` | independent, N mono runs | `./camcalib FOLDER --independent` | `cam<k>/{camchain.yaml,results-cam.txt,report-cam.pdf}`, no `rig/` |
| 6 | `cam0/` (ns names) + `imu0.csv` + `imu0.yaml` | mono, then camera-IMU | `./camcalib FOLDER` | row 1 outputs + `imu/{camchain-imucam.yaml,imu.yaml,results-imucam.txt,report-imucam.pdf}` |
| 7 | `cam0/ .. camN/` (ns names) + `imu0.csv` + `imu0.yaml` | joint, then camera-IMU | `./camcalib FOLDER` | row 4 outputs + `imu/*`, one `T_cam_imu` per camera |
| 8 | row 6 or 7 plus `camchain.yaml` copied from an earlier run | camera-IMU only | `./camcalib FOLDER --camchain /input/camchain.yaml` | `imu/*`; camera stage skipped |

Every run also writes `input.json`, `manifest.json`, `log.txt`; `calib.bag` stays only with
`--keep-bag` or on failure.

Modifiers for any row: `--models M` (one for all) or `--models M0 M1 ...` (one per camera;
`pinhole-radtan` default, `pinhole-equi`, `pinhole-fov`, `omni-radtan`, `omni-none`,
`ds-none`, `eucm-none`), `--out DIR`, `--step N`, `--max-frames N`, `--focal PX`,
`--target PATH` or `FOLDER/target.yaml`, `FOLDER/calib.yaml` for per-folder defaults,
`--imu-models`, `--mi-tol F`, `--approx-sync S`, `--keep-bag`, `--dry-run`, `--verbose`.
Other commands: `./camcalib inspect FOLDER`, `./camcalib shell [FOLDER]`,
`./camcalib capture <script> /dev/videoX`, `./camcalib build`, `./camcalib version`.

## Combinations that fail or surprise

| Combination | Result |
|---|---|
| `imu0.csv` with index-named images | refused: synthetic timestamps cannot align with IMU data |
| `imu0.csv` without `imu0.yaml` | refused |
| `--independent` with `imu0.csv` | IMU stage silently skipped |
| `--independent` with `--camchain` | `--camchain` ignored |
| `--camchain` without `imu0.csv` | camera stage skipped, output holds only the copied camchain |
| flat images plus any `cam*/` folder | flat images ignored; flat layout is single camera only |
| `cam0/`, `cam2/` (gap) | refused: `cam*` must be contiguous |
| frame counts or file names differ across `cam*/` | refused; fix the capture, never rename blindly |
| index and ns naming mixed across cameras | refused |
| `--models` count not 1 and not equal to camera count | refused |
| Charuco target | not a Kalibr target; AprilGrid (default), checkerboard or circlegrid only |
| cameras on unsynchronised clocks with different file names | unsupported; only identical names pair frames |

## Conventions

- `T_cn_cnm1` maps points from camera n-1 into camera n; `T_c2_c0 = T_c2_c1 * T_c1_c0`.
- `T_cam_imu` maps points from the IMU frame into the camera frame.
- Camera frame: X right, Y down, Z forward.
- Index names become synthetic timestamps at 0.1 s per frame; ns names (>= 13 digits) are used as is.
- Container mounts: case at `/input` (read-only), output at `/output`, default
  target at `/defaults/target.yaml`. Paths given to `--target` / `--camchain` are container paths.

## Repository layout

```
camcalib                 host entrypoint (bash)
april_6x10_40mm.yaml     default target (Kalibr AprilGrid yaml)
README.md                quick start for users
docs/                    reference: input-format, commands, capture-and-targets, imu, development
.claude/skills/          calib-mono, calib-rig, calib-imu
examples/                sample mono dataset: 0000..0146.png (1280x800, flat layout) and its calib/ output;
                         detect/detect_aprilgrid.py draws Kalibr AprilGrid corners on one image (host, OpenCV only)
targets/                 printable targets (PDF / PNG)
forge/                   image source; only for rebuilding
  dockerfile             ROS Noetic + Kalibr (pinned commit, patched) + container API
  build.bash             docker build (+ --push)
  patches/               kalibr-fixes.patch
  api/                   /opt/camcalib in the image: entrypoint.sh, calibrate.sh,
                         inspect_input.py, stage_frames.py, split_camchain.py, capture/
```

Fast edit loop: `CAMCALIB_DEV=1 ./camcalib FOLDER` overlays `forge/api` on the published image
without a rebuild.

## Status

Verified 2026-10-07 against a previous host-built Kalibr pipeline: 1280x800 mono within
0.2 px, 1440x1080 FLIR stereo within 0.05 mm. The IMU stage (rows 6 to 8) is wired per the
Kalibr command line but not yet exercised end to end with a real dataset.

## Credits

Packaging layer around Kalibr (Autonomous Systems Lab, ETH Zurich, and Skybotix AG), BSD
license in `LICENSE-kalibr`. *This product includes software developed by the Autonomous
Systems Lab and Skybotix AG.* Single upstream modification: `forge/patches/kalibr-fixes.patch`.

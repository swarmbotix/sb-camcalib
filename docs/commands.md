# Installation and command reference

## Installation

Prerequisites: Docker (tested with 29.x), Linux host. For live capture tools: X11 and
`/dev/video*` access.

### Use the published image (default)

The image is published on Docker Hub as **`swarmbotix/sb_kalibr:latest`**. The `camcalib`
script defaults to it and pulls it automatically the first time it is missing locally
(~7 GB download, one time).

```bash
git clone https://github.com/ubicoders/sb_kalibr.git
cd sb_kalibr
./camcalib version                            # triggers the pull, prints image + Kalibr info
```

Explicit pull or a pinned tag:

```bash
docker pull swarmbotix/sb_kalibr:latest
export CAMCALIB_IMAGE=swarmbotix/sb_kalibr:<tag>   # in your shell profile, to pin a version
```

Only `camcalib` and `april_6x10_40mm.yaml` from this repository are used at run time.

### Build the image locally (last resort)

Build only if you cannot reach Docker Hub or you modified `forge/` (dockerfile, Kalibr patch,
container API).

```bash
bash forge/build.bash          # ~10 min first time (Kalibr compile); tags swarmbotix/sb_kalibr:latest + :<date>
```

The local tag shadows the published one, so `camcalib` uses your build without any further
setting. To publish a new version (maintainers): `docker login` as `swarmbotix`, then
`bash forge/build.bash --push`. `CAMCALIB_IMAGE_REPO=<registry>/<name>` retargets the tag.

## Commands and options

```
camcalib [calibrate] [FOLDER] [--out DIR] [options]    FOLDER defaults to the current directory
camcalib inspect [FOLDER]                            describe the input folder, no calibration
camcalib shell [FOLDER]                              bash inside the container (ROS + Kalibr sourced)
camcalib capture <script> [args]                     live capture / detection tools
camcalib build [--tag T] [--push] [--no-cache]       build the image locally (last resort)
camcalib version
```

Calibration options (passed through to the container; `camcalib calibrate --help`):

| Option | Meaning | Default |
|---|---|---|
| `--models M [M ...]` | Kalibr camera model, one per camera or one for all | `pinhole-radtan` |
| `--target PATH` | target yaml, container path. Put the file in the input folder as `target.yaml` instead, or rely on the default | resolution order below |
| `--step N` | keep every N-th frame | 1 |
| `--max-frames N` | cap frames per camera after `--step`, evenly spread | none |
| `--focal PX` | manual focal-length initialisation | auto |
| `--independent` | N cameras: calibrate each alone, no extrinsics | off |
| `--camchain PATH` | skip the camera stage; use this camchain for the IMU stage (container path, e.g. `/input/camchain.yaml`) | |
| `--imu-models M` | `calibrated`, `scale-misalignment`, `scale-misalignment-size-effect` | `calibrated` |
| `--mi-tol F` | Kalibr mutual-information tolerance; `-1` forces all views | Kalibr default 0.2 |
| `--approx-sync S` | multi-camera time tolerance [s] | 0.02 |
| `--keep-bag` | keep `calib.bag` | delete on success |
| `--dry-run` | inspect, print the plan, exit | |
| `--verbose` | Kalibr verbose output | |

Target resolution order: `--target` > `<folder>/target.yaml` > `april_6x10_40mm.yaml` at the
repository root (mounted automatically as `/defaults/target.yaml`).

Mode is inferred: 1 camera = mono; N cameras = joint (intrinsics + extrinsics); `imu0.csv`
present = joint followed by camera-IMU. Mono is simply joint with N=1; there is no separate code
path.

Examples:

```bash
./camcalib ~/captures/flir_rig                            # stereo, results in ~/captures/flir_rig/calib/
./camcalib ~/captures/single_cam --step 2                 # mono
./camcalib ~/captures/quad_rig --models pinhole-equi      # 4 fisheye cameras, joint
./camcalib ~/captures/quad_rig --independent              # 4 independent mono calibrations
./camcalib ~/captures/rig_imu                             # stereo + IMU (needs imu0.csv/imu0.yaml)
./camcalib ~/captures/flat_folder --out /tmp/flat         # images directly in the folder = cam0
./camcalib inspect ~/captures/flir_rig
```

Environment variables:

| Variable | Meaning |
|---|---|
| `CAMCALIB_IMAGE` | image to run (default `swarmbotix/sb_kalibr:latest`, pulled on first use) |
| `CAMCALIB_DEV=1` | mount `forge/api` over the baked API; edit scripts without rebuilding |
| `CAMCALIB_CAPTURE_DIR` | where `camcalib capture` saves frames (default `./capture_out`) |
| `TZ` | timezone recorded in `manifest.json` (default: host timezone) |

Container mounts set up by `camcalib`: case at `/input` (read-only), output at
`/output`, default target at `/defaults/target.yaml`. The container runs with
the caller's uid/gid, so output files belong to the user.

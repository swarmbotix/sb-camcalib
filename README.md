# sb_kalibr

Camera calibration in a box. [Kalibr](https://github.com/ethz-asl/kalibr) runs inside a Docker
image; the host script `camcalib` points it at a folder of images and writes the results next
to them. Three cases are supported: one camera, N synchronised cameras (stereo is N=2), and
cameras plus an IMU.

```bash
git clone https://github.com/ubicoders/sb_kalibr.git
cd sb_kalibr
./camcalib version          # pulls swarmbotix/sb_kalibr:latest on first use (~7 GB)
```

Requirements: Docker, Linux. Full reference: [docs/](docs/) (case format, commands, capture and targets, IMU, development).

With the swarmbotix CLI (`sb` 0.2.1 or newer) there is no clone step: the repo is an sb app
package (`sb.app.yml` at the root), so

```bash
sb install https://github.com/ubicoders/sb_kalibr.git
sb camcalib ~/data/mycam          # same arguments as ./camcalib, run from anywhere
sb app update camcalib            # pull a newer version later
```

Try it on the bundled sample (147 frames of one 1280x800 camera in `examples/`):

```bash
./camcalib examples
cat examples/calib/cam0/camchain.yaml
```

To look at what the detector sees on one frame, without Docker:

```bash
pip install opencv-contrib-python numpy
python3 examples/detect/detect_aprilgrid.py examples/0034.png
```

## Usage

```bash
./camcalib [CASE] [options]
```

`CASE` is the input folder (defaults to the current directory). The number of `cam*/`
subfolders sets the camera count; an `imu0.csv` file enables the IMU stage. Results go to
`CASE/calib/` unless `--out` is given.

| Option | Meaning | Default |
|---|---|---|
| `--out DIR` | output folder | `CASE/calib` |
| `--models M [M ...]` | camera model, one for all or one per camera | `pinhole-radtan` |
| `--independent` | N cameras: calibrate each alone, no extrinsics | off |
| `--step N` | keep every N-th frame | 1 |
| `--max-frames N` | cap frames per camera after `--step` | none |
| `--focal PX` | manual focal-length init (use if the result is NaN) | auto |
| `--camchain PATH` | skip the camera stage, use this camchain for the IMU stage | |
| `--keep-bag` | keep the intermediate `calib.bag` | delete |
| `--dry-run` | show the plan, do not run | |

Other commands: `./camcalib inspect CASE` (check the folder), `./camcalib calibrate --help`
(all options), `./camcalib shell` (bash inside the container).

---

## 1. Single camera

Input:

```
mycam/
  cam0/
    0000.png
    0001.png
    ...
```

Run:

```bash
./camcalib ~/data/mycam
```

Output:

```
mycam/calib/
  cam0/camchain.yaml        intrinsics + distortion
  cam0/results-cam.txt
  cam0/report-cam.pdf
  manifest.json  log.txt
```

---

## 2. Stereo or N cameras

Input (same file names in every camera folder = same capture instant):

```
myrig/
  cam0/
    0000.png
    0001.png
    ...
  cam1/
    0000.png
    0001.png
    ...
  cam2/ ...                 optional, up to camN
```

Run:

```bash
./camcalib ~/data/myrig
```

Output:

```
myrig/calib/
  rig/camchain.yaml         all intrinsics + extrinsics T_cn_cnm1 between cameras
  rig/results-cam.txt
  rig/report-cam.pdf
  cam0/camchain.yaml        per-camera slices
  cam1/camchain.yaml
  manifest.json  log.txt
```

---

## 3. Cameras + IMU

Input (image names are nanosecond timestamps on the same clock as the IMU):

```
myrig_imu/
  cam0/
    1700000000033000000.png
    1700000000066000000.png
    ...
  cam1/ ...                 optional, same names as cam0
  imu0.csv                  timestamp_ns,wx,wy,wz,ax,ay,az   (rad/s, m/s^2)
  imu0.yaml                 IMU noise parameters, template in examples/imu0.yaml
```

Run:

```bash
./camcalib ~/data/myrig_imu
```

Output:

```
myrig_imu/calib/
  rig/camchain.yaml              camera intrinsics + extrinsics
  cam0/ cam1/                    per-camera slices
  imu/camchain-imucam.yaml       T_cam_imu per camera + timeshift_cam_imu
  imu/results-imucam.txt
  imu/report-imucam.pdf
  manifest.json  log.txt
```

---

## 4. Expanded example: single camera, other lens models

Same input as case 1. The default model is `pinhole-radtan` (normal lens, up to ~120 deg
FOV). Pick another model with `--models`:

| Lens | Command |
|---|---|
| normal | `./camcalib ~/data/mycam` |
| fisheye (Kannala-Brandt) | `./camcalib ~/data/mycam --models pinhole-equi` |
| fisheye (double sphere) | `./camcalib ~/data/mycam --models ds-none` |
| fisheye (extended unified) | `./camcalib ~/data/mycam --models eucm-none` |
| omnidirectional | `./camcalib ~/data/mycam --models omni-radtan` |

Useful extras:

```bash
./camcalib ~/data/mycam --step 2 --max-frames 60     # thin a long capture
./camcalib ~/data/mycam --focal 700                  # manual focal init if the result is NaN
./camcalib ~/data/mycam --out /tmp/mycam_result      # write results elsewhere
./camcalib inspect ~/data/mycam                      # check the folder, no calibration
```

Fixed defaults for one case can go in `mycam/calib.yaml` instead of the command line:

```yaml
models: [pinhole-equi]
step: 2
max_frames: 60
```

Output is the same as case 1; `cam0/camchain.yaml` reports the chosen `camera_model` and
`distortion_model`. For a rig, pass one model per camera in `cam0..camN` order, for example
`--models pinhole-equi pinhole-radtan`.

---

## Credits and license

This project is a packaging layer around **Kalibr**, developed by the Autonomous Systems Lab
(ETH Zurich) and Skybotix AG: <https://github.com/ethz-asl/kalibr>. All calibration algorithms
are Kalibr's work. Kalibr is distributed under the BSD license reproduced in
[LICENSE-kalibr](LICENSE-kalibr). *This product includes software developed by the Autonomous
Systems Lab and Skybotix AG.*

For academic use, cite:

- P. Furgale, J. Rehder, R. Siegwart (2013). Unified Temporal and Spatial Calibration for
  Multi-Sensor Systems. IROS 2013.
- J. Rehder, J. Nikolic, T. Schneider, T. Hinzmann, R. Siegwart (2016). Extending kalibr:
  Calibrating the extrinsics of multiple IMUs and of individual axes. ICRA 2016.

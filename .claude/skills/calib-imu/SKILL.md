---
name: calib-imu
description: Calibrate camera-to-IMU extrinsics T_cam_imu and time offset with ./camcalib (Kalibr in Docker) from ns-timestamped images plus imu0.csv / imu0.yaml. Use when the user mentions IMU, gyro, accelerometer, VIO, camera-IMU spatial or temporal calibration, T_cam_imu, or has an imu0.csv in the case folder.
---

# Camera + IMU calibration

Runs the camera stage (or reuses a camchain), then `kalibr_calibrate_imu_camera`.
Estimates per camera `T_cam_imu`, `timeshift_cam_imu`, gravity direction and IMU biases;
optionally IMU scale and misalignment. Camera intrinsics and inter-camera extrinsics are
fixed inputs.

Status note: the IMU stage follows the Kalibr command line but has not yet been verified end
to end on a real dataset in this repository. Treat the first run as a validation run and read
`log.txt` closely.

## 1. Check the case folder

```
<case>/
  cam0/<ns>.png ...      REQUIRED ns-timestamp names (>= 13 digits). Index names are refused.
  cam1/ ... camN/        optional, identical file names as cam0
  imu0.csv               required; presence switches the case to IMU mode
  imu0.yaml              required with imu0.csv
  camchain.yaml          optional; a previous rig/camchain.yaml to reuse (see step 3)
  target.yaml  calib.yaml   optional
```

Validate: `./camcalib inspect <case>`. Fix `imu0.csv present but imu0.yaml missing` and
any naming error before running.

## 2. IMU data format

`imu0.csv`, header row required, one sample per row (template `examples/imu0.csv`):

```
timestamp_ns,wx,wy,wz,ax,ay,az
1700000000000000000,0.0012,-0.0004,0.0007,0.021,-0.013,-9.806
```

- `timestamp_ns`: integer nanoseconds, same clock as the image names. A constant offset is
  estimated by Kalibr; drift between clocks is not.
- `wx wy wz`: raw gyroscope, rad/s.
- `ax ay az`: raw accelerometer specific force, m/s^2, gravity included. No gravity
  compensation, no filtering, no orientation fusion. Static check: norm of (ax, ay, az) ~ 9.81.
- Gyro and accel in the same right-handed body frame. Any mounting orientation is fine
  (aerospace FRD included); a left-handed frame cannot be recovered.
- Rate 100 to 1000 Hz, monotonic timestamps.

`imu0.yaml` (template `examples/imu0.yaml`):

```yaml
rostopic: /imu0
update_rate: 200.0                     # Hz, must match the csv rate
accelerometer_noise_density: 0.01      # m/s^2/sqrt(Hz)
accelerometer_random_walk:   0.0002    # m/s^3/sqrt(Hz)
gyroscope_noise_density:     0.0005    # rad/s/sqrt(Hz)
gyroscope_random_walk:       4.0e-06   # rad/s^2/sqrt(Hz)
```

Take noise values from the datasheet or an Allan-variance analysis and inflate them 5 to
10x; Kalibr prefers conservative noise. Keep `rostopic: /imu0`.

Quick sanity check on the csv before a long calibration (rate, timestamp gaps, accel norm):

```bash
python3 - <case>/imu0.csv <<'PY'
import csv, math, sys
rows = list(csv.DictReader(open(sys.argv[1])))
t = [int(r['timestamp_ns']) for r in rows]
dt = [(b - a) / 1e9 for a, b in zip(t, t[1:])]
norm = [math.sqrt(sum(float(r[k]) ** 2 for k in ('ax', 'ay', 'az'))) for r in rows]
print('samples', len(rows), 'rate_hz', 1 / (sum(dt) / len(dt)), 'min_dt', min(dt), 'max_dt', max(dt))
print('accel_norm mean', sum(norm) / len(norm), '(expect ~9.81)')
PY
```

A mean accel norm near 1.0 means g units; near 0 means gravity was compensated. Gyro values
above ~10 while the sensor moves gently usually mean deg/s. All three must be fixed in the
csv before calibrating.

Motion requirements: 60 to 120 s, target static, sensor moving, all three rotation axes and
all three translation axes excited, target in view most of the time. Static or
rotation-only data cannot calibrate the extrinsics.

## 3. Choose the workflow

**A. One dataset.** Images are sharp enough for intrinsics and the motion is rich enough for
the IMU. Run the case directly; the camera stage runs first, then the IMU stage.

```bash
./camcalib <case>
```

**B. Two datasets (recommended).** Calibrate cameras on a slow, sharp capture (case A), then
run the fast-motion capture (case B) with case A's camchain. The container only sees the
case and output mounts, so the camchain must be copied into case B and referenced by its
container path:

```bash
./camcalib <A>                                            # camera stage only, no imu0.csv in A
cp <A>/calib/rig/camchain.yaml <B>/camchain.yaml          # for N == 1 use <A>/calib/cam0/camchain.yaml
./camcalib <B> --camchain /data_in/case/camchain.yaml     # skips the camera stage in B
```

Options specific to this stage:

```bash
--imu-models calibrated                         # default: fixed scale, no misalignment
--imu-models scale-misalignment                 # also estimate scale and axis misalignment
--imu-models scale-misalignment-size-effect     # plus accelerometer size effect
--models pinhole-equi                           # camera model, camera stage only
--step N --max-frames N                         # thin camera frames; IMU samples are never thinned
--keep-bag                                      # keep calib.bag for manual Kalibr reruns
```

## 4. Read the result

```
<case>/calib/
  cam<k>/ rig/              camera stage outputs (absent when --camchain was used)
  imu/
    camchain-imucam.yaml    rig camchain + per camera: T_cam_imu (4x4), timeshift_cam_imu (s)
    imu.yaml                IMU noise yaml as used, plus estimated model parameters
    results-imucam.txt      reprojection, gyro and accel error statistics, gravity, biases
    report-imucam.pdf       plots: errors over time, bias estimates, spline fit
    poses-imucam-imu0.csv   estimated IMU trajectory
  case.json  manifest.json  log.txt
```

`T_cam_imu` maps points from the IMU frame into the camera frame (X right, Y down, Z
forward). `timeshift_cam_imu` is in seconds; the image timestamp plus this value aligns the
camera clock to the IMU clock.

Report to the user: `T_cam_imu` per camera (rotation in a readable form, translation in
metres), `timeshift_cam_imu`, reprojection error, gyro and accel error means from
`results-imucam.txt`, and whether the biases and gravity look plausible. Accel errors of a
few 0.01 m/s^2 and gyro errors of a few 0.001 rad/s are typical for consumer MEMS.

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| inspect refuses the case | index-named images; recapture with real ns timestamps |
| `imu0.yaml missing` | copy `examples/imu0.yaml` into the case and set the values |
| IMU stage diverges, huge errors | wrong units (deg/s, g), gravity-compensated accel, filtered data, or timestamps on a different clock |
| large or drifting time shift | timestamps not monotonic, or camera and IMU clocks drift; re-timestamp at capture |
| translation poorly determined | not enough translation excitation; recapture with faster accelerations |
| noise too tight, optimisation stalls | inflate the noise densities in `imu0.yaml` |
| run failed | `<case>/calib/log.txt`; `calib.bag` is kept on failure for manual reruns with `./camcalib shell <case>` |

# Camera + IMU calibration reference

Background for the `calib-imu` skill: what Kalibr estimates, data requirements, noise yaml, recommended two-dataset workflow.

What it estimates: `T_cam_imu` (6-DOF extrinsics per camera), `timeshift_cam_imu` (seconds),
gravity direction, gyro/accel biases; optionally IMU scale/misalignment. Camera intrinsics and
inter-camera extrinsics are fixed inputs from the camera stage. Kalibr fits a continuous-time
B-spline to the camera trajectory and compares its derivatives with the raw IMU readings, so no
attitude filter is involved and none should be applied to the data.

Data requirements:

- Images named with real capture timestamps in nanoseconds. Same clock as the IMU, or a
  constant offset (Kalibr estimates a constant offset, not drift).
- `imu0.csv`: raw gyro (rad/s) and raw accelerometer specific force (m/s^2), SI units, same
  right-handed body frame for both, 100 to 1000 Hz. No gravity compensation, no filtering, no
  orientation fusion. Static check: accel norm ~ 9.81.
- Motion: 60 to 120 s exciting all three rotation axes and three translation axes, target
  static, cameras moving. Static data cannot calibrate extrinsics.
- Any IMU mounting orientation is fine (e.g. aerospace FRD: X forward, Y right, Z down).
  Kalibr solves the rotation; pre-aligning axes to the camera frame is not required.
  Left-handed frames are not recoverable.

`imu0.yaml` (template in `examples/imu0.yaml`):

```yaml
rostopic: /imu0
update_rate: 200.0
accelerometer_noise_density: 0.01      # m/s^2/sqrt(Hz)   (datasheet or Allan variance; inflate 5-10x)
accelerometer_random_walk:   0.0002    # m/s^3/sqrt(Hz)
gyroscope_noise_density:     0.0005    # rad/s/sqrt(Hz)
gyroscope_random_walk:       4.0e-06   # rad/s^2/sqrt(Hz)
```

Recommended workflow: calibrate cameras from a slow, sharp dataset (folder A), then run the IMU
dataset (folder B, fast motion) with `--camchain` pointing at folder A's `rig/camchain.yaml`.
Because the container only sees the input and output mounts, copy folder A's camchain into folder B
(`cp A/calib/rig/camchain.yaml B/camchain.yaml`) and pass `--camchain /input/camchain.yaml`.

Status: the IMU stage is wired per the Kalibr command line but has not yet been exercised end
to end with a real dataset.

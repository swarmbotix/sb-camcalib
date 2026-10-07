# Case folder and output layout

Exact rules for what `camcalib` reads from a case folder and what it writes back. Enforced by `forge/api/inspect_case.py` and arranged by `forge/api/split_camchain.py`.

## Input: case folder

A *case* is one folder. Camera count is the number of `cam*/` subfolders. IMU presence is the
existence of `imu0.csv`.

```
<case>/
  cam0/                 required
    0000.png ...        frame index naming, OR <nanoseconds>.png (>= 13 digits)
  cam1/ ... camN/       optional. Same frame count AND identical file names as cam0.
                        Identical name = same capture instant (hardware or software sync).
  imu0.csv              optional. Columns: timestamp_ns, wx, wy, wz, ax, ay, az (header row required)
  imu0.yaml             required with imu0.csv. Kalibr IMU noise yaml (see docs/imu.md, examples/imu0.yaml)
  target.yaml           optional. Overrides the default target.
  calib.yaml            optional. Per-case defaults (see examples/calib.yaml), e.g.
                          models: [pinhole-equi]
                          step: 2
                          max_frames: 60
                          focal: 700
```

Compatibility: a case with images directly in `<case>/` (no `cam0/`) is treated as a single
camera.

Accepted image extensions: png, jpg, jpeg, bmp. Images are read as 8-bit grayscale.

Rules enforced by `inspect_case.py` (run `camcalib inspect <case>` to see them):

- `cam0..camN` must be contiguous.
- Frame counts and file names must match across cameras.
- File stems must be integers (index or ns timestamp); all cameras must use the same scheme.
- IMU calibration requires ns-timestamp naming (synthetic timestamps cannot align with IMU data).

Index naming is turned into synthetic timestamps at 0.1 s per frame, identical across cameras,
which is how Kalibr pairs synchronised frames.

## Output: calib folder

Default: `<case>/calib/`. Override with `--out DIR`.

```
<case>/calib/
  cam0/
    camchain.yaml         this camera: intrinsics (+ T_cn_cnm1 to the previous camera for k > 0)
    results-cam.txt       (N == 1 only; for N >= 2 the full report is under rig/)
    report-cam.pdf
  cam1/ ...
  rig/                    N >= 2 only
    camchain.yaml         Kalibr multi-camera camchain: all intrinsics + T_cn_cnm1 extrinsics
    results-cam.txt
    report-cam.pdf
  imu/                    with imu0.csv only
    camchain-imucam.yaml  rig camchain + T_cam_imu per camera + timeshift_cam_imu
    imu.yaml
    results-imucam.txt
    report-imucam.pdf
  case.json               inspect_case output
  manifest.json           mode, N, models, step, focal init, target, kalibr commit, date
  log.txt                 full Kalibr log
  calib.bag               only with --keep-bag (or if the run failed)
```

With `--independent`, each `cam<k>/` holds a full standalone calibration and `rig/` is absent.

`T_cn_cnm1` maps points from camera n-1 into camera n. For camera 2 in camera 0 coordinates:
`T_c2_c0 = T_c2_c1 * T_c1_c0`.

`T_cam_imu` maps points from the IMU frame into the camera frame.

Camera frame convention (Kalibr, standard computer vision): X right, Y down, Z forward along
the optical axis.

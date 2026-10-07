# Live capture, camera models and targets

## Live capture tools

```bash
./camcalib capture kalibr_april_detect /dev/video0   # Kalibr AprilGrid detector with corner overlay;
                                                     # SPACE saves only when >= 11 tags are seen
./camcalib capture capture /dev/video0               # raw capture, SPACE saves
./camcalib capture april_detector /dev/video0        # generic AprilTag/ArUco preview (not for AprilGrid)
./camcalib capture capture_undist /dev/video0        # undistorted preview (intrinsics hardcoded in script)
```

Frames are saved as `<ns>.png` under `$CAMCALIB_CAPTURE_DIR/cam0/`, which is directly usable
as a case. Requires `xhost +local:` on the host. V4L2 devices only; the scripts default to
1280x720 MJPG.

Generic AprilTag detectors cannot see Kalibr's AprilGrid because the tags are embedded in a
checkerboard; only the Kalibr detector (`kalibr_april_detect`) works for that target.

## Camera models and targets

Models (Kalibr names): `pinhole-radtan` (default, up to ~120 deg FOV), `pinhole-equi`
(fisheye, Kannala-Brandt), `pinhole-fov`, `omni-radtan`, `omni-none`, `ds-none` (double
sphere), `eucm-none`. Fisheye lenses need `pinhole-equi`, `ds-none` or `eucm-none`.

Targets: Kalibr supports `aprilgrid`, `checkerboard`, `circlegrid`. AprilGrid is strongly
preferred (partial views allowed, unique corner IDs). Charuco is not a Kalibr target; the Charuco
PDFs in `targets/` are for other tools. Printable for the default grid:
`targets/calib.io_kalibr_600x400_6x10_40.pdf`. Measure the printed tag size and gap and update
`tagSize` / `tagSpacing` in the yaml if they differ (`tagSpacing` is gap divided by tag size).

Data quality beats quantity: 30 to 60 frames per camera with full image coverage (including
corners), tilt of 30 to 45 degrees about both axes, several distances, and some roll. For a
rig, also collect frames seen by only one camera (to cover its outer edges) and 20 to 30 frames
seen by all cameras at different depths (for the extrinsics). Kalibr accepts views seen by any
subset of cameras. Kalibr additionally discards redundant views (mutual information) and
outlier corners (reprojection statistics) on its own.

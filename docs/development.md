# Development, troubleshooting, credits

## Development workflow

- Edit `forge/api/*` and test without rebuilding: `CAMCALIB_DEV=1 ./camcalib <case>` (overlays
  the local API on the published image).
- Rebuild after changing the dockerfile or the Kalibr patch: `./camcalib build`. The Kalibr
  layer is cached; API-only rebuilds take seconds. Publish with `./camcalib build --push`
  (requires `docker login` as `swarmbotix`).
- Interactive container with the live API: `docker compose -f forge/docker-compose.yml run --rm dev`.
- Kalibr lives at `/opt/kalibr` inside the image; Python tools at
  `/opt/kalibr/src/kalibr/aslam_offline_calibration/kalibr/python` (`$KALIBR_PY`).
- Pin changes: `KALIBR_COMMIT` build arg in `forge/dockerfile`.
- Build context is the repository root; `.dockerignore` restricts it to `forge/`.
- Verified on 2026-10-07 against a previous host-built Kalibr pipeline: a 1280x800 mono case
  matched intrinsics within 0.2 px, and a 1440x1080 FLIR stereo pair matched the baseline
  within 0.05 mm with identical reprojection error.

## Known failure modes

| Symptom | Cause | Fix |
|---|---|---|
| NaN intrinsics / `nan` in camchain | focal-length auto-init failed (too little tilt diversity, mixed resolutions) | `--focal <px>`; roughly `width / (2 tan(hfov/2))` |
| `frame count mismatch` / `file names differ` | cameras not synchronised by file name | fix the capture; names must be identical across `cam*/` |
| Garbage corners, NaN | mixed image resolutions in one camera folder | remove frames of the wrong size |
| `DLT needs >= 6 points` | view with one tag only | handled by the patch (view skipped) |
| Very few views used, poor error | `--mi-tol` discarding near-duplicate frames | collect more diverse views; `--mi-tol -1` to force all |
| IMU stage refuses | index-named images | capture with real ns timestamps |
| Output files owned by root | running `docker run` without `--user` | always go through `./camcalib` |
| PDF generation error about matplotlib config | non-writable `$HOME` | image sets `MPLCONFIGDIR=/tmp/mpl`; rebuild if using an old image |
| `Permission denied` on X11 | host did not allow container X clients | `xhost +local:` |
| `image swarmbotix/sb_kalibr:latest could not be pulled` | no network or Docker Hub access | retry, `docker login`, or build locally with `./camcalib build` |

## Credits and license

Kalibr: <https://github.com/ethz-asl/kalibr>, Copyright (c) 2014 Paul Furgale, Jérôme Maye,
Jörn Rehder (Autonomous Systems Lab, ETH Zurich) and Thomas Schneider (Skybotix AG). BSD
license, reproduced verbatim in `LICENSE-kalibr`. The image redistributes Kalibr in binary form
with source at `/opt/kalibr/src/kalibr` (including its `LICENSE`), so the notice must stay in
this repository's documentation and in any derived distribution. Required acknowledgement:
*This product includes software developed by the Autonomous Systems Lab and Skybotix AG.*

This repository adds only packaging (dockerfile), a thin container API (`forge/api`), a host
launcher (`camcalib`) and documentation. The single upstream modification is
`forge/patches/kalibr-fixes.patch` (three `try/except` guards around PnP calls). Do not present
this project as endorsed by ETH Zurich or Skybotix AG.

Citations for academic use are listed in `README.md` under "Credits and license".

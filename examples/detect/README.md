# detect: draw Kalibr AprilGrid corners on one image

`detect_aprilgrid.py` reads one image, finds the Kalibr AprilGrid tags and shows the result in
a window: every corner as a dot, each tag outlined, its ID at the centre. Any key closes it.
It runs on the host. No Docker, no Kalibr; only OpenCV with the contrib modules.

```bash
pip install opencv-contrib-python numpy
python3 examples/detect/detect_aprilgrid.py examples/0034.png
```

Options: `--target PATH` (Kalibr AprilGrid yaml, default `april_6x10_40mm.yaml` at the
repository root), `--min-tags N`, `--scale F` (upscale factor for decoding, default 3),
`--out PATH` (also save the annotated image).

Example output on `examples/0034.png`:

```
image   : examples/0034.png  (1280x800)
target  : .../april_6x10_40mm.yaml  rows=6 cols=10
tags    : 60 / 60   corners: 240
valid   : True  (min tags 11)
```

## How it works

Plain AprilTag or ArUco detectors fail on this target because the Kalibr AprilGrid uses
tag36h11 codes with a 2-bit black border (generic detectors assume 1 bit) and the tags sit
inside a checkerboard. OpenCV's ArUco detector accepts the wider border through
`markerBorderBits = 2`, and its `DICT_APRILTAG_36h11` dictionary gives the same tag IDs as
Kalibr. The image is upscaled 3x before decoding because the bit cells are only a few pixels
wide at normal distances; corners are mapped back and refined to sub-pixel on the original
image.

Measured against Kalibr's own detector on the 147 sample frames in `examples/`: about
96 percent of the tags Kalibr finds, corner positions within a few tenths of a pixel. Tags at
the image edge or at steep angles are the ones that may be missed. Calibration itself always
uses Kalibr's detector inside the container; this script is for checking captures.

Corner numbering follows Kalibr: a `2*tagRows x 2*tagCols` grid of points, row-major, tag 0
at the bottom-left of the target.

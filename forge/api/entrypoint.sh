#!/usr/bin/env bash
#
# Container entrypoint. Sources ROS + Kalibr, then dispatches a subcommand.
#
#   calibrate [opts]       run a calibration on /input -> /output
#   capture <script> [..]  run one of the live capture/detector tools
#   shell                  interactive bash with ROS + Kalibr sourced
#   version                print image / Kalibr version info
#
# The host-side `camcalib` script is the intended caller.
set -uo pipefail

# ROS setup scripts are not nounset-clean.
set +u
source /opt/ros/noetic/setup.bash
source /opt/kalibr/devel/setup.bash
set -u

export KALIBR_PY=/opt/kalibr/src/kalibr/aslam_offline_calibration/kalibr/python
export PYTHONPATH="/opt/kalibr/devel/lib/python3/dist-packages:${KALIBR_PY}:${PYTHONPATH:-}"

cmd="${1:-calibrate}"
[ $# -gt 0 ] && shift

case "$cmd" in
  calibrate)
    exec bash /opt/camcalib/calibrate.sh "$@"
    ;;
  capture)
    script="${1:-}"; [ $# -gt 0 ] && shift
    if [ -z "$script" ]; then
      echo "usage: capture <script> [args...]"; echo "available:"
      ls -1 /opt/camcalib/capture/*.py | xargs -n1 basename | sed 's/^/  /'
      exit 2
    fi
    [ "${script%.py}" = "$script" ] && script="$script.py"
    [ -f "/opt/camcalib/capture/$script" ] || { echo "no such capture script: $script"; exit 2; }
    cd /opt/camcalib/capture
    exec python3 "/opt/camcalib/capture/$script" "$@"
    ;;
  shell|bash)
    cd /output 2>/dev/null || cd /
    exec bash "$@"
    ;;
  version)
    echo "camcalib image"
    echo "  kalibr commit : ${KALIBR_COMMIT:-unknown}"
    echo "  ros           : ${ROS_DISTRO}"
    python3 -c 'import numpy, cv2; print("  numpy         :", numpy.__version__); print("  cv2           :", cv2.__version__)'
    echo "  Kalibr        : https://github.com/ethz-asl/kalibr (BSD license, see /opt/kalibr/src/kalibr/LICENSE)"
    echo "  This product includes software developed by the Autonomous Systems Lab and Skybotix AG."
    ;;
  -h|--help|help)
    sed -n '3,11p' "$0"
    ;;
  *)
    echo "unknown subcommand: $cmd  (calibrate | capture | shell | version)" >&2
    exit 2
    ;;
esac

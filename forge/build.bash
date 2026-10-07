#!/usr/bin/env bash
#
# Build (and optionally push) the camcalib image.
#
# Usage:
#   bash forge/build.bash [--tag TAG] [--push] [--no-cache]
#
# The image is tagged swarmbotix/sb_kalibr:<TAG> and swarmbotix/sb_kalibr:latest. TAG defaults to the
# current date (YYYYMMDD) or, inside a git checkout, `git describe`.
# Set CAMCALIB_IMAGE_REPO to tag for another registry (e.g. ghcr.io/org/sb_kalibr).
set -euo pipefail

HERE="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
ROOT="$(dirname "$HERE")"
REPO_NAME="${CAMCALIB_IMAGE_REPO:-swarmbotix/sb_kalibr}"

TAG=""
PUSH=0
EXTRA=()
while [ $# -gt 0 ]; do
  case "$1" in
    --tag)      TAG="$2"; shift 2 ;;
    --push)     PUSH=1; shift ;;
    --no-cache) EXTRA+=("--no-cache"); shift ;;
    -h|--help)  sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$TAG" ]; then
  if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    TAG="$(git -C "$ROOT" describe --tags --always --dirty 2>/dev/null || date +%Y%m%d)"
  else
    TAG="$(date +%Y%m%d)"
  fi
fi

echo ">>> building ${REPO_NAME}:${TAG}  (context: $ROOT)"
docker build "${EXTRA[@]}" \
  -f "$HERE/dockerfile" \
  -t "${REPO_NAME}:${TAG}" \
  -t "${REPO_NAME}:latest" \
  "$ROOT"

if [ "$PUSH" -eq 1 ]; then
  docker push "${REPO_NAME}:${TAG}"
  docker push "${REPO_NAME}:latest"
fi

echo ">>> done: ${REPO_NAME}:${TAG}, ${REPO_NAME}:latest"

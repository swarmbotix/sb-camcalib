#!/usr/bin/env bash
#
# camcalib container worker: /input  ->  /output
#
# Stages:  inspect -> stage -> bag -> cameras -> [imu] -> arrange outputs
#
# Options (all optional):
#   --models M [M ...]   Kalibr camera model per camera, or one for all
#                        (pinhole-radtan | pinhole-equi | pinhole-fov | omni-radtan |
#                         omni-none | ds-none | eucm-none)          default: pinhole-radtan
#   --target PATH        target yaml (container path). Resolution order when omitted:
#                        <folder>/target.yaml  >  /defaults/target.yaml
#   --step N             keep every N-th frame                      default: 1
#   --max-frames N       cap frames per camera after --step (evenly spread)
#   --focal PX           manual focal-length init (use when auto init yields NaN)
#   --independent        N cameras: calibrate each alone (no extrinsics)
#   --camchain PATH      skip camera stage; use this camchain for the IMU stage
#   --imu-models M       Kalibr IMU model: calibrated | scale-misalignment |
#                        scale-misalignment-size-effect              default: calibrated
#   --mi-tol F           Kalibr mutual-information tolerance (-1 = use all views)
#   --approx-sync S      Kalibr multi-camera time tolerance [s]      default: 0.02
#   --keep-bag           keep calib.bag in the output (default: delete after success)
#   --no-report          do not generate PDF reports
#   --dry-run            inspect and print the plan, then exit
#   --verbose            pass --verbose to Kalibr
set -uo pipefail

IN=/input
OUT=/output
STAGE=/tmp/stage
KALIBR_PY=${KALIBR_PY:-/opt/kalibr/src/kalibr/aslam_offline_calibration/kalibr/python}
BAGTAG=calib

MODELS=()
TARGET=""
STEP=1
MAX_FRAMES=0
FOCAL=""
INDEPENDENT=0
CAMCHAIN=""
IMU_MODELS="calibrated"
MI_TOL=""
APPROX_SYNC=""
KEEP_BAG=0
NO_REPORT=0
DRY=0
VERBOSE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --models)      shift; while [ $# -gt 0 ] && [[ "$1" != --* ]]; do MODELS+=("$1"); shift; done ;;
    --target)      TARGET="$2"; shift 2 ;;
    --step)        STEP="$2"; shift 2 ;;
    --max-frames)  MAX_FRAMES="$2"; shift 2 ;;
    --focal)       FOCAL="$2"; shift 2 ;;
    --independent) INDEPENDENT=1; shift ;;
    --camchain)    CAMCHAIN="$2"; shift 2 ;;
    --imu-models)  IMU_MODELS="$2"; shift 2 ;;
    --mi-tol)      MI_TOL="$2"; shift 2 ;;
    --approx-sync) APPROX_SYNC="$2"; shift 2 ;;
    --keep-bag)    KEEP_BAG=1; shift ;;
    --no-report)   NO_REPORT=1; shift ;;
    --dry-run)     DRY=1; shift ;;
    --verbose)     VERBOSE="--verbose"; shift ;;
    -h|--help)     sed -n '3,27p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

die() { echo "camcalib: $*" >&2; exit 1; }

# ---------------------------------------------------------------- inspect
[ -d "$IN" ] || die "no input mounted at $IN"
mkdir -p "$OUT" || die "cannot write $OUT"
INFO_JSON=$(python3 /opt/camcalib/inspect_input.py "$IN") || true
echo "$INFO_JSON" > "$OUT/input.json"

jq_py() { python3 -c "import json,sys; d=json.load(open('$OUT/input.json')); print($1)"; }
NCAMS=$(jq_py "len(d['cams'])")
MODE=$(jq_py "d['mode'] or ''")
FLAT=$(jq_py "int(d['flat'])")
ERRORS=$(jq_py "'\n'.join(d['errors'])")
WARNINGS=$(jq_py "'\n'.join(d['warnings'])")
IMU_CSV=$(jq_py "d['imu_csv'] or ''")
IMU_YAML=$(jq_py "d['imu_yaml'] or ''")
CASE_TARGET=$(jq_py "d['target_yaml'] or ''")
NAMING=$(jq_py "d['cams'][0]['naming'] if d['cams'] else ''")

[ -n "$WARNINGS" ] && echo "warnings:" && echo "$WARNINGS" | sed 's/^/  /'
[ -n "$ERRORS" ] && { echo "errors:"; echo "$ERRORS" | sed 's/^/  /'; exit 1; }

# per-folder defaults from calib.yaml (only keys not given on the command line)
CALIB_YAML="$IN/calib.yaml"
if [ -f "$CALIB_YAML" ]; then
  cy() { python3 -c "import yaml,sys; d=yaml.safe_load(open('$CALIB_YAML')) or {}; v=d.get('$1'); print(' '.join(map(str,v)) if isinstance(v,list) else ('' if v is None else v))"; }
  [ ${#MODELS[@]} -eq 0 ] && read -r -a MODELS <<< "$(cy models)"
  [ "$STEP" = 1 ]          && { v=$(cy step);        [ -n "$v" ] && STEP=$v; }
  [ "$MAX_FRAMES" = 0 ]    && { v=$(cy max_frames);  [ -n "$v" ] && MAX_FRAMES=$v; }
  [ -z "$FOCAL" ]          && FOCAL=$(cy focal)
  [ -z "$MI_TOL" ]         && MI_TOL=$(cy mi_tol)
  [ -z "$APPROX_SYNC" ]    && APPROX_SYNC=$(cy approx_sync)
  [ "$IMU_MODELS" = calibrated ] && { v=$(cy imu_models); [ -n "$v" ] && IMU_MODELS=$v; }
fi

# target resolution
if [ -z "$TARGET" ]; then
  if [ -n "$CASE_TARGET" ]; then TARGET="$CASE_TARGET"
  elif [ -f /defaults/target.yaml ]; then TARGET=/defaults/target.yaml
  else die "no target yaml: pass --target, add <folder>/target.yaml, or mount a default"; fi
fi
[ -f "$TARGET" ] || die "target yaml not found: $TARGET"

# models: one per camera
if [ ${#MODELS[@]} -eq 0 ]; then MODELS=(pinhole-radtan); fi
if [ ${#MODELS[@]} -eq 1 ] && [ "$NCAMS" -gt 1 ]; then
  m="${MODELS[0]}"; MODELS=(); for ((i=0;i<NCAMS;i++)); do MODELS+=("$m"); done
fi
[ ${#MODELS[@]} -eq "$NCAMS" ] || die "--models: got ${#MODELS[@]} models for $NCAMS cameras"

TOPICS=(); for ((i=0;i<NCAMS;i++)); do TOPICS+=("/cam$i/image_raw"); done

REPORT_FLAG="--dont-show-report"
[ "$NO_REPORT" -eq 1 ] && REPORT_FLAG="--dont-show-report"   # Kalibr always writes the PDF; flag kept for parity

echo "================ camcalib ================"
echo "  input    : $IN  (cams=$NCAMS, naming=$NAMING, flat=$FLAT)"
echo "  mode     : $MODE$([ "$INDEPENDENT" -eq 1 ] && echo ' (independent)')"
echo "  out      : $OUT"
echo "  target   : $TARGET"
echo "  models   : ${MODELS[*]}"
echo "  step     : $STEP   max-frames: ${MAX_FRAMES:-0}   focal: ${FOCAL:-auto}"
[ -n "$IMU_CSV" ] && echo "  imu      : $IMU_CSV  ($IMU_YAML)  imu-models: $IMU_MODELS"
[ -n "$CAMCHAIN" ] && echo "  camchain : $CAMCHAIN (camera stage skipped)"
echo "=========================================="
[ "$DRY" -eq 1 ] && { echo "(dry run)"; exit 0; }

LOG="$OUT/log.txt"
exec > >(tee -a "$LOG") 2>&1
echo "# $(date -Is)  camcalib run"

# ---------------------------------------------------------------- stage + bag
FLAT_FLAG=""; [ "$FLAT" = 1 ] && FLAT_FLAG="--flat"
run_stage_and_bag() {   # $1 = stage dir, $2 = bag path, $3.. = extra stage_frames args
  local stage="$1" bag="$2"; shift 2
  python3 /opt/camcalib/stage_frames.py "$IN" "$stage" --step "$STEP" --max-frames "$MAX_FRAMES" $FLAT_FLAG "$@" || return 1
  rm -f "$bag"
  python3 "$KALIBR_PY/kalibr_bagcreater" --folder "$stage" --output-bag "$bag" || return 1
}

run_cameras() {         # $1 = bag, $2.. = topics ; uses MODELS_RUN
  local bag="$1"; shift
  local extra=()
  [ -n "$MI_TOL" ]      && extra+=(--mi-tol "$MI_TOL")
  [ -n "$APPROX_SYNC" ] && extra+=(--approx-sync "$APPROX_SYNC")
  [ -n "$VERBOSE" ]     && extra+=("$VERBOSE")
  cd "$(dirname "$bag")"
  if [ -n "$FOCAL" ]; then
    echo "  manual focal init: $FOCAL px"
    { yes "$FOCAL" || true; } | KALIBR_MANUAL_FOCAL_LENGTH_INIT=1 python3 "$KALIBR_PY/kalibr_calibrate_cameras" \
      --bag "$bag" --topics "$@" --models "${MODELS_RUN[@]}" --target "$TARGET" $REPORT_FLAG "${extra[@]}"
  else
    python3 "$KALIBR_PY/kalibr_calibrate_cameras" \
      --bag "$bag" --topics "$@" --models "${MODELS_RUN[@]}" --target "$TARGET" $REPORT_FLAG "${extra[@]}"
  fi
}

MANIFEST=$(python3 - "$MODE" "$INDEPENDENT" "$STEP" "$MAX_FRAMES" "$FOCAL" "$TARGET" "$IMU_MODELS" "${MODELS[@]}" <<'EOF'
import json, sys, datetime, os
mode, indep, step, maxf, focal, target, imu_models, *models = sys.argv[1:]
print(json.dumps({
  "mode": mode, "independent": bool(int(indep)), "models": models,
  "step": int(step), "max_frames": int(maxf), "focal_init": focal or None,
  "target": (os.environ.get("CAMCALIB_TARGET_NAME") if target == "/defaults/target.yaml" else None) or os.path.basename(target),
  "imu_models": imu_models,
  "kalibr_commit": os.environ.get("KALIBR_COMMIT"), "date": datetime.datetime.now().isoformat(timespec="seconds"),
}))
EOF
)

STATUS=0
if [ "$INDEPENDENT" -eq 1 ] && [ "$NCAMS" -gt 1 ]; then
  # ---- N independent mono calibrations: one bag + one Kalibr run per camera
  for ((i=0;i<NCAMS;i++)); do
    echo "---------------- cam$i (independent) ----------------"
    sub="$OUT/cam$i"; mkdir -p "$sub"
    stage="$STAGE/cam$i"; rm -rf "$stage"; mkdir -p "$stage"
    # stage the whole folder, then keep only this camera as cam0
    python3 /opt/camcalib/stage_frames.py "$IN" "$STAGE/all" --step "$STEP" --max-frames "$MAX_FRAMES" >/dev/null || { STATUS=1; continue; }
    mv "$STAGE/all/cam$i" "$stage/cam0"; rm -rf "$STAGE/all"
    bag="$sub/$BAGTAG.bag"; rm -f "$bag"
    python3 "$KALIBR_PY/kalibr_bagcreater" --folder "$stage" --output-bag "$bag" || { STATUS=1; continue; }
    MODELS_RUN=("${MODELS[$i]}")
    run_cameras "$bag" /cam0/image_raw || STATUS=1
    python3 /opt/camcalib/split_camchain.py "$sub" "$BAGTAG" --manifest "$MANIFEST" || STATUS=1
    # split_camchain nests a cam0/ under $sub for N==1; flatten it
    if [ -d "$sub/cam0" ]; then mv "$sub"/cam0/* "$sub"/ && rmdir "$sub/cam0"; fi
    rm -f "$sub/manifest.json"   # the run-level manifest.json below covers all cameras
    [ "$KEEP_BAG" -eq 1 ] || rm -f "$bag"
  done
  python3 - "$OUT" "$MANIFEST" "$NCAMS" <<'EOF'
import json, sys, os
out, man, n = sys.argv[1], json.loads(sys.argv[2]), int(sys.argv[3])
man["num_cameras"] = n
man["outputs"] = {f"cam{i}": f"cam{i}/camchain.yaml" for i in range(n) if os.path.isfile(os.path.join(out, f"cam{i}", "camchain.yaml"))}
json.dump(man, open(os.path.join(out, "manifest.json"), "w"), indent=2)
EOF
else
  # ---- single joint run (N == 1 is just joint with one camera)
  BAG="$OUT/$BAGTAG.bag"
  run_stage_and_bag "$STAGE/joint" "$BAG" || die "staging / bag creation failed"

  if [ -z "$CAMCHAIN" ]; then
    echo "---------------- cameras ($NCAMS) ----------------"
    MODELS_RUN=("${MODELS[@]}")
    run_cameras "$BAG" "${TOPICS[@]}" || STATUS=1
    CAMCHAIN="$OUT/$BAGTAG-camchain.yaml"
  else
    [ -f "$CAMCHAIN" ] || die "--camchain not found: $CAMCHAIN"
    cp "$CAMCHAIN" "$OUT/$BAGTAG-camchain.yaml"; CAMCHAIN="$OUT/$BAGTAG-camchain.yaml"
  fi

  if [ "$STATUS" -eq 0 ] && [ -n "$IMU_CSV" ]; then
    echo "---------------- imu + cameras ----------------"
    cd "$OUT"
    python3 "$KALIBR_PY/kalibr_calibrate_imu_camera" \
      --bag "$BAG" --cams "$CAMCHAIN" --imu "$IMU_YAML" --imu-models "$IMU_MODELS" \
      --target "$TARGET" --dont-show-report $VERBOSE || STATUS=1
  fi

  python3 /opt/camcalib/split_camchain.py "$OUT" "$BAGTAG" --manifest "$MANIFEST" || STATUS=$?
  [ "$KEEP_BAG" -eq 1 ] || [ "$STATUS" -ne 0 ] || rm -f "$BAG"
fi

rm -rf "$STAGE"
echo "=========================================="
if [ "$STATUS" -eq 0 ]; then
  echo "done: $OUT"; find "$OUT" -maxdepth 2 -name '*.yaml' | sort | sed 's/^/  /'
else
  echo "FAILED (status $STATUS). See $LOG"
fi
exit "$STATUS"

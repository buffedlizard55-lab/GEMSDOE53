#!/usr/bin/env bash
# Autonomous Competition Data Placement & SHA-256 Verification Script
# Restores competition rasters (training_features.tif, labels.tif, sample_submission.tif),
# external USGS/DOE layers (3DEP LiDAR scarps, GeoDAWN radiometrics, SGMC faults, GDR 1391),
# and historical scored rasters into data/ (or GEMS_DATA_DIR) with strict SHA-256 verification.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${GEMS_DATA_DIR:-$ROOT/data}"
mkdir -p "$TARGET_DIR" "$ROOT/evidence"

echo "[GEMSDOE52] Restoring and SHA-256 verifying competition data into: $TARGET_DIR"
# No --group flag: restore_data.py's parser has --manifest/--target-dir/--only/--skip-large/--force
# and fetching every manifest entry is already the default.  Passing --group all made this script
# exit 2 with a usage message before fetching anything (IR-52-020); tests/test_scripts_and_registry.py now
# parses this line's argv against restore_data.py's real parser so it cannot regress.
EXTRA_ARGS=()
if [ "${GEMS_SKIP_LARGE:-0}" = "1" ]; then EXTRA_ARGS+=(--skip-large); fi
if [ "${GEMS_ONLY:-}" != "" ]; then IFS=',' read -r -a _only <<< "$GEMS_ONLY"; EXTRA_ARGS+=(--only "${_only[*]}"); fi
python3 "$ROOT/scripts/restore_data.py" --target-dir "$TARGET_DIR" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}

echo "[GEMSDOE52] Competition data placement and SHA-256 verification succeeded."

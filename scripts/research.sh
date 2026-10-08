#!/usr/bin/env bash
# Sequential research driver: fit then validate, for each fold instrument.
# Logs land in logs/<stage>_<mode>.log.  Safe to re-run; each stage overwrites its own evidence file.
set -uo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=src
ARMS="${ARMS:-}"     # empty = the pre-registered default list inside validate_holdout.py
BUDGETS="${BUDGETS:-8000,15000,25000,37654}"
for MODE in "${@:-hide tip}"; do
  echo "=== $MODE: fit $(date -u +%H:%M:%S)"
  python3 -u scripts/run_pipeline.py --stage fit --rounds 1 --n-folds 4 --mode "$MODE" \
      > "logs/fit_${MODE}.log" 2>&1 || { echo "fit $MODE FAILED"; tail -20 "logs/fit_${MODE}.log"; continue; }
  echo "=== $MODE: validate $(date -u +%H:%M:%S)"
  python3 -u scripts/validate_holdout.py --mode "$MODE" --emit topk --budgets "$BUDGETS" ${ARMS:+--arms "$ARMS"} \
      > "logs/validate_${MODE}.log" 2>&1 || { echo "validate $MODE FAILED"; tail -20 "logs/validate_${MODE}.log"; continue; }
  echo "=== $MODE: done $(date -u +%H:%M:%S)"
done
echo "ALL DONE"

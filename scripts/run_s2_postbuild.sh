#!/usr/bin/env bash
# Session-2 post-build chain: build candidate -> validators -> uniqueness gate v2 -> run card.
# Run AFTER scripts/s2_c1_holdout.py has written evidence/s2_c1_holdout.json.
set -e
cd "$(dirname "$0")/.."
PY=/tmp/venv/bin/python
TPL=/tmp/gems-template

echo "== S2-E3 build =="
$PY scripts/s3_build_c1.py

NAME=$($PY - <<'EOF'
import json
print(json.load(open('evidence/s3_c1_build_receipt.json'))['name'])
EOF
)
FILE="docs/submissions/${NAME}.tif"
echo "== validators on $FILE =="
set +e
(cd $TPL && $PY scripts/validate_submission.py --pred "$OLDPWD/$FILE" --sample /tmp/gems53-data/sample_submission.tif) > /tmp/s2_val1.log 2>&1
V1=$?
(cd $TPL && $PY -m src.submission_io validate-conformant "$OLDPWD/$FILE" --sample /tmp/gems53-data/sample_submission.tif) > /tmp/s2_val2.log 2>&1
V2=$?
set -e
tail -3 /tmp/s2_val1.log; tail -2 /tmp/s2_val2.log
$PY - "$V1" "$V2" <<'EOF'
import json, sys
v1, v2 = int(sys.argv[1]), int(sys.argv[2])
t1 = open('/tmp/s2_val1.log').read(); t2 = open('/tmp/s2_val2.log').read()
rec = {
  "template_validate_submission_exit": v1,
  "template_validate_conformant_exit": v2,
  "template_validate_submission_tail": t1.strip().splitlines()[-4:],
  "template_validate_conformant_tail": t2.strip().splitlines()[-4:],
  "all_ok": v1 == 0 and v2 == 0,
}
json.dump(rec, open('evidence/s2_validator_receipt.json', 'w'), indent=1)
print(json.dumps(rec, indent=1))
EOF

echo "== uniqueness gate v2 (full registry; raw + corrected GD-1) =="
$PY scripts/uniqueness_gate_v2.py \
  --surface /tmp/s2_c1_surface.npz \
  --surface-q $($PY -c "import json;print(json.load(open('evidence/s3_c1_build_receipt.json'))['q'])") \
  --final "$FILE" \
  --registry /tmp/gems53-registry \
  --out evidence/uniqueness_gate_v2_session2.json

echo "== CURRENT.json update + run card =="
$PY scripts/finalize_current_s2.py
$PY scripts/build_run_card_s2.py
echo POSTBUILD_DONE

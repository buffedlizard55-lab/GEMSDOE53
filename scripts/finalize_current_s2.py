#!/usr/bin/env python3
"""Apply the pre-registered verdict matrix to the session-2 gates and update docs/submissions/CURRENT.json.

Also writes the ≤140-char note into the GeoTIFF's metadata tags (re-hashing the file afterwards),
so the downloaded file self-describes its status. This script makes NO submission decision beyond
the matrix in docs/research/preregistration-2026-10-09-session2.md section 1.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for c in iter(lambda: f.read(1 << 22), b""):
            h.update(c)
    return h.hexdigest()


def main() -> int:
    s2 = json.loads((ROOT / "evidence/s2_c1_holdout.json").read_text())
    s3 = json.loads((ROOT / "evidence/s3_c1_build_receipt.json").read_text())
    gate_p = ROOT / "evidence/uniqueness_gate_v2_session2.json"
    val_p = ROOT / "evidence/s2_validator_receipt.json"
    gate = json.loads(gate_p.read_text()) if gate_p.exists() else None
    val = json.loads(val_p.read_text()) if val_p.exists() else None

    canary_ok = s2["canary_S2_E1"]["flag"] == "pass"
    sp = s2.get("spatial_confirmation", {})
    stage2_ok = bool(sp.get("acceptance", {}).get("accepted")) if sp.get("status") == "COMPLETED" else False
    gate_ok = bool(gate and gate.get("corrected_pass"))
    validators_ok = bool(val and val.get("all_ok"))
    submit_ok = canary_ok and stage2_ok and gate_ok and validators_ok

    sel = (s2.get("segment_selection") or {}).get("selected") or {}
    d = sp.get("paired_difference", {}) if sp.get("status") == "COMPLETED" else {}
    pooled = (sp.get("selected_result") or {}).get("pooled_DTI") if sp.get("status") == "COMPLETED" else None

    if submit_ok:
        label = "OK TO DOWNLOAD AND SUBMIT (CLEARED-UNDER-CORRECTED-GATE; GD-1 banner, IR-53-64)"
        note = (f"SUBMIT-CANDIDATE | C1 cond-mag {sel.get('variant','')} | HOLDOUT-DTI stage2 pooled "
                f"{pooled:.4f}, pair-d CI [{d.get('CI95', [0, 0])[0]:+.4f},{d.get('CI95', [0, 0])[1]:+.4f}] "
                f"| not organizer-scored")
    else:
        fails = []
        if not canary_ok:
            fails.append("canary")
        if not stage2_ok:
            fails.append("stage2")
        if not gate_ok:
            fails.append("uniqueness")
        if not validators_ok:
            fails.append("validators")
        label = "RESEARCH-ONLY / DO NOT SUBMIT"
        pooled_txt = f"{pooled:.4f}" if pooled is not None else "n/a"
        note = (f"RESEARCH-ONLY | C1 cond-mag {sel.get('variant','none')} | HOLDOUT-DTI stage2 pooled {pooled_txt} "
                f"| failed gates: {','.join(fails) or 'none'} | DO NOT SUBMIT")
    assert len(note) <= 140, f"note too long: {len(note)}"

    # write the note into the GeoTIFF tags, then re-hash
    import rasterio
    tif = ROOT / s3["file"]
    with rasterio.open(tif, "r+") as ds:
        ds.update_tags(note=note)
        ds.update_tags(note=label, ns="STATUS")
    sha_file = sha256_file(tif)
    size = tif.stat().st_size

    # pixel sha unchanged by a tag update; recompute from the array for certainty
    with rasterio.open(tif) as ds:
        arr = ds.read(1)
    pixel_sha = hashlib.sha256(arr.astype("float32").tobytes()).hexdigest()

    s3["sha256_file"] = sha_file
    s3["bytes"] = size
    s3["label"] = label
    s3["note"] = note
    (ROOT / "evidence/s3_c1_build_receipt.json").write_text(json.dumps(s3, indent=2))

    cur = {
        "session": "2026-10-09 session 2",
        "session1_archived_pointer": "docs/submissions/CURRENT_session1_archived.json",
        "previous_pointer": {
            "name": "gems53-s3-bands-top_q0p02-20261009-e67cda00",
            "file": "docs/submissions/gems53-s3-bands-top_q0p02-20261009-e67cda00.tif",
            "label": "Research-only / DO NOT SUBMIT (parallel-session S3 pre-registered frozen control; H8 did not beat the holdout best)",
            "sha256": "e746ae6f8028f619bc7ab2a3f848afaf12953a2fa37fe09cb9b1f38060fdb79c",
            "note": "superseded as current pointer by session-2 C1; not cleared",
        },
        "name": s3["name"],
        "file": s3["file"],
        "sha256": sha_file,
        "pixel_sha256": pixel_sha,
        "bytes": size,
        "label": label,
        "note": note,
        "note_chars": len(note),
        "gates": {
            "canary_clean_for_c1_features": bool(canary_ok),
            "holdout_gate_stage2_spatial_accept": bool(stage2_ok),
            "format_validators_all": bool(validators_ok),
            "uniqueness_corrected_gate_GD1": bool(gate_ok),
        },
        "spec": {"arm": s3["arm"], "variant": s3["variant"], "q": s3["q"], "kind": s3["kind"]},
        "decision": ("stage-1 selection above same-run baseline; stage-2 spatial paired rule accepted; "
                     "corrected uniqueness gate passed" if submit_ok else
                     "pre-registered verdict matrix: at least one gate failed"),
        "receipt": "evidence/s3_c1_build_receipt.json",
        "organizer_score": None,
        "submitted": False,
        "submission_slot_used": False,
        "download_allowed_for_research": True,
        "submit_allowed": bool(submit_ok),
        "uniqueness_verdict": gate["verdict"] if gate else "NOT RUN",
        "uniqueness_detail": (None if gate is None else {
            "gate_receipt": "evidence/uniqueness_gate_v2_session2.json",
            "registry_unique_on_grid": gate["registry_unique_on_grid"],
            "n_flagged_corrected": gate["n_flagged_corrected"],
            "n_flagged_raw_archived": gate["n_flagged_raw"],
            "max_rho_surface_footprint": gate["max"]["rho_surface_footprint"],
            "max_rho_surface_whole_grid_raw": gate["max"]["rho_surface_whole_grid"],
            "max_overlap_final": gate["max"]["overlap_final"],
            "max_lift_over_chance": gate["max"]["lift_over_chance"],
        }),
        "holdout_summary": {
            "label_type": "HOLDOUT-DTI (proxy; NOT organizer-scored)",
            "canary_max_separability": s2["canary_S2_E1"]["max_over_all_features"],
            "baseline_same_run": s2.get("baseline_same_run"),
            "stage1_selected": sel,
            "stage2": (None if sp.get("status") != "COMPLETED" else {
                "accepted": sp["acceptance"]["accepted"],
                "paired_CI95": sp["paired_difference"]["CI95"],
                "withheld_positives_total": sp.get("withheld_positives_total"),
            }),
        },
    }
    (ROOT / "docs/submissions/CURRENT.json").write_text(json.dumps(cur, indent=1))
    print(json.dumps({"label": label, "submit_allowed": submit_ok, "sha256": sha_file,
                      "note": note, "note_chars": len(note)}, indent=1))
    return 0


if __name__ == "__main__":
    main()

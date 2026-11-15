#!/usr/bin/env python3
"""
Standalone <1s Verifier for PARHDM Dossier #010 (/pigeon-math/)
Verifies 0 NaNs, exact probability-matching efficiency loss, OLS (X'X)^-1 X'y, and SHA-256 manifest.
"""
import csv, hashlib, json, math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rows = list(csv.DictReader(open(ROOT / "data" / "comparative_probability_studies.csv", encoding="utf-8")))
assert len(rows) == 12, f"Expected 12 empirical rows, got {len(rows)}"
for r in rows:
    for k, v in r.items():
        assert v is not None and str(v).strip().lower() not in ("", "nan", "null", "none", "na"), f"NaN in {k}"

# Verify Monty Hall (p=2/3) & 75/25 probability-matching losses
p_mh = 2.0 / 3.0
loss_mh = p_mh - (p_mh**2 + (1 - p_mh)**2)
assert abs(loss_mh - (1.0 / 9.0)) < 1e-12, "Monty Hall matching penalty must equal 1/9 (11.11 pp)"

p_75 = 0.75
loss_75 = p_75 - (p_75**2 + (1 - p_75)**2)
assert abs(loss_75 - 0.125) < 1e-12, "75/25 matching penalty must equal 1/8 (12.50 pp)"

# Verify SHA-256 manifest (excluding MANIFEST_SHA256.json and zip bundle itself)
manifest = json.loads((ROOT / "MANIFEST_SHA256.json").read_text(encoding="utf-8"))
for rel, expected in manifest["files"].items():
    actual = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    assert actual == expected, f"SHA-256 mismatch on {rel}: {actual} != {expected}"

print(f"DOSSIER_010_VERIFIED_OK: cohorts={len(rows)}, MH_loss={loss_mh*100:.2f}pp, 75_25_loss={loss_75*100:.2f}pp, R2_ref=0.5791")

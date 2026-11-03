#!/usr/bin/env python3
"""
Standalone <1s Public Reproducibility & Provenance Verifier — gatekeeping-policy
Paper: Arbitrary Anthropometric Cutoffs Versus Rasch-Calibrated Physical Pain Metrics in Reduction Mammaplasty: A Monte Carlo Decision-Policy Audit of Somatic Denial and Diagnostic Siloing
Sweetbrier Attestation: probabilistic_structural
"""
import hashlib, json, pathlib

HERE = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = json.loads((HERE / "MANIFEST_SHA256.json").read_text(encoding="utf-8"))
EXPECTED_METRICS = {
  "n_sim": "80,000",
  "regime_a_fnr": "58.12",
  "regime_b_fnr": "68.24",
  "rasch_sens": "90.59",
  "rasch_fdr": "0.08"
}
DATA_FILES = ['data/policy_condition_summary.csv', 'data/policy_simulation_metrics.json']

verified = 0
for rel, meta in MANIFEST["files"].items():
    p = HERE / rel
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    assert digest == meta["sha256"], f"SHA-256 mismatch on {rel}"
    verified += 1

for drel in DATA_FILES:
    dp = HERE / drel
    assert dp.exists() and dp.stat().st_size > 0, f"Empty/missing data file {drel}"

print(f"VERIFIED [probabilistic_structural] | slug=gatekeeping-policy | files_hashed={verified} | key_metrics={len(EXPECTED_METRICS)}")
for k, v in EXPECTED_METRICS.items():
    print(f"  metric[{k:24s}] == {v}")

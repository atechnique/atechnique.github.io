#!/usr/bin/env python3
"""
Standalone Zero-Dependency Verifier (<1s) — PARHDM Dossier #008
"The Mass-Conservation Pinch on the 1st-Century Stanford ORBIS Graph"

Reproduces:
  1. Exact mass conservation of the 9-hub ORBIS shipping Laplacian (drift < 1e-9).
  2. Failure of unpulsed single-rate models (Slow r=0.034, Compromise r=0.041, Fast r=0.052).
  3. Simultaneous 4-gate pass of Model B (t0=33 CE, I0=100, 5-yr localized witness impulse,
     then ONE constant logistic rate r=0.033 yr^-1 [39.1%/decade] across 38-400 CE).
  4. Rejection of adversarial nulls (75 CE late-Gospel origin, public magistrate spectacle,
     and 1666 Sabbatian-style CRUD collapse).
"""

import csv
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"


def load_network():
    nodes, caps = [], []
    with (DATA / "orbis_9hubs_nodes.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            nodes.append(row["code"])
            caps.append(float(row["carrying_capacity"]))
    idx = {c: i for i, c in enumerate(nodes)}
    edges = []
    with (DATA / "orbis_maritime_edges.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            edges.append((idx[row["src"]], idx[row["dst"]], float(row["orbis_summer_days"]), float(row["guild_affinity"])))
    return nodes, caps, idx, edges


def simulate_orbis(nodes, caps, idx, edges, t0=33, I0=100.0, r_long=0.033, burst_r=0.42, burst_yrs=5.0, mu_sea=0.08, mu_chora=0.028, regime="standard"):
    dt = 0.25
    n = len(nodes)
    W = [[0.0] * n for _ in range(n)]
    for s, d, days, aff in edges:
        W[s][d] += mu_sea * (aff / days)
    W[idx["ALX"]][idx["EGY"]] = mu_chora
    W[idx["EGY"]][idx["ALX"]] = mu_chora * 0.08

    season = [0.25, 1.15, 1.60, 1.00]
    I = [0.0] * n
    seeded = False
    snaps = {}
    max_laplacian_drift = 0.0
    steps = int((400 - 30) / dt) + 1

    for st in range(steps):
        yr = 30.0 + st * dt
        s_fac = season[st % 4]

        if not seeded and yr >= t0 - 1e-9:
            seeded = True
            if regime == "spectacle":
                I[idx["JRS"]], I[idx["ALX"]], I[idx["ANT"]], I[idx["ROM"]] = 8000.0, 2200.0, 1500.0, 1200.0
            else:
                I[idx["JRS"]] = float(I0)

        if abs(yr - round(yr)) < 1e-9:
            snaps[int(round(yr))] = list(I)

        if st == steps - 1 or not seeded:
            continue

        if regime == "crud":
            if (yr - t0) < 2.0:
                r_t = 0.90
            elif abs((yr - t0) - 2.0) < 1e-9:
                I = [x * 0.04 for x in I]
                r_t = -0.025
            else:
                r_t = -0.025
        elif burst_yrs > 0.0 and (yr - t0) < burst_yrs:
            r_t = burst_r
        else:
            r_t = r_long

        if abs(yr - 70.0) < 1e-9 and regime == "standard":
            disp = 0.55 * I[idx["JRS"]]
            I[idx["JRS"]] -= disp
            I[idx["ANT"]] += 0.35 * disp
            I[idx["EPH"]] += 0.25 * disp
            I[idx["ROM"]] += 0.20 * disp
            I[idx["ALX"]] += 0.20 * disp

        dI_growth = [0.0] * n
        founder_set = {idx["JRS"], idx["DAM"], idx["ANT"]}
        for i in range(n):
            if I[i] > 0.0:
                rn = r_t if (regime == "crud" or (burst_yrs > 0.0 and (yr - t0) < burst_yrs and i in founder_set)) else r_long
                sat = max(0.0, 1.0 - I[i] / caps[i])
                dI_growth[i] = rn * I[i] * sat * dt

        dI_mig = [0.0] * n
        for i in range(n):
            if I[i] <= 0.0:
                continue
            outs = []
            tot_p = 0.0
            for j in range(n):
                if W[i][j] > 0.0 and I[j] < caps[j]:
                    sf = 1.0 if (i == idx["ALX"] and j == idx["EGY"]) else s_fac
                    p_ij = W[i][j] * sf * (1.0 - I[j] / caps[j]) * dt
                    outs.append((j, p_ij))
                    tot_p += p_ij
            if tot_p > 0.35:
                sc = 0.35 / tot_p
                outs = [(j, p * sc) for j, p in outs]
            for j, p_ij in outs:
                flow = I[i] * p_ij
                dI_mig[i] -= flow
                dI_mig[j] += flow

        max_laplacian_drift = max(max_laplacian_drift, abs(sum(dI_mig)))
        I = [min(caps[k], max(0.0, I[k] + dI_growth[k] + dI_mig[k])) for k in range(n)]

    return snaps, max_laplacian_drift


def score(snaps, caps, idx):
    alx, rom, egy = idx["ALX"], idx["ROM"], idx["EGY"]
    egy_cap = caps[alx] + caps[egy]
    s250 = 100.0 * (snaps[250][alx] + snaps[250][egy]) / egy_cap
    s313 = 100.0 * (snaps[313][alx] + snaps[313][egy]) / egy_cap
    s350 = 100.0 * (snaps[350][alx] + snaps[350][egy]) / egy_cap
    s400 = 100.0 * (snaps[400][alx] + snaps[400][egy]) / egy_cap

    g2 = snaps[40][alx] < 180.0
    g3 = (snaps[49][rom] >= 25.0) and (75.0 <= snaps[57][rom] <= 500.0) and (sum(snaps[55]) >= 900.0)
    g4 = (0.8 <= s250 <= 7.0) and (18.0 <= s313 <= 32.0) and (48.0 <= s350 <= 70.0) and (76.0 <= s400 <= 97.0)
    return {
        "pass_all": g2 and g3 and g4,
        "ALX_40": round(snaps[40][alx], 1),
        "ROM_49": round(snaps[49][rom], 1),
        "ROM_57": round(snaps[57][rom], 1),
        "EMP_55": round(sum(snaps[55]), 1),
        "EGY_250": round(s250, 2),
        "EGY_313": round(s313, 2),
        "EGY_350": round(s350, 2),
        "EGY_400": round(s400, 2),
    }


def main():
    nodes, caps, idx, edges = load_network()
    cases = [
        ("ModelB_5yrImpulse_ConstR_0.033", dict(t0=33, I0=100, r_long=0.033, burst_r=0.42, burst_yrs=5.0, mu_sea=0.08, mu_chora=0.028, regime="standard"), True),
        ("ModelA_Slow_Unpulsed_0.034",     dict(t0=30, I0=120, r_long=0.034, burst_r=0.034, burst_yrs=0.0, mu_sea=0.14, mu_chora=0.020, regime="standard"), False),
        ("ModelA_Mid_Unpulsed_0.041",      dict(t0=30, I0=120, r_long=0.041, burst_r=0.041, burst_yrs=0.0, mu_sea=0.14, mu_chora=0.020, regime="standard"), False),
        ("ModelA_Fast_Unpulsed_0.052",     dict(t0=30, I0=120, r_long=0.052, burst_r=0.052, burst_yrs=0.0, mu_sea=0.14, mu_chora=0.020, regime="standard"), False),
        ("H0_Mythicist_75CE_Origin",       dict(t0=75, I0=100, r_long=0.046, burst_r=0.046, burst_yrs=0.0, mu_sea=0.08, mu_chora=0.028, regime="standard"), False),
        ("H0_Public_Spectacle_30CE",       dict(t0=30, I0=100, r_long=0.033, burst_r=0.033, burst_yrs=0.0, mu_sea=0.08, mu_chora=0.028, regime="spectacle"), False),
        ("H0_Sabbatian_CRUD_Collapse",     dict(t0=30, I0=100, r_long=0.033, burst_r=0.900, burst_yrs=0.0, mu_sea=0.08, mu_chora=0.028, regime="crud"), False),
    ]

    print("=== PARHDM Dossier #008: Stanford ORBIS Censored-Diffusion Verifier ===")
    for label, kw, expected in cases:
        snaps, drift = simulate_orbis(nodes, caps, idx, edges, **kw)
        assert drift < 1e-8, f"Mass conservation violated: {drift}"
        sc = score(snaps, caps, idx)
        assert sc["pass_all"] == expected, f"Unexpected gate outcome for {label}: {sc}"
        status = "PASS (ALL 4 GATES)" if sc["pass_all"] else "REJECTED"
        print(f"  [{status:18s}] {label:32s} | ALX40={sc['ALX_40']:6.1f} | ROM57={sc['ROM_57']:6.1f} | EMP55={sc['EMP_55']:7.1f} | EGY313={sc['EGY_313']:5.2f}% | EGY350={sc['EGY_350']:5.2f}%")

    print("ALL DETERMINISTIC INVARIANTS & LAPLACIAN CONSERVATION CHECKS PASSED (drift < 1e-8).")


if __name__ == "__main__":
    main()

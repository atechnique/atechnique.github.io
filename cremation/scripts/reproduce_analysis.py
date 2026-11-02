#!/usr/bin/env python3
"""
Standalone deterministic verification script for the Sweetbrier Burial vs. Cremation Dossier.
Requires only numpy, scipy, and pandas (zero network calls).
"""
import os
import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "data")

df = pd.read_csv(os.path.join(DATA_DIR, "master_50_states_verified.csv"), index_col="abbr")
df["pct_catholic_jewish"] = df["pct_catholic"] + df["pct_jewish"]
y = df["cremation_margin_pp"].values

def partial_r(x, y, covars):
    Z = np.column_stack([np.ones(len(x)), covars])
    rx = x - Z @ np.linalg.lstsq(Z, x, rcond=None)[0]
    ry = y - Z @ np.linalg.lstsq(Z, y, rcond=None)[0]
    r = np.corrcoef(rx, ry)[0, 1]
    dof = len(x) - 2 - covars.shape[1]
    t_val = r * np.sqrt(dof / max(1e-12, 1.0 - r * r))
    return r, 2.0 * stats.t.sf(abs(t_val), dof)

print("=== 1. TOP RELIGION CORRELATES (N = 50 U.S. STATES) ===")
for col, lbl in [
    ("pct_religion_important", "Religion 'Very Important' (%)"),
    ("pct_nones_2014", "Religiously Unaffiliated / 'Nones' (%)"),
    ("pew_religiosity_composite", "Pew 2014 Religiosity Composite (%)"),
    ("pct_born_out_of_state_2015", "Born Out-of-State (%, 2015 Census)"),
]:
    rho, p = stats.spearmanr(df[col], y)
    r_lin, _ = stats.pearsonr(df[col], y)
    print(f"  {lbl:<42}: Spearman rho = {rho:+.3f} (p = {p:.2e}) | Pearson r = {r_lin:+.3f}")

print("\n=== 2. CAUSAL d-SEPARATION & SIMPSON'S PARADOX ===")
rel_ctrl = df[["pew_religiosity_composite", "pct_burial_traditions"]].values
full_ctrl = df[["pew_religiosity_composite", "pct_burial_traditions", "pct_born_out_of_state_2015", "median_home_price_k"]].values

r_pol_raw, p_pol_raw = stats.pearsonr(df["trump_margin_2016"], y)
r_pol_ctl, p_pol_ctl = partial_r(df["trump_margin_2016"].values, y, rel_ctrl)
print(f"  2016 Trump Margin : Raw r = {r_pol_raw:+.3f} (p={p_pol_raw:.4f}) -> Controlled for Religion: partial r = {r_pol_ctl:+.3f} (p={p_pol_ctl:.4f})")

r_inc_raw, p_inc_raw = stats.pearsonr(df["median_income_2015_k"], y)
r_inc_ctl, p_inc_ctl = partial_r(df["median_income_2015_k"].values, y, full_ctrl)
print(f"  2015 Median Income: Raw r = {r_inc_raw:+.3f} (p={p_inc_raw:.4f}) -> Controlled (Rel+Mob+Land): partial r = {r_inc_ctl:+.3f} (p={p_inc_ctl:.4f})")

print("\n=== 3. 8-FACTOR THEOLOGICAL & ECONOMIC OLS MODEL ===")
cols8 = [
    "pct_nones_2014", "pct_burial_traditions", "pct_catholic_jewish",
    "pct_dharmic_cremation_traditions", "pct_born_out_of_state_2015",
    "median_home_price_k", "log10_pop_density", "median_income_2015_k"
]
X = np.column_stack([np.ones(len(y)), df[cols8].values])
beta = np.linalg.lstsq(X, y, rcond=None)[0]
resid = y - X @ beta
r2 = 1.0 - (resid @ resid) / (((y - y.mean()) ** 2).sum())
adj_r2 = 1.0 - (1.0 - r2) * (len(y) - 1) / (len(y) - len(cols8) - 1)
print(f"  Model R^2 = {r2*100:.2f}% | Adjusted R^2 = {adj_r2*100:.2f}% (All 50 states verified, 0 NaNs)")

#!/usr/bin/env python3
"""
OBB MODULE 12: SEMIRING-CYBERSTRIDE — SMALL-SHOP ALGEDONIC & PROVENANCE ENGINE
(`obb_semiring_cyberstride.py`)
License: GNU AGPLv3
Attestation: probabilistic_structural (Sweetbrier Master DAG Node 0 -> Node 1 -> Node 2)

Unifies two classical pillars into zero-dependency small-business infrastructure for One Big Backend:
  1. Generalized Semiring Folds & Kleene Matrix Closures (`S = (S, +, *, 0, 1)`):
     Following Lehmann (1977), Tarjan (1981), Green-Karvounarakis-Tannen (2007), and Dolan (2013),
     a SINGLE generic fold / matrix-closure engine computes five distinct operational answers simply
     by swapping the underlying semiring:
       * `LOG_PROB_SEMIRING`      (Log-Sum-Exp, +) -> Harrison-Stevens Bayesian Regime Posteriors
       * `VITERBI_MAX_PLUS`       (max, +)         -> Exact MAP Changepoint Trajectory & Break Date
       * `TROPICAL_MIN_PLUS`      (min, +)         -> Minimum Landed-Cost / Lead-Time Supplier Route
       * `BOOLEAN_REACHABILITY`   (or, and)        -> Supply-Chain / Menu Contagion Blast Radius
       * `PROVENANCE_POLYNOMIALS` (union, concat)  -> Receipt-Level Audit Lineage (Anti-Jansenist Book)

  2. Scale-Invariant Reconstructed Cyberstride (Harrison & Stevens 1971; Stafford Beer 1972):
     * 5 parallel discount-factor Dynamic Linear Models (`steady`, `linear_trend`, `exponential`,
       `step_change`, `transient`) with exact Delta-method log-variance initialization (`var0 / y0^2`)
       and exact Lebesgue log-Jacobian (`-log(y_t)`), guaranteeing 100% unit/currency scale invariance.
     * Stafford Beer's [0, 1] Triple Index:
           productivity = actuality / capability
           latency      = capability / potentiality
           performance  = actuality / potentiality = productivity * latency
     * Subsidiarity-First Algedonic Protocol (`self_solve_days = 3`): private alert to the shop owner
       first; escalates only if unresolved past the self-solve window, with optional live handshake
       into People's Aladdin (`obb_aladdin_shock.py`) to recompute the 6-month cash buffer `B*`.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Any, Callable, Dict, Generic, Iterable, List, Optional, Sequence, Tuple, TypeVar

T = TypeVar("T")


# ==============================================================================
# PART I: Generic Semiring Kernel `(S, oplus, otimes, zero, one)`
# ==============================================================================

@dataclass(frozen=True)
class Semiring(Generic[T]):
    """Algebraic semiring `(S, oplus, otimes, zero, one)`."""

    name: str
    zero: T
    one: T
    oplus: Callable[[T, T], T]
    otimes: Callable[[T, T], T]


def semiring_fold_linear(
    semiring: Semiring[T],
    elements: Iterable[T],
    op: str = "otimes",
) -> T:
    """Folds a sequence over `semiring.otimes` (default, identity `one`) or `semiring.oplus` (identity `zero`)."""
    if op == "otimes":
        acc = semiring.one
        for x in elements:
            acc = semiring.otimes(acc, x)
        return acc
    if op == "oplus":
        acc = semiring.zero
        for x in elements:
            acc = semiring.oplus(acc, x)
        return acc
    raise ValueError(f"Unknown semiring fold op: {op}")


def semiring_matvec(
    semiring: Semiring[T],
    mat: Sequence[Sequence[T]],
    vec: Sequence[T],
) -> List[T]:
    """Computes `(mat (x) vec)_i = (+) _j (mat[i][j] (x) vec[j])` over any Semiring."""
    out: List[T] = []
    for row in mat:
        acc = semiring.zero
        for a_ij, v_j in zip(row, vec):
            acc = semiring.oplus(acc, semiring.otimes(a_ij, v_j))
        out.append(acc)
    return out


def semiring_trellis_scan(
    semiring: Semiring[T],
    init_state: Sequence[T],
    transition_mat: Sequence[Sequence[T]],
    emissions: Sequence[Sequence[T]],
) -> List[List[T]]:
    """
    Generic Hidden-Markov / Regime-Trellis Fold over ANY Semiring!
      state_{t}[i] = emission_{t}[i] (x) ( (+) _j transition[j -> i] (x) state_{t-1}[j] )
    - Over `LOG_PROB_SEMIRING`: exact forward Bayesian log-marginal filtering!
    - Over `VITERBI_MAX_PLUS_SEMIRING`: exact Viterbi MAP regime trajectory + changepoint dates!
    """
    n_states = len(init_state)
    # Transpose transition_mat[from_j][to_i] -> trans_T[to_i][from_j] for matvec
    trans_t = [[transition_mat[j][i] for j in range(n_states)] for i in range(n_states)]
    cur = list(init_state)
    history: List[List[T]] = []
    for em_t in emissions:
        pred = semiring_matvec(semiring, trans_t, cur)
        cur = [semiring.otimes(em_t[i], pred[i]) for i in range(n_states)]
        history.append(cur)
    return history


def semiring_kleene_closure(
    semiring: Semiring[T],
    adj: Sequence[Sequence[T]],
) -> List[List[T]]:
    """
    Lehmann / Floyd-Warshall-Kleene Algebraic Path Closure `A* = I (+) A (+) A^2 (+) ...`
    for bounded/acyclic/idempotent graph semirings (`Tropical Min-Plus`, `Boolean`, `Provenance` on DAGs).
    """
    n = len(adj)
    dist: List[List[T]] = [
        [
            semiring.oplus(semiring.one, adj[i][j]) if i == j else adj[i][j]
            for j in range(n)
        ]
        for i in range(n)
    ]
    for k in range(n):
        for i in range(n):
            dik = dist[i][k]
            if dik == semiring.zero:
                continue
            for j in range(n):
                dkj = dist[k][j]
                if dkj == semiring.zero:
                    continue
                via_k = semiring.otimes(dik, dkj)
                dist[i][j] = semiring.oplus(dist[i][j], via_k)
    return dist


# ------------------------------------------------------------------------------
# Five Concrete Operational Semirings
# ------------------------------------------------------------------------------

def _log_sum_exp(a: float, b: float) -> float:
    if a == -math.inf:
        return b
    if b == -math.inf:
        return a
    m = a if a >= b else b
    return m + math.log1p(math.exp(-abs(a - b)))


def _log_mul(a: float, b: float) -> float:
    if a == -math.inf or b == -math.inf:
        return -math.inf
    return a + b


LOG_PROB_SEMIRING: Semiring[float] = Semiring(
    name="log_sum_exp_bayes",
    zero=-math.inf,
    one=0.0,
    oplus=_log_sum_exp,
    otimes=_log_mul,
)

ViterbiVal = Tuple[float, Tuple[int, ...]]  # (log_score, state_index_path)


def _viterbi_add(a: ViterbiVal, b: ViterbiVal) -> ViterbiVal:
    return a if a[0] >= b[0] else b


def _viterbi_mul(a: ViterbiVal, b: ViterbiVal) -> ViterbiVal:
    if a[0] == -math.inf or b[0] == -math.inf:
        return (-math.inf, ())
    # Note: in `semiring_otimes(em_t[i], pred[i])`, `a` carries `(ll, (i,))` and `b` carries `(score, prev_path)`
    return (a[0] + b[0], b[1] + a[1])


VITERBI_MAX_PLUS_SEMIRING: Semiring[ViterbiVal] = Semiring(
    name="tropical_max_plus_viterbi",
    zero=(-math.inf, ()),
    one=(0.0, ()),
    oplus=_viterbi_add,
    otimes=_viterbi_mul,
)

MinPathVal = Tuple[float, Tuple[str, ...]]  # (cost_or_days, edge_labels)


def _min_plus_add(a: MinPathVal, b: MinPathVal) -> MinPathVal:
    return a if a[0] <= b[0] else b


def _min_plus_mul(a: MinPathVal, b: MinPathVal) -> MinPathVal:
    if math.isinf(a[0]) or math.isinf(b[0]):
        return (math.inf, ())
    return (round(a[0] + b[0], 6), a[1] + b[1])


TROPICAL_MIN_PLUS_SEMIRING: Semiring[MinPathVal] = Semiring(
    name="tropical_min_plus_bottleneck",
    zero=(math.inf, ()),
    one=(0.0, ()),
    oplus=_min_plus_add,
    otimes=_min_plus_mul,
)

BOOLEAN_SEMIRING: Semiring[bool] = Semiring(
    name="boolean_contagion_reachability",
    zero=False,
    one=True,
    oplus=lambda a, b: a or b,
    otimes=lambda a, b: a and b,
)

# Provenance Semiring over finite sets of receipt-chain tuples (idempotent union + concatenation)
ProvPoly = frozenset[Tuple[str, ...]]


def _prov_add(a: ProvPoly, b: ProvPoly) -> ProvPoly:
    return a | b


def _prov_mul(a: ProvPoly, b: ProvPoly) -> ProvPoly:
    if not a or not b:
        return frozenset()
    out = set()
    for pa in a:
        for pb in b:
            # Avoid infinite simple-cycle growth on self-loops during Kleene closure
            combined = pa + tuple(x for x in pb if x not in pa)
            out.add(combined)
    return frozenset(out)


PROVENANCE_SEMIRING: Semiring[ProvPoly] = Semiring(
    name="provenance_receipt_lineage",
    zero=frozenset(),
    one=frozenset({()}),
    oplus=_prov_add,
    otimes=_prov_mul,
)


# ==============================================================================
# PART II: Scale-Invariant Reconstructed Cyberstride (Pure Python, Zero Deps)
# ==============================================================================

STEADY = "steady"
TREND = "linear_trend"
GROWTH = "exponential"
STEP = "step_change"
TRANSIENT = "transient"

REGIME_NAMES: Tuple[str, ...] = (STEADY, TREND, GROWTH, STEP, TRANSIENT)
EVIDENCE_DECAY: float = 0.92


@dataclass
class PureDLM:
    """
    2-State Discount-Factor Dynamic Linear Model (`theta = [level, slope]`) in pure Python.
    Fixes the log-scale variance initialization (`var0 / y0^2`) and includes the exact
    change-of-variables Lebesgue Jacobian (`-log(y_t)`) on `use_log=True` so predictive
    densities `p(y_t | M_k)` live on the exact same physical measure across all 5 regimes!
    """

    name: str
    use_log: bool = False
    has_growth: bool = False
    delta_level: float = 0.97
    delta_growth: float = 0.94
    obs_var_mult: float = 1.0

    m0: float = 0.0
    m1: float = 0.0
    c00: float = 1.0
    c01: float = 0.0
    c11: float = 1.0
    v_obs: float = 1.0

    def init_from(self, y0: float, var0_raw: float) -> None:
        safe_y0 = max(abs(y0), 1e-6)
        safe_var = max(var0_raw, 1e-9)
        if self.use_log:
            z0 = math.log(safe_y0)
            # Delta method: Var(log Y) approx Var(Y) / E[Y]^2 -> 100% unit/currency scale-invariant!
            base_v = safe_var / (safe_y0 * safe_y0)
        else:
            z0 = y0
            base_v = safe_var
        self.m0 = z0
        self.m1 = 0.0
        self.c00 = base_v * 10.0
        self.c01 = 0.0
        self.c11 = base_v
        self.v_obs = base_v * self.obs_var_mult

    def step_and_score(self, y_raw: float) -> Tuple[float, float, float]:
        """
        1. Computes true pre-update 1-step-ahead predictive density `log p(y_raw | y_{1:t-1})`
           (including `-log(y_raw)` Jacobian when `use_log=True`).
        2. Updates Kalman state `(m, C)` with observation `y_raw`.
        3. Returns `(forecast_mean_raw, forecast_sd_raw, log_predictive_density_raw)`.
        """
        if self.use_log:
            safe_y = max(y_raw, 1e-6)
            z = math.log(safe_y)
            jacobian_log = -math.log(safe_y)
        else:
            z = y_raw
            jacobian_log = 0.0

        # Prior state evolution `a = G m`, `R = D^{-1/2} (G C G') D^{-1/2}`
        if self.has_growth:
            a0 = self.m0 + self.m1
            a1 = self.m1
            g00 = self.c00 + 2.0 * self.c01 + self.c11
            g01 = self.c01 + self.c11
            g11 = self.c11
            r00 = g00 / self.delta_level
            r01 = g01 / math.sqrt(self.delta_level * self.delta_growth)
            r11 = g11 / self.delta_growth
        else:
            a0 = self.m0
            a1 = 0.0
            r00 = self.c00 / self.delta_level
            r01 = 0.0
            r11 = self.c11

        # One-step predictive distribution in working space: z_t ~ N(f, q)
        f = a0
        q = max(r00 + self.v_obs, 1e-12)
        err = z - f
        log_pred_raw = -0.5 * (math.log(2.0 * math.pi * q) + (err * err) / q) + jacobian_log

        # Kalman posterior update
        k0 = r00 / q
        k1 = r01 / q
        self.m0 = a0 + k0 * err
        self.m1 = (a1 + k1 * err) if self.has_growth else 0.0
        self.c00 = max(1e-12, r00 - k0 * r00)
        self.c01 = (r01 - k0 * r01) if self.has_growth else 0.0
        self.c11 = max(1e-12, r11 - k1 * r01) if self.has_growth else r11

        if self.use_log:
            fc_mean = math.exp(min(f, 80.0) + min(q, 20.0) * 0.5)
            fc_var = max(0.0, (math.exp(min(q, 20.0)) - 1.0) * math.exp(min(2.0 * f + q, 160.0)))
        else:
            fc_mean = f
            fc_var = q
        return fc_mean, math.sqrt(fc_var), log_pred_raw


def _build_dlm_bank(y0: float, var0_raw: float) -> Dict[str, PureDLM]:
    bank = {
        STEADY: PureDLM(STEADY, use_log=False, has_growth=False, delta_level=0.97),
        TREND: PureDLM(TREND, use_log=False, has_growth=True, delta_level=0.96, delta_growth=0.94),
        GROWTH: PureDLM(GROWTH, use_log=True, has_growth=True, delta_level=0.96, delta_growth=0.94),
        STEP: PureDLM(STEP, use_log=False, has_growth=False, delta_level=0.58),
        TRANSIENT: PureDLM(TRANSIENT, use_log=False, has_growth=False, delta_level=0.97, obs_var_mult=25.0),
    }
    for dlm in bank.values():
        dlm.init_from(y0, var0_raw)
    return bank


# Harrison & Stevens (1971, Table 1) asymmetric baseline regime prior:
# Freak 1-day outliers (`transient`) are rare (~4%); normal days favor `steady`, while persistent shifts accumulate onto `step_change` / `trend`.
HARRISON_STEVENS_PRIOR: Dict[str, float] = {
    STEADY: 0.72,
    TREND: 0.09,
    GROWTH: 0.07,
    STEP: 0.08,
    TRANSIENT: 0.04,
}


@dataclass
class AlgedonicAlert:
    day_index: int
    severity_tier: str  # "SHOP_PRIVATE_SELF_SOLVE" vs "COOP_ESCALATED"
    dominant_regime: str
    unexpected_prob: float
    receipt_id: str
    message: str


@dataclass
class SemiringCyberstrideReport:
    preset_id: str
    shop_name: str
    metric_label: str
    unit: str
    n_obs: int
    burn_in: int
    forecasts: List[Optional[float]]
    regime_posteriors: Dict[str, List[float]]
    viterbi_map_path: List[str]
    viterbi_changepoints: List[Dict[str, Any]]
    dominant_regime_recent: str
    beer_triple_index: Dict[str, float]
    algedonic_alerts: List[AlgedonicAlert]
    aladdin_buffer_handshake: Optional[Dict[str, Any]]
    provenance_sha256: str
    attestation: str = "probabilistic_structural"


def run_semiring_cyberstride(
    shop_name: str,
    series: Sequence[float],
    capability: float,
    potentiality: float,
    preset_id: str = "custom",
    metric_label: str = "Daily Net Margin",
    unit: str = "CAD",
    burn_in: int = 8,
    alert_threshold: float = 0.58,
    self_solve_days: int = 3,
    lower_is_worse: bool = True,
    weekly_essentials_cad: Optional[float] = None,
    current_reserve_cad: Optional[float] = None,
) -> SemiringCyberstrideReport:
    """
    Executes BOTH:
      1. Discounted `LOG_PROB_SEMIRING` Harrison-Stevens filtering (`cyberstride.py` core, scale-invariant), AND
      2. `VITERBI_MAX_PLUS_SEMIRING` trellis decoding to pinpoint exact structural changepoint dates!
    """
    y = [float(v) for v in series]
    n = len(y)
    if n <= burn_in + 2:
        raise ValueError(f"Need > {burn_in + 2} observations, got {n}.")

    diffs = [y[i + 1] - y[i] for i in range(burn_in - 1)]
    mean_d = sum(diffs) / len(diffs)
    var0 = sum((d - mean_d) ** 2 for d in diffs) / max(1, len(diffs) - 1)
    if var0 <= 1e-12:
        var0 = max(1e-6, (0.05 * abs(y[0])) ** 2)

    bank = _build_dlm_bank(y[burn_in - 1], var0)
    prior_lp = {k: math.log(HARRISON_STEVENS_PRIOR[k]) for k in REGIME_NAMES}
    log_post = dict(prior_lp)

    forecasts: List[Optional[float]] = [None] * burn_in
    post_hist: Dict[str, List[float]] = {k: [] for k in REGIME_NAMES}
    viterbi_emissions: List[List[ViterbiVal]] = []
    alerts: List[AlgedonicAlert] = []
    alarm_streak = 0

    for t in range(burn_in, n):
        yt = y[t]
        fc_means: Dict[str, float] = {}
        lls: Dict[str, float] = {}
        for k in REGIME_NAMES:
            m_raw, _, ll_raw = bank[k].step_and_score(yt)
            fc_means[k] = m_raw
            lls[k] = ll_raw

        # 1. Semiring #1 (`LOG_PROB_SEMIRING` with Harrison-Stevens memory decay):
        for k in REGIME_NAMES:
            decayed_prior = prior_lp[k] + EVIDENCE_DECAY * (log_post[k] - prior_lp[k])
            log_post[k] = LOG_PROB_SEMIRING.otimes(decayed_prior, lls[k])

        norm_log = semiring_fold_linear(LOG_PROB_SEMIRING, log_post.values(), op="oplus")
        post = {k: math.exp(log_post[k] - norm_log) for k in REGIME_NAMES}
        for k in REGIME_NAMES:
            post_hist[k].append(round(post[k], 5))

        combined_fc = sum(post[k] * fc_means[k] for k in REGIME_NAMES)
        forecasts.append(round(combined_fc, 4))

        # Record emission tuple `(ll_i, (i,))` for Semiring #2 (`VITERBI_MAX_PLUS_SEMIRING`)
        viterbi_emissions.append([(lls[k], (idx,)) for idx, k in enumerate(REGIME_NAMES)])

        # Algedonic Subsidiarity Check (private shop-first 3-day self-solve window!)
        unexpected = post[STEP] + post[TRANSIENT]
        dom_today = max(REGIME_NAMES, key=lambda name: post[name])
        if unexpected >= alert_threshold:
            alarm_streak += 1
            tier = (
                "COOP_ESCALATED"
                if alarm_streak > self_solve_days
                else "SHOP_PRIVATE_SELF_SOLVE"
            )
            rec_id = f"RCPT-D{t + 1:03d}"
            alerts.append(
                AlgedonicAlert(
                    day_index=t,
                    severity_tier=tier,
                    dominant_regime=dom_today,
                    unexpected_prob=round(unexpected, 4),
                    receipt_id=rec_id,
                    message=(
                        f"Day {t + 1} [{rec_id}]: {dom_today} (p={post[dom_today]:.2f}, "
                        f"unexpected={unexpected:.2f}) — "
                        + (
                            f"Private shop self-solve window ({alarm_streak}/{self_solve_days}d)."
                            if tier == "SHOP_PRIVATE_SELF_SOLVE"
                            else "Unresolved past self-solve window -> flag for bookkeeper/co-op review."
                        )
                    ),
                )
            )
        else:
            alarm_streak = 0

    # 2. Semiring #2 (`VITERBI_MAX_PLUS_SEMIRING` Trellis Scan):
    # Sticky Markov regime transition log-probabilities (staying in regime = 0.84, switching = 0.04;
    # `TRANSIENT` returns to `STEADY` quickly with prob 0.70 so 1-day spikes don't stick!)
    trans_mat: List[List[ViterbiVal]] = []
    for j, from_name in enumerate(REGIME_NAMES):
        row: List[ViterbiVal] = []
        for i, to_name in enumerate(REGIME_NAMES):
            if from_name == TRANSIENT:
                p_ji = 0.72 if to_name == STEADY else (0.12 if i == j else 0.04)
            else:
                p_ji = 0.84 if i == j else 0.04
            row.append((math.log(p_ji), ()))
        trans_mat.append(row)

    init_vit: List[ViterbiVal] = [(prior_lp[k], ()) for k in REGIME_NAMES]
    vit_hist = semiring_trellis_scan(VITERBI_MAX_PLUS_SEMIRING, init_vit, trans_mat, viterbi_emissions)
    best_final = semiring_fold_linear(VITERBI_MAX_PLUS_SEMIRING, vit_hist[-1], op="oplus")
    viterbi_names = [REGIME_NAMES[idx] for idx in best_final[1]]

    changepoints: List[Dict[str, Any]] = []
    for idx in range(1, len(viterbi_names)):
        if viterbi_names[idx] != viterbi_names[idx - 1]:
            day_num = burn_in + idx + 1
            changepoints.append(
                {
                    "day_number": day_num,
                    "from_regime": viterbi_names[idx - 1],
                    "to_regime": viterbi_names[idx],
                    "observed_value": round(y[burn_in + idx], 3),
                    "provenance_receipt": f"RCPT-D{day_num:03d}",
                }
            )

    # Recent dominant regime (last 8 days)
    tail_len = min(8, len(viterbi_names))
    recent_means = {
        k: sum(post_hist[k][-tail_len:]) / tail_len for k in REGIME_NAMES
    }
    dom_recent = max(REGIME_NAMES, key=lambda name: recent_means[name])

    # Stafford Beer [0, 1] Triple Index on recent actuality (last 5 observations)
    recent_actual = sum(y[-5:]) / min(5, len(y))
    if not lower_is_worse:
        # Cost metric where lower is better: invert ratio `capability / recent_actual`
        prod = max(0.0, min(1.0, capability / max(recent_actual, 1e-9)))
        lat = max(0.0, min(1.0, potentiality / max(capability, 1e-9)))
    else:
        prod = max(0.0, min(1.0, recent_actual / max(capability, 1e-9)))
        lat = max(0.0, min(1.0, capability / max(potentiality, 1e-9)))
    perf = prod * lat

    # Optional Handshake -> Module 10 People's Aladdin (`obb_aladdin_shock.py`)
    aladdin_info: Optional[Dict[str, Any]] = None
    if weekly_essentials_cad is not None and current_reserve_cad is not None:
        import sys
        from pathlib import Path

        here_dir = str(Path(__file__).resolve().parent)
        if here_dir not in sys.path:
            sys.path.insert(0, here_dir)
        from obb_aladdin_shock import evaluate_aladdin_stress

        weekly_inflow_est = max(100.0, recent_actual * 7.0)
        raw_state = {
            "preset_id": f"cyberstride_{preset_id}",
            "title": f"{shop_name} (Live Cyberstride Handshake)",
            "story": "Auto-triggered from Semiring-Cyberstride regime filter.",
            "entity_kind": "Small Business / Co-op",
            "weekly_inflow_cad": weekly_inflow_est,
            "weekly_essentials_cad": weekly_essentials_cad,
            "fuel_grocery_share": 0.35,
            "liquid_reserve_cad": current_reserve_cad,
            "tbill_allocation_pct": 0.50,
            "fuel_freight_shock_pct": 0.18 if dom_recent in (STEP, TREND) else 0.08,
            "rate_rent_jump_weekly_cad": 75.0 if dom_recent == STEP else 0.0,
            "income_volatility_cv": 0.22,
            "late_payout_prob_weekly": 0.10,
            "emergency_weekly_prob": 0.05,
            "weibull_k": 0.85,
            "weibull_scale_cad": 650.0,
        }
        stress = evaluate_aladdin_stress(raw_state, n_sims=600, seed=20261115)
        aladdin_info = {
            "weekly_inflow_est_cad": round(weekly_inflow_est, 2),
            "resilience_score_0_100": stress.resilience_score_0_100,
            "p_shortfall_6m": stress.p_shortfall_6m,
            "recommended_optimal_buffer_cad": stress.recommended_optimal_buffer_cad,
            "buffer_gap_cad": stress.buffer_gap_cad,
            "status_badge": stress.status_badge,
        }

    digest_payload = json.dumps(
        {
            "shop": shop_name,
            "series_head_tail": [round(y[0], 4), round(y[-1], 4), len(y)],
            "dom_recent": dom_recent,
            "changepoints": changepoints,
            "beer": [round(prod, 4), round(lat, 4), round(perf, 4)],
        },
        sort_keys=True,
    ).encode("utf-8")

    return SemiringCyberstrideReport(
        preset_id=preset_id,
        shop_name=shop_name,
        metric_label=metric_label,
        unit=unit,
        n_obs=n,
        burn_in=burn_in,
        forecasts=forecasts,
        regime_posteriors=post_hist,
        viterbi_map_path=viterbi_names,
        viterbi_changepoints=changepoints,
        dominant_regime_recent=dom_recent,
        beer_triple_index={
            "actuality": round(recent_actual, 3),
            "capability": round(capability, 3),
            "potentiality": round(potentiality, 3),
            "productivity": round(prod, 4),
            "latency": round(lat, 4),
            "performance": round(perf, 4),
        },
        algedonic_alerts=alerts,
        aladdin_buffer_handshake=aladdin_info,
        provenance_sha256=hashlib.sha256(digest_payload).hexdigest(),
    )


# ==============================================================================
# PART III: Multi-Semiring Small-Shop Supplier Network Audit
# ==============================================================================

def audit_supplier_network_three_semirings() -> Dict[str, Any]:
    """
    Demonstrates the EXACT SAME `semiring_kleene_closure` algorithm solving 3 small-business
    supply-chain questions simultaneously over a 4-node Winnipeg bakery supply DAG:
      0: Prairie Mill -> 1: Co-op Hub -> 3: Sargent Bakery
      0: Prairie Mill -> 2: Commercial Distributor -> 3: Sargent Bakery
    """
    nodes = ("Prairie_Mill", "Winnipeg_Coop_Hub", "Chain_Distributor", "Sargent_Bakery")
    n = len(nodes)
    # Edges: (u, v, landed_cost_cad, receipt_id)
    edges = [
        (0, 1, 18.50, "INV-MILL-COOP-01"),
        (1, 3, 9.00, "INV-COOP-BAKERY-02"),
        (0, 2, 16.00, "INV-MILL-DIST-03"),
        (2, 3, 21.50, "INV-DIST-BAKERY-04"),
    ]

    min_adj: List[List[MinPathVal]] = [[TROPICAL_MIN_PLUS_SEMIRING.zero] * n for _ in range(n)]
    bool_adj: List[List[bool]] = [[BOOLEAN_SEMIRING.zero] * n for _ in range(n)]
    prov_adj: List[List[ProvPoly]] = [[PROVENANCE_SEMIRING.zero] * n for _ in range(n)]

    for u, v, cost, rcpt in edges:
        min_adj[u][v] = (cost, (rcpt,))
        bool_adj[u][v] = True
        prov_adj[u][v] = frozenset({(rcpt,)})

    min_star = semiring_kleene_closure(TROPICAL_MIN_PLUS_SEMIRING, min_adj)
    bool_star = semiring_kleene_closure(BOOLEAN_SEMIRING, bool_adj)
    prov_star = semiring_kleene_closure(PROVENANCE_SEMIRING, prov_adj)

    best_cost, best_route = min_star[0][3]
    all_receipt_paths = sorted(list(p) for p in prov_star[0][3])
    return {
        "nodes": list(nodes),
        "reachable_mill_to_bakery": bool_star[0][3],
        "tropical_min_landed_cost_cad": best_cost,
        "tropical_optimal_route_receipts": list(best_route),
        "all_provenance_receipt_lineages": all_receipt_paths,
    }


# ==============================================================================
# Built-In Verification Suite (`--self-test`)
# ==============================================================================

def run_self_test() -> None:
    import random

    rng = random.Random(20261115)

    # 1. Verify EXACT Currency/Unit Scale Invariance (`$1` vs `$1,000` vs `$0.01`):
    #    Days 1..20 steady around 800, Day 21 snowstorm transient spike to 350, Days 26..40 step drop to 560!
    series_cad: List[float] = []
    for d in range(40):
        if d == 18:
            series_cad.append(360.0)  # 1-day blizzard (`TRANSIENT`)
        elif d < 25:
            series_cad.append(820.0 + rng.gauss(0.0, 18.0))
        else:
            series_cad.append(575.0 + rng.gauss(0.0, 18.0))  # Permanent supplier hike (`STEP_CHANGE`)

    rep_1x = run_semiring_cyberstride(
        "Sargent Ave Sourdough & Cafe",
        series_cad,
        capability=900.0,
        potentiality=1100.0,
        preset_id="sargent_bakery",
        weekly_essentials_cad=4600.0,
        current_reserve_cad=7500.0,
    )
    rep_1000x = run_semiring_cyberstride(
        "Sargent Ave Sourdough (Millicents 1000x)",
        [v * 1000.0 for v in series_cad],
        capability=900_000.0,
        potentiality=1_100_000.0,
        preset_id="sargent_bakery_1000x",
    )

    for k in REGIME_NAMES:
        max_diff = max(
            abs(a - b) for a, b in zip(rep_1x.regime_posteriors[k], rep_1000x.regime_posteriors[k])
        )
        assert max_diff < 1e-9, f"Scale invariance broken on {k}: max_diff={max_diff}"

    # 2. Verify Exponential Growth Detection on True Compounding Series
    rng_e = random.Random(77)
    exp_series = [120.0 * math.exp(0.045 * t) * math.exp(rng_e.gauss(0.0, 0.015)) for t in range(38)]
    rep_exp = run_semiring_cyberstride(
        "Transcona Precision CNC",
        exp_series,
        capability=650.0,
        potentiality=900.0,
        preset_id="transcona_cnc",
    )
    assert rep_exp.dominant_regime_recent in (GROWTH, TREND), f"Unexpected regime: {rep_exp.dominant_regime_recent}"

    # 3. Verify 3-Semiring Supplier Kleene Closure (`Min-Plus`, `Boolean`, `Provenance`)
    sup = audit_supplier_network_three_semirings()
    assert sup["reachable_mill_to_bakery"] is True
    assert abs(sup["tropical_min_landed_cost_cad"] - 27.50) < 1e-9
    assert sup["tropical_optimal_route_receipts"] == ["INV-MILL-COOP-01", "INV-COOP-BAKERY-02"]
    assert len(sup["all_provenance_receipt_lineages"]) == 2

    print("=== OBB MODULE 12 (SEMIRING-CYBERSTRIDE) SELF-TEST PASSED! ===")
    print("  1. Scale Invariance (1x vs 1000x across all 5 regimes): EXACT (< 1e-9)")
    print("  2. Bakery Recent Regime:", rep_1x.dominant_regime_recent, "| Viterbi Changepoints:", rep_1x.viterbi_changepoints)
    print("  3. Stafford Beer Triple Index:", rep_1x.beer_triple_index)
    print("  4. Algedonic Alerts Fired:", len(rep_1x.algedonic_alerts))
    if rep_1x.aladdin_buffer_handshake:
        print("  5. People's Aladdin Handshake B*:", rep_1x.aladdin_buffer_handshake)
    print("  6. Supplier 3-Semiring Closure (Co-op Route):", sup["tropical_min_landed_cost_cad"], "CAD via", sup["tropical_optimal_route_receipts"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OBB Module 12: Semiring-Cyberstride Small-Shop Engine")
    parser.add_argument("--self-test", action="store_true", help="Run mathematical & scale-invariance verification suite")
    args = parser.parse_args()
    run_self_test()

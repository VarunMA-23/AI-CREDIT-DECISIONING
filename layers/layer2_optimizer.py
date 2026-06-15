"""
Layer 2 — Constraint Optimizer
Solves for feasible (loan_amount, interest_rate, tenure) combinations
given the risk profile, bank constraints, and applicant affordability.
"""
import numpy as np
from scipy.optimize import linprog
from itertools import product

# ── Bank constraint constants ─────────────────
RISK_THRESHOLD        = 0.15    # Max acceptable adjusted PD
PROFITABILITY_FLOOR   = 0.02    # Min net margin (rate - cost_of_funds - EL rate)
COST_OF_FUNDS         = 0.065   # Bank's funding cost (repo + spread)
CONCENTRATION_LIMIT   = 0.15    # Max cohort concentration (15%)

# Candidate grids
AMOUNT_STEPS  = [50_000, 100_000, 150_000, 200_000, 250_000, 300_000,
                 350_000, 400_000, 500_000, 600_000, 750_000, 1_000_000]
RATE_STEPS    = [0.095, 0.105, 0.110, 0.115, 0.120, 0.125,
                 0.130, 0.140, 0.150, 0.160, 0.175, 0.185]
TENURE_STEPS  = [12, 24, 36, 48, 60, 84]          # months


def emi(amount: float, annual_rate: float, tenure_months: int) -> float:
    """Standard EMI formula."""
    r = annual_rate / 12
    if r == 0:
        return amount / tenure_months
    return amount * r * (1 + r) ** tenure_months / ((1 + r) ** tenure_months - 1)


def is_feasible(amount: float, rate: float, tenure: int,
                risk_profile: dict, applicant: dict,
                cohort_concentration: float = 0.10,
                risk_threshold_override: float = None) -> tuple[bool, dict]:
    """
    Check all 4 constraints for a single (amount, rate, tenure) point.
    Returns (feasible: bool, constraint_values: dict)
    """
    pd  = risk_profile["pd_adjusted"]
    lgd = risk_profile["lgd"]

    # 1. Risk constraint: PD < threshold
    threshold = risk_threshold_override if risk_threshold_override is not None else RISK_THRESHOLD
    risk_ok = pd < threshold

    # 2. Margin constraint: rate - cost_of_funds - expected_loss_rate > floor
    el_rate  = pd * lgd
    margin   = rate - COST_OF_FUNDS - el_rate
    margin_ok = margin > PROFITABILITY_FLOOR

    # 3. Affordability: EMI < 40% of net monthly income
    monthly_emi   = emi(amount, rate, tenure)
    income        = applicant.get("income_monthly", 30000)
    existing_emi_ = applicant.get("existing_emi", 0)
    disposable    = income * 0.40
    afford_ok     = (monthly_emi + existing_emi_) < disposable

    # 4. Concentration: portfolio cohort < limit (mock check)
    concentration_ok = cohort_concentration < CONCENTRATION_LIMIT

    feasible = risk_ok and margin_ok and afford_ok and concentration_ok

    return feasible, {
        "pd":                round(pd, 4),
        "margin":            round(margin, 4),
        "monthly_emi":       round(monthly_emi, 2),
        "income_40pct":      round(disposable, 2),
        "cohort_conc":       cohort_concentration,
        "risk_ok":           risk_ok,
        "margin_ok":         margin_ok,
        "afford_ok":         afford_ok,
        "concentration_ok":  concentration_ok,
        "el_rate":           round(el_rate, 4),
    }


def run_optimizer(applicant: dict, risk_profile: dict,
                  cohort_concentration: float = 0.10,
                  max_requested_amount: float = None,
                  risk_threshold_override: float = None) -> dict:
    """
    Generate feasible frontier of (amount, rate, tenure) combinations.

    Returns:
      {
        "frontier":    [...],   # list of feasible points
        "branch":      "empty" | "single" | "multiple",
        "best_point":  {...} | None,
        "requested_amount": float,
      }
    """
    requested = max_requested_amount or applicant.get("loan_amount", 300000)

    # Only evaluate amounts up to what was requested
    candidate_amounts = [a for a in AMOUNT_STEPS if a <= requested]
    if not candidate_amounts:
        candidate_amounts = [AMOUNT_STEPS[0]]

    frontier = []

    for amount, rate, tenure in product(candidate_amounts, RATE_STEPS, TENURE_STEPS):
        feasible, constraints = is_feasible(
            amount, rate, tenure, risk_profile, applicant, cohort_concentration, risk_threshold_override
        )
        if feasible:
            el_rate = risk_profile["pd_adjusted"] * risk_profile["lgd"]
            margin  = rate - COST_OF_FUNDS - el_rate
            frontier.append({
                "amount":   amount,
                "rate":     rate,
                "tenure":   tenure,
                "margin":   round(margin, 4),
                "emi":      round(emi(amount, rate, tenure), 2),
                "pd":       risk_profile["pd_adjusted"],
                "constraints": constraints,
            })

    # Determine branch
    if len(frontier) == 0:
        branch = "empty"
        best   = None
    elif len(frontier) == 1 and frontier[0]["amount"] == requested:
        # Fast-Path ONLY if the single point fulfills the exact requested amount
        branch = "single"
        best   = frontier[0]
    else:
        # If multiple points OR a single point with a slashed amount, trigger negotiation
        branch = "multiple"
        # Default best = max amount at lowest rate (Sales-optimal)
        best = max(frontier, key=lambda p: (p["amount"], -p["rate"]))

    # Pareto-reduce for agent negotiation (keep non-dominated points)
    pareto = _pareto_filter(frontier) if len(frontier) > 1 else frontier

    return {
        "frontier":          pareto,
        "all_feasible_count": len(frontier),
        "branch":            branch,
        "best_point":        best,
        "requested_amount":  requested,
        "cohort_concentration": cohort_concentration,
    }


def _pareto_filter(points: list[dict], max_points: int = 8) -> list[dict]:
    """
    Keep Pareto-non-dominated points on (amount↑, rate↓, margin↑).
    Cap at max_points for agent negotiation efficiency.
    """
    if len(points) <= max_points:
        return points

    # Sort by amount desc, rate asc — pick diverse set
    sorted_pts = sorted(points, key=lambda p: (-p["amount"], p["rate"]))
    seen_combinations = set()
    pareto = []
    for p in sorted_pts:
        comb = (p["amount"], p["tenure"])
        if comb not in seen_combinations:
            seen_combinations.add(comb)
            pareto.append(p)
        if len(pareto) >= max_points:
            break

    return pareto if pareto else points[:max_points]

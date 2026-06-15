"""
Layer 1 — Scoring Layer (Python 3.14 compatible, pure numpy)
4.1 Credit Risk Model inference
4.2 Trust Score Module
4.3 Macro Adjustment Module
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.credit_model import predict_pd, compute_lgd_from_applicant
from memory.customer_memory import get_history

# ── 4.1 Credit Risk Model ──────────────────────

def compute_lgd(applicant: dict) -> float:
    """Loss Given Default — banking heuristic."""
    lgd = 0.45
    if applicant.get("has_collateral"):  lgd -= 0.20
    if applicant.get("has_guarantor"):   lgd -= 0.10
    if applicant.get("salary_account_linked"): lgd -= 0.05
    return max(0.10, round(lgd, 2))


def compute_ead(applicant: dict) -> float:
    return float(applicant.get("loan_amount", 300_000))


# ── 4.2 Trust Score ───────────────────────────

def compute_trust_score(customer_id: str, applicant: dict) -> float:
    """Trust Score 0–100 from customer history. Fresh applicants start at 50."""
    history = get_history(customer_id)
    if not history:
        return 50.0

    base = 50.0

    scores = [h["credit_score"] for h in history if h.get("credit_score")]
    if len(scores) >= 2:
        delta = scores[-1] - scores[0]
        base += min(20, max(-20, delta / 5))

    savings = [h["savings_balance"] for h in history if h.get("savings_balance") is not None]
    if len(savings) >= 2 and savings[0] > 0:
        growth = (savings[-1] - savings[0]) / savings[0]
        base += min(15, growth * 30)

    decisions  = [h["decision"] for h in history]
    base += decisions.count("APPROVED") * 5 - decisions.count("REJECTED") * 3

    return round(min(100, max(0, base)), 1)


# ── 4.3 Macro Adjustment Module ───────────────

MACRO_DATA = {
    "sector_unemployment": {
        "IT": 3.2, "Manufacturing": 7.1, "Retail": 8.5,
        "Healthcare": 2.8, "Construction": 10.2, "Finance": 3.5, "Default": 6.0,
    },
    "base_interest_rate": 6.5,
    "inflation_rate":     4.8,
    "credit_growth_rate": 14.2,
}

def compute_macro_premium(applicant: dict) -> float:
    sector       = applicant.get("sector", "Default")
    unemployment = MACRO_DATA["sector_unemployment"].get(sector, 6.0)
    inflation    = MACRO_DATA["inflation_rate"]
    premium = (unemployment - 5.0) * 0.005 + (inflation - 4.0) * 0.002
    return round(max(0.0, premium), 4)


# ── Layer 1 Master Function ───────────────────

def run_scoring(customer_id: str, applicant: dict) -> dict:
    pd_base       = predict_pd(applicant)
    macro_premium = compute_macro_premium(applicant)
    pd_adjusted   = min(0.99, pd_base + macro_premium)
    lgd           = compute_lgd(applicant)
    ead           = compute_ead(applicant)
    trust_score   = compute_trust_score(customer_id, applicant)
    sector        = applicant.get("sector", "Default")

    return {
        "pd_base":       pd_base,
        "macro_premium": macro_premium,
        "pd_adjusted":   round(pd_adjusted, 4),
        "lgd":           lgd,
        "ead":           ead,
        "expected_loss": round(pd_adjusted * lgd * ead, 2),
        "trust_score":   trust_score,
        "macro_data": {
            "sector":       sector,
            "unemployment": MACRO_DATA["sector_unemployment"].get(sector, 6.0),
            "base_rate":    MACRO_DATA["base_interest_rate"],
            "inflation":    MACRO_DATA["inflation_rate"],
        }
    }

"""
Layer 6 — Counterfactual Engine: The Acquisition Engine
Branch A: Improvement paths (SHAP-grounded, what would make original product approvable)
Branch B: Alternative product routing (instant cross-sell on rejection)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.credit_model import predict_pd, get_shap_approximation
from layers.layer2_optimizer import run_optimizer
from agents.base_agent import call_llm

# ── Adjacent Product Catalog ───────────────────
PRODUCT_CATALOG = [
    {
        "id":          "secured_credit_builder",
        "name":        "Secured Credit-Builder Loan",
        "max_amount":  150_000,
        "min_rate":    0.135,
        "max_tenure":  36,
        "risk_threshold_override": 0.18,  # More lenient — secured product
        "description": "Secured against FD/savings. Builds credit history.",
    },
    {
        "id":          "digital_savings",
        "name":        "SBI Digital Savings Account",
        "max_amount":  0,
        "min_rate":    0.0,
        "max_tenure":  0,
        "risk_threshold_override": 1.0,   # Always approvable
        "description": "Zero-balance savings account with digital banking.",
    },
    {
        "id":          "micro_loan",
        "name":        "SBI Micro Personal Loan",
        "max_amount":  50_000,
        "min_rate":    0.155,
        "max_tenure":  24,
        "risk_threshold_override": 0.15,
        "description": "Small-ticket unsecured loan for credit-building.",
    },
    {
        "id":          "salary_advance",
        "name":        "SBI Salary Advance",
        "max_amount":  100_000,
        "min_rate":    0.12,
        "max_tenure":  12,
        "risk_threshold_override": 0.12,
        "description": "Short-term advance against salary. Salary account required.",
    },
]

# Improvement action templates (Branch A)
IMPROVEMENT_ACTIONS = [
    {
        "id":           "add_guarantor",
        "label":        "Add a guarantor",
        "perturbation": {"has_guarantor": True},
        "feasibility":  lambda a: not a.get("has_guarantor", False),
        "effort":       "Medium",
        "timeline":     "Immediate",
    },
    {
        "id":           "reduce_amount",
        "label":        "Reduce requested amount by ₹75,000",
        "perturbation": {"loan_amount_delta": -75_000},
        "feasibility":  lambda a: a.get("loan_amount", 0) > 75_000,
        "effort":       "Low",
        "timeline":     "Immediate",
    },
    {
        "id":           "reduce_amount_half",
        "label":        "Reduce requested amount by half",
        "perturbation": {"loan_amount_delta_pct": -0.5},
        "feasibility":  lambda a: True,
        "effort":       "Low",
        "timeline":     "Immediate",
    },
    {
        "id":           "payoff_debt",
        "label":        "Pay off existing card/loan debt",
        "perturbation": {"existing_emi": 0, "num_existing_loans": 0},
        "feasibility":  lambda a: a.get("existing_emi", 0) > 0,
        "effort":       "High",
        "timeline":     "1–3 months",
    },
    {
        "id":           "add_collateral",
        "label":        "Pledge collateral (FD/property)",
        "perturbation": {"has_collateral": True},
        "feasibility":  lambda a: not a.get("has_collateral", False),
        "effort":       "Medium",
        "timeline":     "1 week",
    },
    {
        "id":           "savings_3mo",
        "label":        "Build 3-month consistent savings history (₹5K/mo)",
        "perturbation": {"savings_balance": lambda a: a.get("savings_balance", 0) + 15_000,
                         "repayment_history": lambda a: min(1.0, a.get("repayment_history", 0.8) + 0.1)},
        "feasibility":  lambda a: True,
        "effort":       "Medium",
        "timeline":     "3 months",
    },
    {
        "id":           "guarantor_savings",
        "label":        "Add guarantor + 3 months savings history",
        "perturbation": {"has_guarantor": True,
                         "savings_balance": lambda a: a.get("savings_balance", 0) + 15_000},
        "feasibility":  lambda a: not a.get("has_guarantor", False),
        "effort":       "High",
        "timeline":     "3 months",
    },
]

COUNTERFACTUAL_NARRATIVE_PROMPT = """You are a financial advisor at SBI helping a customer understand how to improve their loan eligibility.
Convert the computed probability improvements below into clear, encouraging, actionable advice.
Keep it concise (2-3 sentences per action). Use ₹ for currency. 
Focus on the concrete benefit and practical steps.
Do NOT make up probability numbers — only use the ones provided.
Respond in plain text with numbered recommendations."""


def _apply_perturbation(applicant: dict, perturbation: dict) -> dict:
    modified = dict(applicant)
    for k, v in perturbation.items():
        if k == "loan_amount_delta":
            modified["loan_amount"] = max(50_000, applicant.get("loan_amount", 300_000) + v)
        elif k == "loan_amount_delta_pct":
            modified["loan_amount"] = max(50_000, applicant.get("loan_amount", 300_000) * (1 + v))
        elif callable(v):
            modified[k] = v(applicant)
        else:
            modified[k] = v
    return modified


def run_branch_a(applicant: dict, risk_profile: dict) -> list[dict]:
    """
    Branch A: Compute improvement paths using SHAP-approximated sensitivity analysis.
    Re-runs optimizer with each perturbation to confirm frontier becomes non-empty.
    """
    base_pd      = risk_profile["pd_adjusted"]
    base_approval = base_pd < 0.08  # RISK_THRESHOLD

    improvements = []

    for action in IMPROVEMENT_ACTIONS:
        try:
            if not action["feasibility"](applicant):
                continue

            perturbed    = _apply_perturbation(applicant, action["perturbation"])
            perturbed_pd = predict_pd(perturbed)
            macro_prem   = risk_profile.get("macro_premium", 0)
            perturbed_pd_adj = min(0.99, perturbed_pd + macro_prem)

            perturbed_risk = {**risk_profile, "pd_adjusted": perturbed_pd_adj}
            opt_result     = run_optimizer(perturbed, perturbed_risk,
                                           max_requested_amount=applicant.get("loan_amount"))

            frontier_non_empty = len(opt_result.get("frontier", [])) > 0
            pd_lift = base_pd - perturbed_pd_adj
            approval_probability = max(5, min(99, int((1 - perturbed_pd_adj / 0.20) * 100)))

            improvements.append({
                "action":               action["label"],
                "action_id":            action["id"],
                "effort":               action["effort"],
                "timeline":             action["timeline"],
                "pd_before":            round(base_pd, 4),
                "pd_after":             round(perturbed_pd_adj, 4),
                "pd_lift":              round(pd_lift, 4),
                "approval_probability": approval_probability,
                "frontier_non_empty":   frontier_non_empty,
                "recommended_terms":    opt_result.get("best_point"),
            })
        except Exception:
            continue

    # Sort by probability lift descending
    improvements.sort(key=lambda x: x["pd_lift"], reverse=True)
    return improvements[:6]   # Top 6


def run_branch_b(applicant: dict, risk_profile: dict) -> list[dict]:
    """
    Branch B: Check alternative products for immediate approval.
    """
    available = []

    for product in PRODUCT_CATALOG:
        # Digital savings — always available
        if product["risk_threshold_override"] == 1.0:
            available.append({
                "product_id":   product["id"],
                "product_name": product["name"],
                "status":       "APPROVED NOW",
                "description":  product["description"],
                "terms":        None,
                "reason":       "No credit risk assessment required",
            })
            continue

        # Check salary advance requirement
        if product["id"] == "salary_advance" and not applicant.get("salary_account_linked"):
            continue

        # Re-run optimizer with product constraints
        prod_applicant = {**applicant, "loan_amount": min(
            applicant.get("loan_amount", 300_000),
            product["max_amount"]
        )}
        if product["max_amount"] == 0:
            continue

        prod_risk = {
            **risk_profile,
            "pd_adjusted": risk_profile["pd_adjusted"],
            "lgd": max(0.10, risk_profile["lgd"] - (0.20 if product["id"] == "secured_credit_builder" else 0)),
        }

        result = run_optimizer(prod_applicant, prod_risk,
                               max_requested_amount=product["max_amount"],
                               risk_threshold_override=product["risk_threshold_override"])

        if result["branch"] != "empty":
            best = result["best_point"]
            available.append({
                "product_id":   product["id"],
                "product_name": product["name"],
                "status":       "APPROVED NOW",
                "description":  product["description"],
                "terms":        {
                    "amount": best["amount"],
                    "rate":   best["rate"],
                    "tenure": best["tenure"],
                    "emi":    best["emi"],
                } if best else None,
                "reason":       "Feasible under product-specific risk parameters",
            })
        else:
            available.append({
                "product_id":   product["id"],
                "product_name": product["name"],
                "status":       "NOT ELIGIBLE",
                "description":  product["description"],
                "terms":        None,
                "reason":       "Risk profile exceeds product limits",
            })

    return available


def generate_narrative(branch_a: list[dict], applicant: dict) -> str:
    """Use Gemini to translate computed deltas into natural language."""
    items = "\n".join(
        f"{i+1}. {b['action']}: PD {b['pd_before']:.2%} → {b['pd_after']:.2%} "
        f"(approval probability ~{b['approval_probability']}%) | Effort: {b['effort']} | Timeline: {b['timeline']}"
        for i, b in enumerate(branch_a[:4])
    )
    user_msg = (
        f"Customer profile: {applicant.get('name', 'Applicant')}, "
        f"requesting ₹{applicant.get('loan_amount', 0):,.0f} personal loan.\n\n"
        f"Computed improvement options:\n{items}"
    )
    try:
        return call_llm(COUNTERFACTUAL_NARRATIVE_PROMPT, user_msg, temperature=0.4)
    except Exception as e:
        return f"[Narrative generation unavailable: {str(e)[:60]}]"


def run_counterfactual(applicant: dict, risk_profile: dict,
                       final_decision: str) -> dict:
    """
    Run both branches. Returns full counterfactual result.
    final_decision: 'APPROVED' | 'REJECTED' | 'CONDITIONAL'
    """
    branch_a = run_branch_a(applicant, risk_profile)
    branch_b = run_branch_b(applicant, risk_profile)
    narrative = generate_narrative(branch_a, applicant)

    approved_b = [p for p in branch_b if p["status"] == "APPROVED NOW"]

    return {
        "final_decision": final_decision,
        "branch_a":       branch_a,
        "branch_b":       branch_b,
        "branch_b_instant_approvals": len(approved_b),
        "narrative":      narrative,
        "base_pd":        risk_profile["pd_adjusted"],
        "acquisition_note": (
            f"Rejection converted: {len(approved_b)} alternative product(s) immediately approvable"
            if final_decision == "REJECTED" and approved_b
            else None
        ),
    }

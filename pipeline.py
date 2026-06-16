"""
Main Pipeline Orchestrator — runs all 7 layers in sequence.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from layers.layer0_gate        import run_compliance, run_fraud
from layers.layer1_scoring     import run_scoring
from layers.layer2_optimizer   import run_optimizer
from layers.layer3_negotiation import run_negotiation, run_shadow_opinion_only
from layers.layer4_stress      import run_stress_test
from layers.layer5_routing     import run_decision_routing
from layers.layer6_counterfactual import run_counterfactual
from layers.layer7_journey     import run_journey_agent
from memory.customer_memory    import save_application
from data.credit_model         import save_calibrated_weights


def ensure_model():
    """Ensure model weights exist on first run."""
    weights_path = os.path.join(os.path.dirname(__file__), "models", "lr_weights.json")
    if not os.path.exists(weights_path):
        save_calibrated_weights()


def run_pipeline(applicant: dict, callbacks: dict = None) -> dict:
    """
    Full pipeline: Layers 0 → 7.

    callbacks: optional dict of {layer_name: callable(result)} for UI updates.
    """
    cb = callbacks or {}

    def emit(name: str, data):
        if name in cb:
            cb[name](data)
        return data

    customer_id = applicant.get("customer_id", "UNKNOWN")
    result = {"customer_id": customer_id, "applicant": applicant}

    # ── Layer 0: Gate ─────────────────────────
    compliance = emit("compliance", run_compliance(applicant))
    result["compliance"] = compliance

    if compliance["status"] == "FAIL":
        result["final_decision"] = "REJECTED"
        result["rejection_stage"] = "COMPLIANCE"
        result["rejection_reason"] = compliance["reason"]
        _save_and_return(customer_id, applicant, result)
        return result

    fraud = emit("fraud", run_fraud(applicant))
    result["fraud"] = fraud

    if fraud["flag"] == "reject":
        result["final_decision"] = "REJECTED"
        result["rejection_stage"] = "FRAUD"
        result["rejection_reason"] = f"Fraud score {fraud['fraud_score']}/100 — application terminated"
        _save_and_return(customer_id, applicant, result)
        return result

    # ── Layer 1: Scoring ──────────────────────
    risk_profile = emit("scoring", run_scoring(customer_id, applicant))
    result["risk_profile"] = risk_profile

    # ── Layer 2: Optimizer ────────────────────
    optimizer = emit("optimizer", run_optimizer(applicant, risk_profile))
    result["optimizer"] = optimizer

    branch = optimizer["branch"]

    # ── Fast-path / Negotiation branch ────────
    selected_point   = None
    negotiation_res  = None
    shadow_opinion   = None

    if branch == "empty":
        # Rejected by optimizer
        result["final_decision"] = "REJECTED"
        result["rejection_stage"] = "OPTIMIZER"
        result["rejection_reason"] = "No feasible (amount, rate, tenure) combination satisfies all constraints"
        selected_point  = None
        shadow_opinion  = run_shadow_opinion_only(optimizer, {"amount": 0, "rate": 0, "tenure": 0})

    elif branch == "single":
        # Fast-path
        selected_point = optimizer["best_point"]
        result["fast_path"] = True
        shadow_opinion = emit("shadow", run_shadow_opinion_only(optimizer, selected_point))

    else:
        # Negotiation
        neg = emit("negotiation", run_negotiation(optimizer, applicant, risk_profile))
        result["negotiation"] = neg
        negotiation_res = neg

        if neg["result"] == "vetoed":
            result["final_decision"] = "REJECTED"
            result["rejection_stage"] = "PORTFOLIO_VETO"
            result["rejection_reason"] = neg.get("veto_reason", "Portfolio concentration breach")
            selected_point  = None
        else:
            selected_point = neg.get("selected_point")
        shadow_opinion = neg.get("shadow_opinion")

    result["selected_point"]  = selected_point
    result["shadow_opinion"]  = shadow_opinion

    # ── Layer 4: Stress Test (if we have a point) ──
    stress = None
    if selected_point:
        stress = emit("stress", run_stress_test(applicant, risk_profile, selected_point))
        result["stress_test"] = stress

        # ── Layer 5: Decision Routing ─────────────
        routing = emit("routing", run_decision_routing(stress, negotiation_res, risk_profile))
        result["routing"] = routing

        if routing["route"] == "AUTO_EXECUTE":
            result["final_decision"] = "APPROVED"
        else:
            result["final_decision"] = "CONDITIONAL"  # Human underwriter decides

    # ── Layer 6: Counterfactual Engine ─────────
    final_dec = result.get("final_decision", "REJECTED")
    counterfactual = emit("counterfactual", run_counterfactual(applicant, risk_profile, final_dec))
    result["counterfactual"] = counterfactual

    # ── Layer 7: Customer Journey Agent ────────
    journey = emit("journey", run_journey_agent(
        final_dec, applicant, counterfactual, risk_profile["trust_score"]
    ))
    result["journey"] = journey

    # ── Persist to Customer Memory ─────────────
    _save_and_return(customer_id, applicant, result)
    return result


def _save_and_return(customer_id, applicant, result):
    try:
        save_application(
            customer_id    = customer_id,
            decision       = result.get("final_decision", "UNKNOWN"),
            reason         = result.get("rejection_reason", ""),
            credit_score   = applicant.get("credit_score", 0),
            income_monthly = applicant.get("income_monthly", 0),
            savings_balance= applicant.get("savings_balance", 0),
            loan_amount    = applicant.get("loan_amount", 0),
            trust_score    = result.get("risk_profile", {}).get("trust_score", 0),
        )
    except Exception:
        pass

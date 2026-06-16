"""
Layer 5 — Decision Routing
Routes to AUTO-EXECUTE or HUMAN-UNDERWRITER based on:
- Stress test resilience
- Negotiation consensus
- Risk threshold
"""

ESCALATION_PD_THRESHOLD = 0.06   # PD above this → always human review


def run_decision_routing(stress_result: dict, negotiation_result: dict,
                          risk_profile: dict) -> dict:
    """
    Determine final routing: AUTO_EXECUTE | HUMAN_UNDERWRITER
    """
    reasons = []
    escalate = False

    # Condition 1: High resilience + consensus → auto-execute
    routing         = stress_result.get("routing", "HUMAN_REVIEW")
    negotiation_res = negotiation_result.get("result", "consensus") if negotiation_result else "fast_path"
    pd_adjusted     = risk_profile.get("pd_adjusted", 0)

    # Force escalation conditions
    if routing == "HUMAN_REVIEW":
        escalate = True
        reasons.append("Stress test resilience LOW — requires underwriter review")

    if negotiation_res == "escalate":
        escalate = True
        reasons.append("Agents could not reach consensus after max negotiation rounds")

    if pd_adjusted > ESCALATION_PD_THRESHOLD:
        escalate = True
        reasons.append(f"PD {pd_adjusted:.2%} exceeds escalation threshold {ESCALATION_PD_THRESHOLD:.2%}")

    if negotiation_res == "vetoed":
        escalate = True
        reasons.append("Portfolio Agent exercised veto — requires underwriter sign-off")

    if not escalate and routing == "AUTO_EXECUTE":
        decision_route = "AUTO_EXECUTE"
        route_label    = "✅ AUTO-EXECUTE"
        route_note     = "High resilience + agent consensus + risk within threshold → instant decision"
    elif not escalate and routing == "BORDERLINE":
        escalate = True
        reasons.append("Borderline stress resilience — flagged for human review")
        decision_route = "HUMAN_UNDERWRITER"
        route_label    = "👤 HUMAN UNDERWRITER"
        route_note     = "Borderline case — system recommends approval, underwriter must confirm"
    else:
        decision_route = "HUMAN_UNDERWRITER"
        route_label    = "👤 HUMAN UNDERWRITER"
        route_note     = "Receives full structured debate log + system recommendation"

    return {
        "route":        decision_route,
        "route_label":  route_label,
        "route_note":   route_note,
        "escalated":    escalate,
        "reasons":      reasons,
        "pd_adjusted":  pd_adjusted,
        "resilience":   stress_result.get("resilience_score", 0),
    }

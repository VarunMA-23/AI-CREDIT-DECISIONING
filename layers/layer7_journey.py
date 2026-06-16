"""
Layer 7 — Customer Journey Agent: The Re-Acquisition Loop
Approved path: onboarding → cross-sell → investment
Rejected path: education → savings challenge → reapply → Month 6 recheck
Trust-score-triggered early outreach logic.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.base_agent import call_llm

EARLY_OUTREACH_THRESHOLD = 65.0   # Trust score crossing point for early recheck

JOURNEY_SYSTEM_PROMPT = """You are the Customer Journey Manager at SBI.
Based on the loan decision and customer profile, create a personalized engagement sequence.
Be specific, warm, and actionable. Reference actual numbers from the customer's profile.
Keep each touchpoint to 1-2 sentences.
Respond in plain text."""


# ── Pre-built journey templates ─────────────────

APPROVED_JOURNEY_TEMPLATE = [
    {"day": 1,  "event": "Loan Onboarding",
     "action": "Welcome call + digital onboarding. Loan disbursed to account."},
    {"day": 7,  "event": "Auto-Pay Setup",
     "action": "Prompt customer to link salary account for auto-EMI. Offer 0.05% rate reduction."},
    {"day": 30, "event": "Credit Score Tracker",
     "action": "Activate SBI Credit Score Monitor. Share that on-time EMI will improve score."},
    {"day": 60, "event": "Cross-Sell: Insurance",
     "action": "Offer term life / loan protection insurance tailored to loan amount."},
    {"day": 90, "event": "Investment Recommendation",
     "action": "Based on savings profile, recommend SBI Mutual Fund SIP (₹1,000/mo)."},
]

REJECTED_JOURNEY_TEMPLATE = [
    {"week": 1,  "event": "Credit Education",
     "action": "Send personalized 'Improve Your Credit' guide. Highlight top 2 improvement actions."},
    {"month": 1, "event": "Savings Challenge",
     "action": "Launch '3-Month Savings Challenge' tied to Branch A improvement path."},
    {"month": 3, "event": "Progress Check-in",
     "action": "Review credit score improvement. Send reapplication reminder if threshold met."},
    {"month": 6, "event": "Automatic Eligibility Recheck",
     "action": "Re-enter pipeline at Layer 1 automatically. Zero manual effort required."},
]


def _generate_personalized_journey(decision: str, applicant: dict,
                                    counterfactual: dict, trust_score: float) -> str:
    """Use Gemini to personalize the journey sequence."""
    top_action = ""
    if counterfactual and counterfactual.get("branch_a"):
        top_action = counterfactual["branch_a"][0]["action"]

    user_msg = f"""Customer: {applicant.get('name', 'Applicant')}
Decision: {decision}
Loan Amount: ₹{applicant.get('loan_amount', 0):,.0f}
Monthly Income: ₹{applicant.get('income_monthly', 0):,.0f}
Trust Score: {trust_score}/100
Top Improvement Action: {top_action or 'N/A'}
Savings Balance: ₹{applicant.get('savings_balance', 0):,.0f}

Create a personalized 6-step engagement journey for this customer. 
{"Focus on re-engagement, credit building, and the path back to approval." if decision == "REJECTED" else "Focus on loan servicing, cross-sell, and growing their relationship with SBI."}"""

    try:
        return call_llm(JOURNEY_SYSTEM_PROMPT, user_msg, temperature=0.5)
    except Exception as e:
        return f"[Journey generation unavailable: {str(e)[:60]}]"


def check_early_outreach_trigger(customer_id: str, current_trust_score: float,
                                  previous_trust_score: float,
                                  last_decision: str) -> dict:
    """
    Check if trust score crossing threshold triggers early eligibility recheck.
    """
    if last_decision != "REJECTED":
        return {"triggered": False, "reason": "Not a rejected applicant"}

    if previous_trust_score >= EARLY_OUTREACH_THRESHOLD:
        return {"triggered": False, "reason": "Already above threshold previously"}

    if current_trust_score >= EARLY_OUTREACH_THRESHOLD:
        return {
            "triggered":   True,
            "reason":      f"Trust Score crossed threshold: {previous_trust_score:.0f} → {current_trust_score:.0f} (≥{EARLY_OUTREACH_THRESHOLD})",
            "action":      "Eligibility recheck triggered EARLY — customer re-enters Layer 1 pipeline",
            "note":        "Proactive outreach — no manual sales effort required",
        }

    return {
        "triggered": False,
        "reason":    f"Trust Score {current_trust_score:.0f} still below threshold {EARLY_OUTREACH_THRESHOLD}",
    }


def run_journey_agent(final_decision: str, applicant: dict,
                       counterfactual: dict, trust_score: float) -> dict:
    """
    Build complete customer journey sequence.
    """
    is_approved = final_decision in ("APPROVED", "CONDITIONAL", "AUTO_APPROVED")
    is_rejected = final_decision == "REJECTED"

    # Build template journey
    if is_approved:
        template = APPROVED_JOURNEY_TEMPLATE
    else:
        template = REJECTED_JOURNEY_TEMPLATE

    # Personalized narrative via Gemini
    narrative = _generate_personalized_journey(
        final_decision, applicant, counterfactual, trust_score
    )

    # Trust-triggered early outreach check (demo: simulate prior trust score 42)
    prior_trust = max(0, trust_score - 18)   # Simulate improvement in demo
    outreach_trigger = check_early_outreach_trigger(
        applicant.get("customer_id", "UNKNOWN"),
        current_trust_score  = trust_score,
        previous_trust_score = prior_trust,
        last_decision        = final_decision,
    )

    # Cross-sell note for approved customers
    cross_sell_note = None
    if is_approved and counterfactual:
        approved_alternatives = [
            p for p in counterfactual.get("branch_b", [])
            if p["status"] == "APPROVED NOW" and p.get("terms")
        ]
        if approved_alternatives:
            cross_sell_note = (
                f"Also eligible for: {', '.join(p['product_name'] for p in approved_alternatives[:2])}"
            )

    return {
        "decision":           final_decision,
        "template_journey":   template,
        "personalized_plan":  narrative,
        "trust_score":        trust_score,
        "early_outreach":     outreach_trigger,
        "cross_sell_note":    cross_sell_note,
        "theme_mapping": {
            "Digital Adoption":    "Onboarding sequence, auto-pay, cross-sell",
            "Digital Engagement":  "Credit education, savings challenge",
            "Customer Acquisition":"Reapply reminder, eligibility recheck, trust-triggered outreach",
        },
    }

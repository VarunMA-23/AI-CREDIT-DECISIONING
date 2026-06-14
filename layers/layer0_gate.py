"""
Layer 0 — Gate Layer
3.1 Compliance Agent (deterministic rule engine)
3.2 Fraud Agent (rule-based + Gemini LLM for narrative consistency)
"""
from agents.base_agent import call_llm_json


# ──────────────────────────────────────────────
# 3.1 Compliance Agent
# ──────────────────────────────────────────────

COMPLIANCE_RULES = {
    "min_age": 21,
    "max_age": 70,
    "required_kyc_fields": ["name", "dob", "pan", "address", "income_monthly"],
    "required_residency": ["IN"],
}


def run_compliance(applicant: dict) -> dict:
    """
    Returns: {status: PASS|FAIL, reason: str, checks: dict}
    """
    checks = {}
    failures = []

    # KYC completeness
    for field in COMPLIANCE_RULES["required_kyc_fields"]:
        present = bool(applicant.get(field))
        checks[f"kyc_{field}"] = present
        if not present:
            failures.append(f"Missing KYC field: {field}")

    # Age check
    age = applicant.get("age", 0)
    age_ok = COMPLIANCE_RULES["min_age"] <= age <= COMPLIANCE_RULES["max_age"]
    checks["age_eligible"] = age_ok
    if not age_ok:
        failures.append(f"Age {age} out of eligible range 21–70")

    # Residency check
    residency = applicant.get("residency", "IN")
    res_ok = residency in COMPLIANCE_RULES["required_residency"]
    checks["residency"] = res_ok
    if not res_ok:
        failures.append(f"Residency '{residency}' not eligible")

    # Sanctions check (mock — real would hit an external API)
    sanctioned = applicant.get("_sanctioned", False)
    checks["sanctions_clear"] = not sanctioned
    if sanctioned:
        failures.append("Applicant appears on sanctions/watchlist")

    # Self-Employed Vintage check
    emp_type = applicant.get("employment_type", "")
    emp_years = applicant.get("employment_years", 0)
    vintage_ok = not (emp_type == "Self-Employed" and emp_years < 2.0)
    checks["business_vintage_ok"] = vintage_ok
    if not vintage_ok:
        failures.append(f"Self-employed vintage ({emp_years} years) does not meet minimum bank criteria of 2.0 years")

    status = "FAIL" if failures else "PASS"
    return {
        "status": status,
        "reason": "; ".join(failures) if failures else "All compliance checks passed",
        "checks": checks,
    }


# ──────────────────────────────────────────────
# 3.2 Fraud Agent
# ──────────────────────────────────────────────

FRAUD_SYSTEM_PROMPT = """You are a fraud detection specialist at a bank. 
You will be given a loan application's narrative summary and must assess document/narrative consistency.
Check for:
- Income declared vs estimated from employment type/sector
- Address/name consistency patterns  
- Any suspicious application characteristics

Respond ONLY with valid JSON in this format:
{
  "narrative_fraud_score": <0-100>,
  "flags": ["list", "of", "concerns"],
  "reasoning": "brief explanation"
}
Score 0=clearly legitimate, 100=clearly fraudulent."""


def run_fraud(applicant: dict) -> dict:
    """
    Hybrid fraud check: deterministic velocity/consistency rules + LLM narrative check.
    Returns: {fraud_score: 0-100, flag: clean|flagged|reject, details: dict}
    """
    score = 0
    flags = []

    # Rule 1: Application velocity (multiple apps in short window)
    recent_apps = applicant.get("recent_applications_30d", 0)
    if recent_apps >= 5:
        score += 40
        flags.append(f"High application velocity: {recent_apps} apps in 30 days")
    elif recent_apps >= 3:
        score += 20
        flags.append(f"Elevated application velocity: {recent_apps} apps in 30 days")

    # Rule 2: Declared income vs derived income discrepancy
    declared_income = applicant.get("income_monthly", 0)
    bureau_income   = applicant.get("bureau_income_estimate", declared_income)
    if bureau_income > 0:
        discrepancy = abs(declared_income - bureau_income) / bureau_income
        if discrepancy > 0.40:
            score += 35
            flags.append(f"Income discrepancy: declared ₹{declared_income:,.0f} vs bureau ₹{bureau_income:,.0f}")
        elif discrepancy > 0.20:
            score += 15
            flags.append(f"Mild income discrepancy: {discrepancy:.0%}")

    # Rule 3: Requested amount >> income
    loan_amount = applicant.get("loan_amount", 0)
    if declared_income > 0 and loan_amount / declared_income > 20:
        score += 20
        flags.append(f"Loan amount {loan_amount/declared_income:.1f}x monthly income — unusually high")

    # Rule 4: LLM narrative consistency check
    narrative_score = 0
    llm_flags = []
    try:
        user_msg = f"""Loan Application:
Name: {applicant.get('name', 'N/A')}
Age: {applicant.get('age', 'N/A')}
Employment: {applicant.get('employment_type', 'N/A')} in {applicant.get('sector', 'N/A')}
Monthly Income: ₹{applicant.get('income_monthly', 0):,.0f}
Loan Requested: ₹{applicant.get('loan_amount', 0):,.0f} for {applicant.get('loan_purpose', 'N/A')}
Credit Score: {applicant.get('credit_score', 'N/A')}
Savings: ₹{applicant.get('savings_balance', 0):,.0f}"""

        result = call_llm_json(FRAUD_SYSTEM_PROMPT, user_msg)
        if not result.get("parse_error"):
            narrative_score = result.get("narrative_fraud_score", 0)
            llm_flags = result.get("flags", [])
        else:
            # Bug Fix: Parse error should default to suspicious, not completely safe
            narrative_score = 50
            llm_flags = ["System Warning: Fraud LLM Parse Error - Defaulting to Suspicious"]
    except Exception:
        # Bug Fix: Exception should default to suspicious
        narrative_score = 50
        llm_flags = ["System Warning: Fraud LLM Exception - Defaulting to Suspicious"]

    # Weighted combination
    combined = min(100, score * 0.6 + narrative_score * 0.4)
    all_flags = flags + llm_flags

    if combined > 80:
        flag = "reject"
    elif combined >= 40:
        flag = "flagged"
    else:
        flag = "clean"

    return {
        "fraud_score": round(combined, 1),
        "flag": flag,
        "rule_score": score,
        "llm_narrative_score": narrative_score,
        "flags": all_flags,
    }

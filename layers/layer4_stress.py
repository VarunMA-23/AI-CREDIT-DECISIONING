"""
Layer 4 — Stress Test Layer
Re-runs credit risk model under 3 perturbed scenarios.
Returns resilience score and routing recommendation.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.credit_model import predict_pd
from layers.layer2_optimizer import run_optimizer, RISK_THRESHOLD

STRESS_SCENARIOS = [
    {"name": "Interest Rate +2%",      "rate_delta": 0.02, "income_delta": 0.0,  "unemployment_premium": 0.0},
    {"name": "Income Shock -20%",      "rate_delta": 0.0,  "income_delta": -0.20, "unemployment_premium": 0.0},
    {"name": "Sector Unemployment",    "rate_delta": 0.0,  "income_delta": 0.0,  "unemployment_premium": 0.015},
]


def run_stress_test(applicant: dict, risk_profile: dict, selected_point: dict) -> dict:
    """
    Stress-test the selected decision under 3 adverse scenarios.
    Returns resilience assessment.
    """
    base_pd      = risk_profile["pd_adjusted"]
    results      = []
    worst_pd     = base_pd
    failures     = 0

    for scenario in STRESS_SCENARIOS:
        # Perturb applicant
        stressed_applicant = dict(applicant)
        if scenario["income_delta"] != 0:
            stressed_applicant["income_monthly"] = (
                applicant.get("income_monthly", 30_000) * (1 + scenario["income_delta"])
            )

        # Predict stressed PD
        stressed_pd = predict_pd(stressed_applicant)
        stressed_pd += scenario["unemployment_premium"]
        stressed_pd = min(0.99, stressed_pd)

        # Check if selected point still feasible under stress
        from layers.layer2_optimizer import is_feasible
        stressed_rate = selected_point["rate"] + scenario["rate_delta"]
        feasible, _ = is_feasible(
            selected_point["amount"],
            stressed_rate,
            selected_point["tenure"],
            {**risk_profile, "pd_adjusted": stressed_pd},
            stressed_applicant,
        )

        survives = feasible and (stressed_pd < RISK_THRESHOLD * 1.5)
        if not survives:
            failures += 1
        if stressed_pd > worst_pd:
            worst_pd = stressed_pd

        results.append({
            "scenario":    scenario["name"],
            "stressed_pd": round(stressed_pd, 4),
            "survives":    survives,
            "pd_delta":    round(stressed_pd - base_pd, 4),
        })

    # Resilience score: 0-100
    survival_rate = (len(STRESS_SCENARIOS) - failures) / len(STRESS_SCENARIOS)
    pd_headroom   = max(0, RISK_THRESHOLD - worst_pd) / RISK_THRESHOLD
    resilience    = round((survival_rate * 0.7 + pd_headroom * 0.3) * 100, 1)

    if resilience >= 70:
        routing = "AUTO_EXECUTE"
        label   = "HIGH"
    elif resilience >= 40:
        routing = "BORDERLINE"
        label   = "BORDERLINE"
    else:
        routing = "HUMAN_REVIEW"
        label   = "LOW"

    return {
        "scenarios":       results,
        "resilience_score": resilience,
        "resilience_label": label,
        "routing":         routing,
        "worst_pd":        round(worst_pd, 4),
        "failures":        failures,
        "base_pd":         base_pd,
    }

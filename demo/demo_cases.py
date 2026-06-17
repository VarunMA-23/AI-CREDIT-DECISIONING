"""
Demo Cases — 4 pre-built applicant profiles matching the architecture's demo script (Section 14).
"""

DEMO_CASES = {
    "1": {
        "label":       "Case 1 — Fast-Path Approval",
        "description": "Single optimal frontier point. No negotiation. Decision in <30s.",
        "theme":       "Demonstrates: optimizer doing real work, efficiency",
        "applicant": {
            "customer_id":         "CUST-00101",
            "name":                "Rajesh Kumar",
            "age":                 38,
            "dob":                 "1988-03-15",
            "pan":                 "ABCPK1234D",
            "address":             "12 MG Road, Bengaluru",
            "residency":           "IN",
            "sector":              "IT",
            "employment_type":     "Salaried",
            "employment_years":    8,
            "income_monthly":      85_000,
            "existing_emi":        8_000,
            "num_existing_loans":  1,
            "savings_balance":     250_000,
            "credit_score":        748,
            "repayment_history":   0.96,
            "has_guarantor":       False,
            "has_collateral":      False,
            "salary_account_linked": True,
            "loan_amount":         350_000,
            "loan_tenure":         36,
            "loan_purpose":        "Home renovation",
            "recent_applications_30d": 0,
            "bureau_income_estimate":  88_000,
        }
    },
    "2": {
        "label":       "Case 2 — Negotiation Case",
        "description": "Multiple frontier points. Sales vs Risk genuine disagreement. Portfolio Agent veto demo.",
        "theme":       "Demonstrates: multi-stakeholder negotiation, regulatory-grade explainability",
        "applicant": {
            "customer_id":         "CUST-00202",
            "name":                "Priya Sharma",
            "age":                 31,
            "dob":                 "1995-07-22",
            "pan":                 "BCDPS5678E",
            "address":             "45 Park Street, Mumbai",
            "residency":           "IN",
            "sector":              "Finance",
            "employment_type":     "Salaried",
            "employment_years":    5,
            "income_monthly":      65_000,
            "existing_emi":        12_000,
            "num_existing_loans":  2,
            "savings_balance":     120_000,
            "credit_score":        692,
            "repayment_history":   0.88,
            "has_guarantor":       False,
            "has_collateral":      False,
            "salary_account_linked": True,
            "loan_amount":         400_000,
            "loan_tenure":         48,
            "loan_purpose":        "Wedding expenses",
            "recent_applications_30d": 1,
            "bureau_income_estimate":  67_000,
        }
    },
    "3": {
        "label":       "Case 3 — Rejection → Improvement Path (Branch A)",
        "description": "Empty optimizer frontier. Counterfactual Engine shows ranked improvement paths. 6-month re-acquisition journey.",
        "theme":       "Demonstrates: 'No becomes Not Yet' — scheduled re-acquisition",
        "applicant": {
            "customer_id":         "CUST-00231",
            "name":                "Amit Verma",
            "age":                 26,
            "dob":                 "2000-01-10",
            "pan":                 "CDQAV9012F",
            "address":             "88 Civil Lines, Delhi",
            "residency":           "IN",
            "sector":              "Retail",
            "employment_type":     "Self-Employed",
            "employment_years":    1.5,
            "income_monthly":      22_000,
            "existing_emi":        9_500,
            "num_existing_loans":  3,
            "savings_balance":     8_000,
            "credit_score":        578,
            "repayment_history":   0.52,
            "has_guarantor":       False,
            "has_collateral":      False,
            "salary_account_linked": False,
            "loan_amount":         400_000,
            "loan_tenure":         48,
            "loan_purpose":        "Business expansion",
            "recent_applications_30d": 2,
            "bureau_income_estimate":  20_000,
        }
    },
    "4": {
        "label":       "Case 4 — Rejection → Instant Cross-Sell (Branch B)",
        "description": "Same rejection as Case 3 but Branch B shows secured credit-builder loan immediately approvable. Sales shadow opinion quantifies acquisition-vs-risk trade-off.",
        "theme":       "Demonstrates: rejection converted into live sale in same session",
        "applicant": {
            "customer_id":         "CUST-00232",
            "name":                "Sneha Pillai",
            "age":                 29,
            "dob":                 "1997-04-05",
            "pan":                 "DEFSP3456G",
            "address":             "22 Anna Salai, Chennai",
            "residency":           "IN",
            "sector":              "Retail",
            "employment_type":     "Salaried",
            "employment_years":    2,
            "income_monthly":      28_000,
            "existing_emi":        7_000,
            "num_existing_loans":  2,
            "savings_balance":     35_000,   # Some savings → secured product feasible
            "credit_score":        601,
            "repayment_history":   0.65,
            "has_guarantor":       False,
            "has_collateral":      True,     # Has FD → secured product unlocked
            "salary_account_linked": True,
            "loan_amount":         300_000,
            "loan_tenure":         36,
            "loan_purpose":        "Education loan gap funding",
            "recent_applications_30d": 1,
            "bureau_income_estimate":  27_000,
        }
    },
}


def get_case(case_id: str) -> dict:
    return DEMO_CASES.get(str(case_id))


def list_cases() -> list[dict]:
    return [
        {
            "id":          k,
            "label":       v["label"],
            "description": v["description"],
            "theme":       v["theme"],
        }
        for k, v in DEMO_CASES.items()
    ]

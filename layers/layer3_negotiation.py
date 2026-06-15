"""
Layer 3 — Department Agent Negotiation
All 5 agents + Master Coordinator FSM.
Sales Agent shadow opinion runs on 100% of applications.
"""
from agents.base_agent import call_llm_json
from memory.agent_memory import get_context, log_observation

# ── Market Benchmark feed (mock) ──────────────
MARKET_BENCHMARK = {
    "personal_loan_avg_rate": 0.108,     # 10.8%
    "home_loan_avg_rate":     0.085,
    "car_loan_avg_rate":      0.095,
    "credit_builder_avg_rate":0.145,
}

# ──────────────────────────────────────────────
# Agent system prompts
# ──────────────────────────────────────────────

RISK_PROMPT = """You are the Credit Risk Department representative at SBI.
Your mandate: minimize Probability of Default and credit exposure.
You prefer frontier points with lowest PD and most conservative loan terms.
Prior cohort observations (your memory):
{memory}

Given the frontier points, pick your PREFERRED point and explain why.
Respond in JSON:
{{
  "preferred_index": <int, 0-based index into frontier>,
  "claim": "Approve at ₹X at Y%, Z months",
  "evidence": "PD=X%, margin=Y%, EMI=₹Z, cohort conc=W%",
  "reasoning": "brief explanation of risk stance",
  "hard_limit": <bool — true if you'd veto anything above this>
}}"""

SALES_PROMPT = """You are the Sales & Acquisition Department representative at SBI.
Your mandate: maximize approval amounts and conversion. Push rates toward market benchmark.
Market average personal loan rate: {market_rate:.1%}
Prior observations (your memory):
{memory}

Given the frontier points, pick your PREFERRED point (highest amount, most competitive rate).
Respond in JSON:
{{
  "preferred_index": <int, 0-based index into frontier>,
  "claim": "Approve at ₹X at Y%, Z months",
  "evidence": "Amount delta vs risk preference: ₹X. Rate delta: Y pp vs market",
  "counterargument": "brief challenge to risk agent's conservative stance",
  "reasoning": "acquisition impact"
}}"""

PROFITABILITY_PROMPT = """You are the Product & Finance Department representative at SBI.
Your mandate: maximize net margin (rate - cost_of_funds - expected_loss).
Cost of funds: 6.5%. You want the highest sustainable margin.
Prior observations (your memory):
{memory}

Given the frontier points, pick your PREFERRED point (best margin).
Respond in JSON:
{{
  "preferred_index": <int, 0-based index>,
  "claim": "Approve at ₹X at Y%, Z months",
  "evidence": "Margin=X%, EL rate=Y%, net spread=Z pp",
  "reasoning": "profitability stance"
}}"""

PORTFOLIO_PROMPT = """You are the Portfolio Management Department at SBI.
Your mandate: prevent cohort concentration breaches. You have VETO POWER.
Current cohort concentration: {cohort_conc:.1%} (limit: 15%).
You block ANY point that would breach concentration limits.
Respond in JSON:
{{
  "veto": <bool>,
  "veto_reason": "explanation if veto=true, else empty string",
  "allowed_indices": [<list of frontier indices that pass concentration check>],
  "note": "brief portfolio stance"
}}"""

COLLECTIONS_PROMPT = """You are the Collections Department at SBI.
Your role: adjust effective LGD based on recoverability signals. You FEED the Risk Agent, not vote.
Salary account linked: {salary_linked}
Has collateral: {has_collateral}
Has guarantor: {has_guarantor}

Assess recoverability and provide LGD adjustment.
Respond in JSON:
{{
  "lgd_adjustment": <float, negative = better recovery, e.g. -0.05>,
  "effective_lgd": <float>,
  "recoverability_note": "brief explanation",
  "signals": ["list", "of", "positive/negative recovery signals"]
}}"""

RESOLUTION_PROMPT = """You are the Master Coordinator at SBI Credit.
Given the structured debate below, find the consensus resolution.
Respond in JSON:
{
  "selected_index": <int, 0-based index of selected frontier point>,
  "resolution_type": "consensus" | "compromise" | "escalate",
  "resolution_note": "which constraint was binding and why this point was chosen",
  "binding_constraint": "risk | sales | profitability | portfolio | none"
}"""


def _fmt_frontier(frontier: list[dict]) -> str:
    lines = []
    for i, p in enumerate(frontier):
        lines.append(
            f"  [{i}] ₹{p['amount']:,.0f} @ {p['rate']:.1%} / {p['tenure']}mo "
            f"| EMI ₹{p['emi']:,.0f} | Margin {p['margin']:.2%} | PD {p['pd']:.2%}"
        )
    return "\n".join(lines)


# ──────────────────────────────────────────────
# Individual agent calls
# ──────────────────────────────────────────────

def run_risk_agent(frontier: list[dict]) -> dict:
    memory = get_context("risk")
    mem_str = "\n".join(f"- {m['note']}" for m in memory) or "No prior observations."
    user_msg = f"Frontier points:\n{_fmt_frontier(frontier)}"
    result = call_llm_json(RISK_PROMPT.format(memory=mem_str), user_msg)
    result["agent"] = "Risk Agent"
    return result


def run_sales_agent(frontier: list[dict], system_decision: dict = None,
                    is_shadow: bool = False) -> dict:
    memory = get_context("sales")
    mem_str = "\n".join(f"- {m['note']}" for m in memory) or "No prior observations."
    market_rate = MARKET_BENCHMARK["personal_loan_avg_rate"]

    if is_shadow and system_decision:
        # Shadow opinion mode — compare system decision to sales-optimal
        user_msg = (
            f"System decision: ₹{system_decision.get('amount', 'N/A'):,.0f} "
            f"@ {system_decision.get('rate', 0):.1%} / {system_decision.get('tenure','N/A')}mo\n"
            f"Frontier (all feasible):\n{_fmt_frontier(frontier)}\n"
            f"Market avg rate: {market_rate:.1%}\n"
            f"What would Sales prefer and what is the delta?"
        )
        shadow_prompt = SALES_PROMPT.format(market_rate=market_rate, memory=mem_str) + (
            "\n\nThis is a SHADOW OPINION. Log the acquisition delta vs system decision. "
            "Add field 'shadow_delta': 'Risk constraint cost ₹X in amount and Y pp in rate'"
        )
        result = call_llm_json(shadow_prompt, user_msg)
        result["agent"]  = "Sales Agent (Shadow)"
        result["shadow"] = True
    else:
        user_msg = f"Frontier points:\n{_fmt_frontier(frontier)}"
        result = call_llm_json(
            SALES_PROMPT.format(market_rate=market_rate, memory=mem_str), user_msg
        )
        result["agent"] = "Sales Agent"

    return result


def run_profitability_agent(frontier: list[dict]) -> dict:
    memory = get_context("profitability")
    mem_str = "\n".join(f"- {m['note']}" for m in memory) or "No prior observations."
    user_msg = f"Frontier points:\n{_fmt_frontier(frontier)}"
    result = call_llm_json(PROFITABILITY_PROMPT.format(memory=mem_str), user_msg)
    result["agent"] = "Profitability Agent"
    return result


def run_portfolio_agent(frontier: list[dict], cohort_conc: float) -> dict:
    user_msg = f"Frontier points:\n{_fmt_frontier(frontier)}"
    result = call_llm_json(
        PORTFOLIO_PROMPT.format(cohort_conc=cohort_conc), user_msg
    )
    result["agent"] = "Portfolio Agent"
    return result


def run_collections_agent(applicant: dict, risk_profile: dict) -> dict:
    user_msg = (
        f"Base LGD: {risk_profile['lgd']:.2%}\n"
        f"Loan amount: ₹{applicant.get('loan_amount', 0):,.0f}"
    )
    result = call_llm_json(
        COLLECTIONS_PROMPT.format(
            salary_linked=applicant.get("salary_account_linked", False),
            has_collateral=applicant.get("has_collateral", False),
            has_guarantor=applicant.get("has_guarantor", False),
        ),
        user_msg
    )
    result["agent"] = "Collections Agent"
    return result


def run_coordinator(frontier: list[dict], debate: list[dict],
                    allowed_indices: list[int]) -> dict:
    debate_str = "\n\n".join(
        f"[{d['agent']}]\n  Claim: {d.get('claim','')}\n"
        f"  Evidence: {d.get('evidence','')}\n"
        f"  Reasoning: {d.get('reasoning','')}"
        for d in debate if not d.get("shadow")
    )
    frontier_str = _fmt_frontier(frontier)
    allowed_str  = f"Portfolio-allowed indices: {allowed_indices}"
    user_msg = f"Frontier:\n{frontier_str}\n\n{allowed_str}\n\nDebate:\n{debate_str}"
    result = call_llm_json(RESOLUTION_PROMPT, user_msg)
    result["agent"] = "Master Coordinator"
    return result


# ──────────────────────────────────────────────
# Master negotiation runner
# ──────────────────────────────────────────────

def run_negotiation(optimizer_result: dict, applicant: dict,
                    risk_profile: dict) -> dict:
    """
    Full negotiation cycle. Returns structured debate + selected point.
    """
    frontier     = optimizer_result["frontier"]
    cohort_conc  = optimizer_result.get("cohort_concentration", 0.10)
    debate       = []
    escalate     = False

    # Step 1: Collections agent adjusts LGD (feeds Risk, doesn't vote)
    collections = run_collections_agent(applicant, risk_profile)
    debate.append(collections)
    
    # Bug Fix: Apply LGD adjustment back to risk profile and recalculate frontier
    lgd_adj = collections.get("lgd_adjustment", 0)
    if lgd_adj != 0:
        risk_profile["lgd"] = max(0.05, min(0.95, risk_profile["lgd"] + lgd_adj))
        for pt in frontier:
            pt["el_rate"] = pt["pd"] * risk_profile["lgd"]
            # Recalculate margin (rate - cost_of_funds - el_rate)
            # Assuming cost of funds is 0.065 as per layer2_optimizer default
            pt["margin"] = round(pt["rate"] - 0.065 - pt["el_rate"], 4)

    # Step 2: Portfolio agent veto check (hard gate within negotiation)
    portfolio = run_portfolio_agent(frontier, cohort_conc)
    debate.append(portfolio)

    if portfolio.get("veto"):
        return {
            "result":        "vetoed",
            "veto_reason":   portfolio.get("veto_reason", "Portfolio concentration breach"),
            "debate":        debate,
            "selected_point": None,
            "shadow_opinion": None,
        }

    allowed_indices = portfolio.get("allowed_indices", list(range(len(frontier))))
    if not allowed_indices:
        allowed_indices = list(range(len(frontier)))

    allowed_frontier = [frontier[i] for i in allowed_indices if i < len(frontier)]
    if not allowed_frontier:
        allowed_frontier = frontier

    # Step 3: Negotiation rounds (max 2)
    for _round in range(2):
        risk_opinion   = run_risk_agent(allowed_frontier)
        sales_opinion  = run_sales_agent(allowed_frontier)
        profit_opinion = run_profitability_agent(allowed_frontier)
        debate.extend([risk_opinion, sales_opinion, profit_opinion])

        # Check consensus (all prefer same index)
        prefs = [
            risk_opinion.get("preferred_index", 0),
            sales_opinion.get("preferred_index", 0),
            profit_opinion.get("preferred_index", 0),
        ]
        if len(set(prefs)) == 1:
            break   # Consensus reached

    # Step 4: Coordinator resolves
    coordinator = run_coordinator(allowed_frontier, debate, allowed_indices)
    debate.append(coordinator)

    resolution_type = coordinator.get("resolution_type", "consensus")
    if resolution_type == "escalate":
        escalate = True

    sel_idx = coordinator.get("selected_index", 0)
    selected = allowed_frontier[sel_idx] if sel_idx < len(allowed_frontier) else allowed_frontier[0]

    # Step 5: Sales Agent shadow opinion (runs on every application)
    shadow = run_sales_agent(frontier, system_decision=selected, is_shadow=True)
    debate.append(shadow)

    log_observation("sales", f"Negotiation resolved: ₹{selected['amount']:,.0f} @ {selected['rate']:.1%}")

    return {
        "result":         "escalate" if escalate else "consensus",
        "debate":         debate,
        "selected_point": selected,
        "shadow_opinion": shadow,
        "rounds":         len([d for d in debate if d.get("agent") == "Risk Agent"]),
        "binding_constraint": coordinator.get("binding_constraint", "none"),
    }


def run_shadow_opinion_only(optimizer_result: dict, fast_path_point: dict) -> dict:
    """
    For fast-path cases: run Sales Agent shadow opinion only (no full negotiation).
    """
    frontier = optimizer_result.get("frontier", [fast_path_point])
    shadow   = run_sales_agent(frontier, system_decision=fast_path_point, is_shadow=True)
    log_observation("sales", f"Fast-path shadow: ₹{fast_path_point['amount']:,.0f} @ {fast_path_point['rate']:.1%}")
    return shadow

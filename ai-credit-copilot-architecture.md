# AI Credit Copilot — System Architecture

## 1. Executive Summary

The AI Credit Copilot is a hybrid system combining a deterministic constraint optimizer with department-representative AI agents. The optimizer performs the mathematical heavy lifting (finding feasible loan terms), while agents engage only when genuine trade-offs exist between competing bank departments.

**The core insight:** every decision the system makes — approve, reject, or conditional — is also an acquisition event. A rejection on Product A isn't a dead end; it's either an instant cross-sell into Product B (alternative product routing) or a scheduled, automated re-acquisition event (eligibility recheck). The system treats "no" as a routing decision, not a terminal state.

**One-line pitch:** A constraint optimizer finds what's mathematically feasible; real bank-department agents negotiate which feasible option to choose — only when genuine choice exists; every outcome is stress-tested, fully explainable, and every "no" is automatically converted into a cross-sell offer or a scheduled re-acquisition event — with acquisition-vs-risk trade-offs measured on 100% of applications, not just the contested ones.

---

## 2. High-Level Flow

```
                        APPLICATION INPUT
                              |
                    ┌─────────────────────┐
                    │   GATE LAYER         │
                    │   (hard constraints) │
                    │  Compliance + Fraud  │
                    └─────────────────────┘
                              |
                    ┌─────────────────────┐
                    │   SCORING LAYER      │
                    │  PD / LGD / EAD      │
                    │  Trust Score         │
                    │  Macro Adjustment    │
                    └─────────────────────┘
                              |
                    ┌─────────────────────┐
                    │ CONSTRAINT OPTIMIZER │
                    │  Feasible frontier:  │
                    │  amount, rate, tenure│
                    └─────────────────────┘
                              |
                    ┌─────────────────────┐
                    │   Conflict check     │
                    └─────────────────────┘
                       /              \
              No conflict          Conflict exists
                    |                    |
            FAST-PATH DECISION   DEPARTMENT-AGENT
                    |               NEGOTIATION
                    |                    |
                    └────────┬───────────┘
                              |
                    ┌─────────────────────┐
                    │  STRESS TEST LAYER   │
                    │  (resilience score)  │
                    └─────────────────────┘
                              |
                    ┌─────────────────────┐
                    │  DECISION ROUTING    │
                    └─────────────────────┘
                       /              \
              Auto-execute      Human Underwriter
                    |                    |
                    └────────┬───────────┘
                              |
                    ┌─────────────────────┐
                    │ COUNTERFACTUAL ENGINE│
                    │ (Financial Improve-  │
                    │  ment Graph)         │
                    └─────────────────────┘
                              |
                    ┌─────────────────────┐
                    │ CUSTOMER JOURNEY     │
                    │ AGENT                │
                    └─────────────────────┘
                              |
                        CUSTOMER OUTPUT
```

---

## 3. Layer 0 — Gate Layer (Hard Constraints)

These are non-negotiable veto checks that run first, before any scoring or optimization. No agent negotiation applies here — failure terminates or flags the application immediately.

### 3.1 Compliance Agent
- **Type:** Deterministic rule engine
- **Checks:** KYC completeness, AML screening, sanctions/watchlist matching, regulatory eligibility (age, residency, product-specific rules)
- **Output:** PASS / FAIL (binary)
- **On FAIL:** Application terminates immediately with reason code

### 3.2 Fraud Agent
- **Type:** Hybrid — rule-based velocity/consistency checks + LLM for document/narrative consistency
- **Scope (realistic data sources only):**
  - Bureau data cross-checks
  - Declared income vs. derived income (from bank statement uploads)
  - Application velocity (multiple applications in short window)
  - Document OCR consistency (name, address, ID matches across documents)
- **Output:** Fraud Confidence Score (0–100)
- **Routing:**
  - `> 80` → Reject / terminate
  - `40–80` → Flag for additional verification (continues with flag attached)
  - `< 40` → Pass through clean

---

## 4. Layer 1 — Scoring Layer

Converts raw application data into a quantified risk profile. This is where real banking models replace LLM-generated risk numbers.

### 4.1 Credit Risk Model
- **Type:** Trained ML model (XGBoost / logistic regression) on synthetic dataset
- **Outputs:** PD (Probability of Default), LGD (Loss Given Default), EAD (Exposure At Default)
- **Inputs:** Customer-level features only (income, credit history, employment tenure, existing obligations, repayment history)
- **Design decision:** Macro variables deliberately excluded from training data — handled separately by the Macro Adjustment Module (avoids double-counting)

### 4.2 Trust Score Module
- **Type:** Derived feature (not a standalone agent)
- **Computed from Customer Memory:**
  - Credit score improvement trajectory since last application
  - Savings growth trend
  - Document consistency across applications over time
  - Repayment history (if returning customer)
- **Usage:** Feeds as an adjustment multiplier into PD; also feeds the Counterfactual Engine's "improvement narrative"

### 4.3 Macro Adjustment Module
- **Type:** External data feed + adjustment layer
- **Inputs:** Sector unemployment rate, interest rate environment, inflation indices
- **Usage:** Applies a separate risk premium/multiplier on top of customer-level PD — explicitly kept separate from the Credit Risk Model to avoid double-counting macro effects

### Output of Layer 1
A fully parameterized risk profile per applicant:
```
{
  PD: adjusted probability of default,
  LGD: loss given default,
  EAD: exposure at default,
  trust_score: 0-100,
  macro_premium: risk premium adjustment
}
```

---

## 5. Layer 2 — Constraint Optimizer

### Purpose
Given the risk profile, solve for the feasible frontier of (loan amount, interest rate, tenure) combinations.

### Constraints
```
PD(amount, rate, tenure)        < risk_threshold
margin(amount, rate, tenure)    > profitability_floor
EMI(amount, rate, tenure)       < affordability_limit(income)
portfolio_exposure(cohort)      < concentration_limit
```

### Technology
Mathematical solver (e.g., `scipy.optimize` or OR-Tools) for multi-objective frontier generation.

### Decision Branching
| Frontier Result | Action |
|---|---|
| Empty frontier | REJECT → proceed to Counterfactual Engine |
| Single feasible point | FAST-PATH — deterministic decision, no negotiation |
| Multiple Pareto-optimal points | CONFLICT → trigger Department-Agent Negotiation |

This is the central design principle: **the optimizer determines what's mathematically possible; agents only engage when genuine choice exists among valid alternatives.**

---

## 6. Layer 3 — Department-Agent Negotiation (Conditional)

Triggered **only** when the optimizer returns multiple valid frontier points. Agents represent real bank departments with real incentives — not abstract "Risk/Profit/Fraud" personas.

### 6.1 Agent Roster

| Agent | Represents | Role in negotiation |
|---|---|---|
| **Risk Agent** | Credit Risk dept | Prefers frontier points minimizing PD/exposure |
| **Sales/Acquisition Agent** | Sales dept | Prefers points maximizing approval amount/conversion, informed by Market Benchmarking. **Also logs a shadow opinion on every application — including fast-path cases — see Section 6.4** |
| **Profitability Agent** | Product/Finance dept | Prefers points maximizing margin |
| **Portfolio Agent** | Portfolio Management | Holds **veto power** — can block any point breaching cohort concentration limits |
| **Collections Agent** | Collections dept | Adjusts effective LGD based on recoverability signals (salary account linkage, collateral); feeds Risk Agent rather than voting independently |

### 6.2 Market Benchmarking Module
- External/competitor rate data feed
- Gives Sales Agent a concrete quantitative lever: "push toward 10.7% to stay competitive with market average 10.8%"
- Creates genuine, non-ceremonial disagreement with Risk Agent's preference for higher rates

### 6.3 Negotiation Protocol — Structured Debate Format

For each candidate frontier point, agents produce a structured debate entry:

```
Claim:            "Approve at ₹3.5L, 12.5%, 48 months"
Evidence:         PD = 2.1%, margin = 18%, EMI = ₹8,200, 
                  cohort concentration = 12% (limit 15%)
Counterargument:  Sales Agent — "₹4L would improve conversion;
                  market rate is 10.8%, we're above it"
Resolution:       Selected point + which constraint was binding
```

**Regulatory defensibility:** This log is the system's answer to "why did this customer get 12.5% instead of 11%?" It is not a generated summary or an LLM's after-the-fact rationalization — it is the deterministic record of the actual negotiation that produced the decision. If a regulator asks for the reasoning behind a specific rate, the bank hands them this exact text trace, showing precisely which department's constraint was binding and what compromise was reached. This converts "the AI thought it was best" into an auditable, replayable record.

### 6.4 Sales Agent Shadow Opinion (Runs on Every Application)

While most agents only activate during negotiation (Section 6.3), the Sales/Acquisition Agent additionally logs a **non-binding shadow opinion on 100% of applications** — including fast-path cases that never reach negotiation.

**Mechanism:** After the optimizer/negotiation produces a final decision, the Sales Agent compares it against its own conversion-optimal point on the frontier (or, for rejections, against the nearest feasible point) and logs the delta.

**Example log entries:**
```
Fast-path case:
  System decision:        ₹3.0L at 13.0%
  Sales Agent optimal:     ₹3.5L at 12.5%
  Delta logged:           "Risk constraint cost ~₹50K in approved 
                           amount and 0.5pp in rate"

Rejected case:
  System decision:        REJECTED (empty frontier)
  Sales Agent optimal:     ₹1.5L secured credit-builder loan — feasible
  Delta logged:           "Primary product infeasible; alternative 
                           product feasible at full requested risk 
                           tolerance"
```

**Why this matters:** This produces acquisition-vs-risk telemetry across the entire application pool, not just the ~10% that hit negotiation — giving judges (and eventually the bank) a portfolio-wide view of how much acquisition is being "left on the table" by risk-conservative decisions, and where that trade-off is most concentrated.

### 6.5 Master Coordinator
- **Type:** Deterministic orchestration logic (state machine, not an "intelligent" agent)
- **Responsibilities:**
  1. Check Portfolio Agent veto first (hard gate within negotiation)
  2. Run up to 2–3 negotiation rounds among remaining agents
  3. If consensus reached → proceed to Stress Test Layer
  4. If no consensus after max rounds → escalate to Human Underwriter
  5. Log full structured debate trace for explainability

---

## 7. Layer 4 — Stress Test Layer

Applied to the selected decision (whether fast-pathed or negotiated).

### Process
Re-run the Credit Risk Model under perturbed scenarios:
1. Interest rate +2%
2. Customer income −20%
3. Sector unemployment shock (macro premium increase)

### Output
**Resilience Score** — does the approval survive these scenarios?

### Routing
| Resilience | Action |
|---|---|
| High | Proceed to auto-execute path |
| Borderline | Risk Agent re-enters with tighter terms, or flag for human review |

---

## 8. Layer 5 — Decision Routing

```
Consensus reached + high resilience + risk below escalation threshold
    → AUTO-EXECUTE (instant decision, ~minutes)

Consensus reached but borderline resilience
OR no consensus reached
OR risk above escalation threshold
    → HUMAN UNDERWRITER
      (receives full structured debate log + system recommendation)
```

This embodies the "Credit Copilot" framing: AI analyzes → negotiates → recommends → human approves for non-trivial cases.

---

## 9. Layer 6 — Counterfactual Engine: The Acquisition Engine

Runs on **every** outcome — approved, conditional, or rejected. This layer is the system's primary acquisition mechanism, not merely a "rejection explainer."

### Mechanism
Re-runs the optimizer/scoring pipeline under hypothetical input perturbations to build a **Financial Improvement Graph**, ranked by probability lift and feasibility, with two distinct branches:

**Branch A — Improvement Path (the "Not Yet")**
Single-step and multi-step changes that would make the *original requested product* approvable.

**Mathematical grounding for Branch A:** Because the Credit Risk Model (Section 4.1) is an XGBoost/logistic regression model, every probability shift shown to the customer is computed, not LLM-estimated. The engine uses:
- **SHAP values** on the trained model to identify which input features have the largest marginal effect on PD for this specific applicant
- **Iterative sensitivity analysis** — re-scoring the model with each candidate feature perturbed (e.g., card debt = 0, income +10%, guarantor flag = true) to get the resulting PD, then re-running the Layer 2 optimizer with the updated risk profile to confirm the frontier becomes non-empty

The LLM's role is limited to translating these computed deltas into natural-language recommendations — it does not generate or guess the probability numbers themselves.

**Branch B — Alternative Product Routing (the "Yes, but different" — instant cross-sell)**
If the original product is infeasible, immediately check feasibility of adjacent products. A "no" on the requested loan becomes a "yes" on a different product, in the same session — this is a live acquisition conversion, not a future promise.

### Example Output
```
Requested: ₹4L unsecured personal loan
Current approval probability: 35%

── Branch A: Improvement Path ──
  + Add guarantor                          → 78%
  + Reduce requested amount by ₹75,000     → 92%
  + Pay off existing card debt             → 85%
  + Guarantor + 3 months savings history   → 96%

── Branch B: Alternative Product Routing (immediate) ──
  ✓ Secured credit-builder loan (₹1L)      → APPROVED NOW
  ✓ Digital savings account                → APPROVED NOW
```

### Why this matters
Branch B converts a rejection into an on-the-spot sale of a different product — this is customer acquisition happening inside the rejection flow itself. Branch A converts a rejection into a future pipeline entry (see Layer 7). Together: **every "no" on the requested product resolves to either a "yes" on something else right now, or a scheduled path back to "yes" on the original ask.**

---

## 10. Layer 7 — Customer Journey Agent: The Re-Acquisition Loop

### Inputs
Final decision + counterfactual graph (Branches A & B) + trust score + product catalog

### Approved Path
```
Day 1:  Loan onboarding
Day 7:  Auto-pay setup
Day 30: Credit score tracker activation
Day 60: Cross-sell offer (insurance, based on profile)
Day 90: Investment recommendation
```

### Rejected / Conditional Path — Automated Re-Acquisition
```
Week 1:  Targeted credit education content
Month 1: Savings challenge (linked to Branch A of counterfactual graph)
Month 3: Progress check-in / reapply reminder
Month 6: Automatic eligibility recheck (re-enters pipeline at Layer 1)
```

**Why this matters:** Most banks treat a rejected application as a lost lead — re-acquisition requires the customer to independently decide to come back, with zero institutional follow-up. This system schedules that follow-up automatically. The Month 6 recheck is a fully automated re-acquisition event requiring zero manual sales effort, and **reapplication conversion rate** (what % of Month 6 rechecks convert to approval) becomes a concrete, demoable acquisition metric.

### Trust-Score-Triggered Early Outreach (event-driven, not just time-driven)
Rather than waiting for the scheduled Month 6 recheck, the Journey Agent monitors Trust Score (Section 11.2) between cycles. If a previously-rejected customer's Trust Score crosses a defined improvement threshold mid-cycle (e.g., credit score jumps 50+ points, or savings pattern shows sustained improvement for 2+ months), the eligibility recheck is triggered early — proactive outreach instead of waiting for the customer to either reapply or hit the scheduled checkpoint.

```
Customer rejected on 2025-12-01 (Trust Score: 42)
Month 3 check-in (2026-03-01): Trust Score: 58 — below trigger threshold (65)
Mid-cycle update (2026-04-15): Credit score +55 pts, Trust Score: 71
  → THRESHOLD CROSSED → eligibility recheck triggered early
  → Customer re-enters Layer 1 pipeline 6 weeks ahead of schedule
```

### Theme Mapping
| Journey Element | Hackathon Pillar |
|---|---|
| Onboarding sequence, cross-sell | Digital Adoption |
| Credit education, savings challenge | Digital Engagement |
| Reapply reminder, eligibility recheck, trust-triggered early outreach | Customer Acquisition |

---

## 11. Agent Memory (Cross-Cutting Layer)

### 11.1 Department Agent Memory

Each department-agent maintains a lightweight rolling log of cohort-level calibration observations. These are **soft adjustments to preferences**, not model retraining — deliberately avoiding the reject-inference bias problem.

```
Risk Agent memory:
  "Young freelancer cohort — actual defaults trending below predicted"

Sales Agent memory:
  "Co-applicant offers — 34% acceptance rate this month"

Portfolio Agent memory:
  "Cohort 'Stable Saver' approaching concentration limit (14.2% / 15%)"
```

These logs feed as minor weight adjustments into future negotiation rounds, giving agents a form of evolving behavior without introducing uncontrolled feedback loops.

### 11.2 Trust Score (Referenced by Layer 7)

The Trust Score (defined in Section 4.2) is the trigger condition for the early-outreach mechanism in Layer 7. It is recalculated whenever Customer Memory is updated (new application, or new data linked to an existing customer profile via the digital banking app — e.g., updated credit bureau pull, savings account activity). When it crosses the early-outreach threshold for a previously-rejected customer, it fires the trust-triggered recheck described in Section 10.

---

## 12. Customer Memory (Persistent Store)

Tracks applicant history across time and applications:

```json
{
  "customer_id": "CUST-00231",
  "applications": [
    {
      "date": "2025-12-01",
      "decision": "REJECTED",
      "reason": "Credit score 580, insufficient savings",
      "credit_score": 580,
      "savings": 0
    },
    {
      "date": "2026-06-01",
      "decision": "PENDING",
      "credit_score": 610,
      "savings": 15000
    }
  ]
}
```

Used by: Trust Score Module, Counterfactual Engine (improvement narrative), Customer Journey Agent (reapply tracking).

---

## 13. Technology Stack

| Component | Technology |
|---|---|
| Gate Layer (Compliance) | Deterministic rule engine |
| Gate Layer (Fraud) | Rule-based velocity checks + Claude for document/narrative consistency |
| Credit Risk Model | XGBoost / logistic regression on synthetic data |
| Trust Score | Derived feature from Customer Memory (PostgreSQL) |
| Macro Adjustment | External/mock macro data feed |
| Constraint Optimizer | `scipy.optimize` / OR-Tools — multi-objective frontier solver |
| Department Agents | Claude — preference reasoning + structured debate generation over optimizer outputs |
| Master Coordinator | LangGraph as deterministic state machine (orchestration only, not "intelligence") |
| Stress Test | Re-invocation of Credit Risk Model with perturbed feature vectors |
| Counterfactual Engine | Optimizer run in reverse / sensitivity analysis over feature space |
| Customer Journey Agent | Claude — generates personalized sequences from templates + decision context |
| Market Benchmarking | External/mock competitor rate feed |
| Customer Memory | PostgreSQL |
| Agent Memory | Lightweight key-value store (Redis) |
| Decision Logs | PostgreSQL (structured debate traces for audit) |

---

## 14. Demo Script (3 Cases)

### Case 1 — Fast-Path Approval
- Single optimal frontier point found
- No negotiation triggered
- Decision in under 30 seconds
- **Demonstrates:** efficiency, the optimizer doing real work

### Case 2 — Negotiation Case
- Multiple frontier points exist
- Sales Agent (using Market Benchmark) vs. Risk Agent (concentration concerns) genuinely disagree
- Portfolio Agent veto demonstrated on one candidate point
- Full structured debate trace shown to judges as the **raw, unsummarized audit log** — framed explicitly as what would be handed to a regulator who asks "why 12.5% and not 11%?"
- **Demonstrates:** genuine multi-stakeholder negotiation, regulatory-grade explainability (no black box)

### Case 3 — Rejection → Improvement Path → Journey
- Application rejected by optimizer (empty frontier)
- Counterfactual Engine generates ranked Branch A (Improvement Path)
- Customer Journey Agent produces 6-month re-engagement plan with trust-triggered early-outreach explained
- **Demonstrates:** "No becomes Not Yet" — the scheduled re-acquisition narrative

### Case 4 — Rejection → Instant Cross-Sell (Branch B)
- Same rejected application as Case 3, but Counterfactual Engine's Branch B shows an alternative product (e.g., secured credit-builder loan) is immediately approvable
- Customer is offered and "accepts" the alternative product in the same session
- Sales Agent's shadow opinion log is shown alongside, quantifying the acquisition-vs-risk trade-off for this case
- **Demonstrates:** the core acquisition reframe — a rejection converted into a live sale within the same interaction, with the trade-off fully quantified

---

## 15. Metric Reframe — The Closing Argument

| Metric Type | Traditional Banking | AI Credit Copilot |
|---|---|---|
| **Rejection Outcome** | Lost lead / dead end | Instant cross-sell (Branch B) or active pipeline asset (Branch A + Layer 7) |
| **Risk vs. Sales View** | Siloed, adversarial bickering | 100% quantified portfolio telemetry via Sales Agent shadow opinion (Section 6.4) |
| **Re-Acquisition** | Expensive manual marketing campaigns | Fully automated, event-driven trigger loop (scheduled + trust-score-triggered) |
| **Explainability** | Adversarial committee opinions, undocumented judgment calls | Structured, replayable debate trace — regulator-ready audit log (Section 6.3) |
| **Counterfactual Reasoning** | "You didn't qualify" — no further information | SHAP-grounded, mathematically computed improvement paths (Section 9) |

## 16. Design Principles Summary

1. **Optimization does the math; agents arbitrate preferences** — agents only engage on genuine trade-offs, not deterministic outcomes
2. **Hard gates are structurally separate from negotiation** — Compliance and Portfolio concentration are vetoes, not debate participants
3. **Agents map to real bank departments** — organizationally legible to banking judges, resolves "who authorized this agent" questions
4. **Macro effects are explicitly separated from customer-level risk** — avoids double-counting
5. **Reject inference is future work, not a core claim** — avoids unvalidatable methodology questions
6. **Negotiation is tiered/exception-based** — most applications skip it entirely, controlling LLM cost
7. **Every "no" is a routing decision, not a terminal state** — instant cross-sell (Branch B) or scheduled re-acquisition (Layer 7), with no manual sales effort required
8. **Acquisition trade-offs are measured on 100% of applications** — the Sales Agent's shadow opinion runs on fast-path cases too, not just negotiated ones
9. **Re-acquisition is both scheduled and event-driven** — Month 6 recheck as baseline, Trust Score threshold crossings trigger early outreach
10. **Human-in-the-loop for contested or high-risk cases** — "Copilot," not "replacement"

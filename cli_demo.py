"""
AI Credit Copilot — CLI Demo Runner
Rich terminal interface showcasing all 7 layers and 4 demo cases.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.columns import Columns
from rich.align import Align
from rich import box

from demo.demo_cases import list_cases, get_case
from pipeline import run_pipeline, ensure_model

console = Console()

# ── Color palette ─────────────────────────────
C = {
    "brand":   "bold cyan",
    "ok":      "bold green",
    "warn":    "bold yellow",
    "danger":  "bold red",
    "info":    "dim white",
    "label":   "bold white",
    "accent":  "bold magenta",
    "muted":   "grey62",
}


# ── Header ─────────────────────────────────────
def print_header():
    console.clear()
    console.print()
    console.print(Panel.fit(
        "[bold cyan]  AI Credit Copilot[/]\n"
        "[dim]  SBI Hackathon Demo — Hybrid Constraint Optimizer + Department Agents[/]\n"
        "[dim]  Powered by Groq AI · Llama-3-8B (Open-Source, Free, Lightning Fast)[/]",
        border_style="cyan",
        padding=(1, 4),
    ))
    console.print()


# ── Demo case selector ─────────────────────────
def select_demo_case() -> dict:
    cases = list_cases()

    table = Table(box=box.ROUNDED, border_style="cyan", show_header=True,
                  header_style="bold cyan", padding=(0, 1))
    table.add_column("#",          width=3,  style="bold white")
    table.add_column("Case",       width=35, style="bold yellow")
    table.add_column("Demonstrates", width=55, style="dim white")

    for c in cases:
        table.add_row(c["id"], c["label"].replace("Case " + c["id"] + " — ", ""),
                      c["theme"])

    console.print(table)
    console.print()
    console.print("[bold white]  Enter custom applicant[/] → press [bold cyan]5[/]", justify="left")
    console.print()

    while True:
        choice = console.input("[bold cyan]Select case (1-4, or 5 for custom): [/]").strip()
        if choice in ("1", "2", "3", "4"):
            case = get_case(choice)
            console.print(
                f"\n  [bold cyan]▶[/] Running: [bold yellow]{case['label']}[/]"
                f"\n  [dim]{case['description']}[/]\n"
            )
            return case["applicant"]
        elif choice == "5":
            return build_custom_applicant()
        else:
            console.print("  [bold red]Invalid choice. Enter 1-5.[/]")


# ── Custom applicant builder ───────────────────
def build_custom_applicant() -> dict:
    console.print("\n[bold cyan]── Custom Applicant ──[/]\n")

    def ask(prompt, default, cast=str):
        val = console.input(f"  [white]{prompt}[/] [{default}]: ").strip()
        try:
            return cast(val) if val else cast(default)
        except Exception:
            return cast(default)

    name        = ask("Full name",           "Applicant")
    age         = ask("Age",                 "35",   int)
    income      = ask("Monthly income (₹)",  "50000", float)
    credit      = ask("Credit score",        "680",  int)
    savings     = ask("Savings balance (₹)", "80000", float)
    emp_years   = ask("Employment years",    "4",    float)
    existing_emi= ask("Existing EMI/mo (₹)", "0",    float)
    loans_count = ask("Number of existing loans", "0", int)
    loan_amount = ask("Requested loan amount (₹)", "300000", float)
    tenure      = ask("Loan tenure (months)", "36",  int)
    purpose     = ask("Loan purpose",        "Personal")
    sector      = ask("Sector (IT/Finance/Retail/Manufacturing/Healthcare/Construction)", "IT")
    guarantor   = ask("Has guarantor? (y/n)", "n").lower() == "y"
    collateral  = ask("Has collateral? (y/n)", "n").lower() == "y"

    return {
        "customer_id": "CUST-CUSTOM",
        "name": name, "age": age, "dob": "1990-01-01",
        "pan": "CUSTOM123X", "address": "India", "residency": "IN",
        "sector": sector, "employment_type": "Salaried",
        "employment_years": emp_years, "income_monthly": income,
        "existing_emi": existing_emi, "num_existing_loans": loans_count,
        "savings_balance": savings, "credit_score": credit,
        "repayment_history": min(1.0, credit / 900),
        "has_guarantor": guarantor, "has_collateral": collateral,
        "salary_account_linked": True,
        "loan_amount": loan_amount, "loan_tenure": tenure,
        "loan_purpose": purpose, "recent_applications_30d": 0,
        "bureau_income_estimate": income * 1.02,
    }


# ── Layer display functions ─────────────────────

def show_layer_header(n: int, name: str, icon: str = "⬡"):
    console.print()
    console.print(Rule(f"[bold cyan]{icon} LAYER {n} — {name}[/]", style="cyan"))


def show_compliance(result: dict):
    show_layer_header(0, "GATE — COMPLIANCE")
    status = result["status"]
    color  = C["ok"] if status == "PASS" else C["danger"]
    console.print(f"  Status: [{color}]{status}[/]")
    console.print(f"  {result['reason']}", style=C["info"])

    table = Table(box=box.SIMPLE, show_header=False, padding=(0,2))
    table.add_column(style="dim white")
    table.add_column()
    for k, v in result["checks"].items():
        icon = "✓" if v else "✗"
        col  = C["ok"] if v else C["danger"]
        table.add_row(k.replace("_", " ").title(), f"[{col}]{icon}[/]")
    console.print(table)


def show_fraud(result: dict):
    score = result["fraud_score"]
    flag  = result["flag"]
    color = C["ok"] if flag == "clean" else (C["warn"] if flag == "flagged" else C["danger"])

    table = Table(box=box.SIMPLE, show_header=False, padding=(0,2))
    table.add_column(style="dim white", width=28)
    table.add_column()
    table.add_row("Fraud Score",       f"[{color}]{score}/100[/]")
    table.add_row("Flag",              f"[{color}]{flag.upper()}[/]")
    table.add_row("Rule Score",        str(result["rule_score"]))
    table.add_row("LLM Narrative",     str(result["llm_narrative_score"]))
    if result["flags"]:
        table.add_row("Flags", "\n".join(f"⚠ {f}" for f in result["flags"][:3]))
    console.print(table)


def show_scoring(result: dict):
    show_layer_header(1, "SCORING — RISK PROFILE")
    table = Table(box=box.ROUNDED, border_style="dim cyan", padding=(0,2))
    table.add_column("Metric",   style="bold white",  width=28)
    table.add_column("Value",    width=18)
    table.add_column("Note",     style=C["muted"])

    pd_color = C["ok"] if result["pd_adjusted"] < 0.05 else (C["warn"] if result["pd_adjusted"] < 0.15 else C["danger"])
    table.add_row("PD (Base)",        f"[{pd_color}]{result['pd_base']:.2%}[/]",     "Customer-level")
    table.add_row("Macro Premium",    f"+{result['macro_premium']:.3%}",               f"Sector: {result['macro_data']['sector']}")
    table.add_row("PD (Adjusted)",    f"[{pd_color}]{result['pd_adjusted']:.2%}[/]", "Risk threshold: 15%")
    table.add_row("LGD",              f"{result['lgd']:.0%}",                          "Loss given default")
    table.add_row("EAD",              f"₹{result['ead']:,.0f}",                        "Exposure at default")
    table.add_row("Expected Loss",    f"₹{result['expected_loss']:,.0f}",              "PD × LGD × EAD")
    ts_color = C["ok"] if result["trust_score"] >= 65 else (C["warn"] if result["trust_score"] >= 45 else C["danger"])
    table.add_row("Trust Score",      f"[{ts_color}]{result['trust_score']}/100[/]",  "From customer history")
    console.print(table)


def show_optimizer(result: dict):
    show_layer_header(2, "CONSTRAINT OPTIMIZER")
    branch = result["branch"]
    branch_color = {"empty": C["danger"], "single": C["ok"], "multiple": C["warn"]}[branch]
    console.print(f"  Branch: [{branch_color}]{branch.upper()}[/]  |  Feasible points: [bold]{result['all_feasible_count']}[/]  |  Pareto frontier: [bold]{len(result['frontier'])}[/]")

    if result["frontier"]:
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan", padding=(0,1))
        table.add_column("#",      width=3)
        table.add_column("Amount",  width=12)
        table.add_column("Rate",    width=7)
        table.add_column("Tenure",  width=8)
        table.add_column("EMI/mo",  width=11)
        table.add_column("Margin",  width=8)
        table.add_column("PD",      width=7)

        for i, p in enumerate(result["frontier"][:8]):
            is_best = (p == result.get("best_point"))
            style   = "bold green" if is_best else ""
            tag     = " ◀ best" if is_best else ""
            table.add_row(
                str(i), f"₹{p['amount']:,.0f}{tag}",
                f"{p['rate']:.1%}", f"{p['tenure']}mo",
                f"₹{p['emi']:,.0f}", f"{p['margin']:.2%}",
                f"{p['pd']:.2%}",
                style=style,
            )
        console.print(table)

    if branch == "empty":
        console.print("  [bold red]✗ Empty frontier → Proceeding to Counterfactual Engine[/]")
    elif branch == "single":
        console.print("  [bold green]✓ Single feasible point → FAST-PATH (no negotiation)[/]")
    else:
        console.print("  [bold yellow]⚡ Multiple Pareto points → TRIGGERING AGENT NEGOTIATION[/]")


def show_negotiation(result: dict):
    show_layer_header(3, "DEPARTMENT-AGENT NEGOTIATION")

    if result.get("result") == "vetoed":
        console.print(f"  [bold red]🚫 PORTFOLIO AGENT VETO[/]")
        console.print(f"  {result.get('veto_reason','')}", style=C["danger"])
        return

    debate = result.get("debate", [])
    for entry in debate:
        agent = entry.get("agent", "")
        if entry.get("shadow"):
            continue  # shown separately
        agent_color = {
            "Risk Agent":          "red",
            "Sales Agent":         "green",
            "Profitability Agent": "yellow",
            "Portfolio Agent":     "magenta",
            "Collections Agent":   "blue",
            "Master Coordinator":  "cyan",
        }.get(agent, "white")

        console.print(f"\n  [bold {agent_color}]▸ {agent}[/]")
        if entry.get("claim"):
            console.print(f"    Claim:    [white]{entry['claim']}[/]")
        if entry.get("evidence"):
            console.print(f"    Evidence: [dim]{entry['evidence']}[/]")
        if entry.get("counterargument"):
            console.print(f"    Counter:  [dim yellow]{entry['counterargument']}[/]")
        if entry.get("reasoning"):
            console.print(f"    Stance:   [dim]{entry['reasoning']}[/]")
        if entry.get("recoverability_note"):
            console.print(f"    Recovery: [dim]{entry['recoverability_note']}[/]")
        if entry.get("resolution_note"):
            console.print(f"    [bold cyan]Resolution: {entry['resolution_note']}[/]")
            console.print(f"    Binding constraint: [bold yellow]{entry.get('binding_constraint','none')}[/]")

    if result.get("selected_point"):
        p = result["selected_point"]
        console.print(f"\n  [bold green]✓ Consensus: ₹{p['amount']:,.0f} @ {p['rate']:.1%} / {p['tenure']}mo | EMI ₹{p['emi']:,.0f}[/]")
        console.print(f"  Binding constraint: [bold yellow]{result.get('binding_constraint','none')}[/]")


def show_shadow_opinion(shadow: dict):
    if not shadow:
        return
    console.print()
    console.print(Panel(
        f"[bold green]Sales Agent Shadow Opinion[/]\n"
        f"[dim]Runs on 100% of applications — acquisition-vs-risk telemetry[/]\n\n"
        f"[white]Preferred point:[/] {shadow.get('claim', 'N/A')}\n"
        f"[white]Delta vs system:[/] {shadow.get('shadow_delta', shadow.get('counterargument', 'N/A'))}\n"
        f"[dim]{shadow.get('reasoning', '')}[/]",
        border_style="green",
        padding=(0, 2),
        title="[bold green]§6.4 Shadow Opinion[/]",
    ))


def show_stress_test(result: dict):
    show_layer_header(4, "STRESS TEST LAYER")
    res_color = C["ok"] if result["resilience_label"] == "HIGH" else (
                C["warn"] if result["resilience_label"] == "BORDERLINE" else C["danger"])

    table = Table(box=box.ROUNDED, border_style="dim cyan", padding=(0,2))
    table.add_column("Scenario",     width=28, style="bold white")
    table.add_column("Stressed PD",  width=12)
    table.add_column("PD Delta",     width=10)
    table.add_column("Survives",     width=10)

    for s in result["scenarios"]:
        surv_icon  = "[bold green]✓ YES[/]" if s["survives"] else "[bold red]✗ NO[/]"
        delta_col  = C["ok"] if s["pd_delta"] < 0.01 else (C["warn"] if s["pd_delta"] < 0.03 else C["danger"])
        table.add_row(
            s["scenario"],
            f"{s['stressed_pd']:.2%}",
            f"[{delta_col}]+{s['pd_delta']:.2%}[/]",
            surv_icon,
        )
    console.print(table)
    console.print(
        f"  Resilience Score: [{res_color}]{result['resilience_score']}/100 ({result['resilience_label']})[/]"
        f"  |  Routing → [{res_color}]{result['routing']}[/]"
    )


def show_routing(result: dict):
    show_layer_header(5, "DECISION ROUTING")
    color = C["ok"] if result["route"] == "AUTO_EXECUTE" else C["warn"]
    console.print(f"  [{color}]{result['route_label']}[/]")
    console.print(f"  {result['route_note']}", style=C["info"])
    if result.get("reasons"):
        for r in result["reasons"]:
            console.print(f"  [dim yellow]⚠ {r}[/]")


def show_decision_banner(result: dict):
    console.print()
    dec = result.get("final_decision", "UNKNOWN")
    color = {"APPROVED": "green", "REJECTED": "red", "CONDITIONAL": "yellow"}.get(dec, "white")
    p = result.get("selected_point")

    lines = [f"[bold {color}]  FINAL DECISION: {dec}  [/]"]
    if p and dec != "REJECTED":
        lines.append(f"[white]  ₹{p['amount']:,.0f} @ {p['rate']:.1%} p.a. / {p['tenure']} months[/]")
        lines.append(f"[dim]  EMI: ₹{p['emi']:,.0f}/month[/]")
    elif dec == "REJECTED":
        lines.append(f"[dim]  {result.get('rejection_reason','')[:80]}[/]")

    console.print(Panel(
        "\n".join(lines),
        border_style=color,
        padding=(1, 4),
    ))


def show_counterfactual(result: dict):
    show_layer_header(6, "COUNTERFACTUAL ENGINE — ACQUISITION ENGINE")

    # Branch A
    console.print("\n  [bold cyan]── Branch A: Improvement Path (\"Not Yet\")[/]")
    branch_a = result.get("branch_a", [])
    if branch_a:
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan", padding=(0,1))
        table.add_column("Action",       width=40, style="white")
        table.add_column("PD Before",    width=10)
        table.add_column("PD After",     width=10)
        table.add_column("Approval %",   width=11, style="bold green")
        table.add_column("Effort",       width=8)
        table.add_column("Timeline",     width=12)
        for b in branch_a:
            table.add_row(
                b["action"],
                f"{b['pd_before']:.2%}",
                f"{b['pd_after']:.2%}",
                f"~{b['approval_probability']}%",
                b["effort"],
                b["timeline"],
            )
        console.print(table)
    else:
        console.print("  [dim]No improvement paths computed.[/]")

    # Narrative
    if result.get("narrative"):
        console.print()
        console.print(Panel(
            result["narrative"],
            title="[bold cyan]AI-Generated Improvement Narrative (Gemini)[/]",
            border_style="cyan",
            padding=(0, 2),
        ))

    # Branch B
    console.print("\n  [bold magenta]── Branch B: Alternative Product Routing (\"Yes, but different\")[/]")
    branch_b = result.get("branch_b", [])
    if branch_b:
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold magenta", padding=(0,1))
        table.add_column("Product",      width=35, style="white")
        table.add_column("Status",       width=16)
        table.add_column("Terms",        width=35)
        for b in branch_b:
            st_color = C["ok"] if b["status"] == "APPROVED NOW" else C["danger"]
            terms_str = ""
            if b.get("terms"):
                t = b["terms"]
                terms_str = f"₹{t['amount']:,.0f} @ {t['rate']:.1%} / {t['tenure']}mo"
            table.add_row(
                b["product_name"],
                f"[{st_color}]{b['status']}[/]",
                terms_str or b.get("reason", ""),
            )
        console.print(table)

    acq_note = result.get("acquisition_note")
    if acq_note:
        console.print(f"\n  [bold green]🎯 {acq_note}[/]")


def show_journey(result: dict):
    show_layer_header(7, "CUSTOMER JOURNEY AGENT — RE-ACQUISITION LOOP")

    template = result.get("template_journey", [])
    table = Table(box=box.ROUNDED, border_style="dim cyan", padding=(0,2))
    table.add_column("Touchpoint", width=12, style="bold cyan")
    table.add_column("Event",      width=28, style="bold white")
    table.add_column("Action",     width=50, style="dim white")

    for t in template:
        timing = f"Day {t['day']}" if "day" in t else (f"Week {t['week']}" if "week" in t else f"Month {t['month']}")
        table.add_row(timing, t["event"], t["action"])
    console.print(table)

    if result.get("personalized_plan"):
        console.print()
        console.print(Panel(
            result["personalized_plan"],
            title="[bold cyan]Personalized Journey (Gemini)[/]",
            border_style="cyan",
            padding=(0, 2),
        ))

    # Trust-triggered early outreach
    outreach = result.get("early_outreach", {})
    if outreach.get("triggered"):
        console.print()
        console.print(Panel(
            f"[bold yellow]⚡ TRUST-SCORE EARLY OUTREACH TRIGGERED[/]\n"
            f"{outreach['reason']}\n"
            f"[bold green]{outreach['action']}[/]\n"
            f"[dim]{outreach.get('note','')}[/]",
            border_style="yellow",
            padding=(0,2),
        ))


# ── Main CLI loop ──────────────────────────────

def run_demo():
    ensure_model()
    print_header()

    while True:
        applicant = select_demo_case()

        console.print()
        console.print(Panel.fit(
            f"[bold white]Processing: [bold cyan]{applicant.get('name','Applicant')}[/][/]\n"
            f"[dim]Requested: ₹{applicant.get('loan_amount',0):,.0f}  |  "
            f"Credit Score: {applicant.get('credit_score','N/A')}  |  "
            f"Income: ₹{applicant.get('income_monthly',0):,.0f}/mo[/]",
            border_style="cyan",
        ))
        console.print()

        start = time.time()

        # Callbacks for live display
        def cb_compliance(r):
            show_layer_header(0, "GATE — COMPLIANCE & FRAUD")
            show_compliance(r)

        def cb_fraud(r):
            show_fraud(r)

        def cb_scoring(r):
            show_scoring(r)

        def cb_optimizer(r):
            show_optimizer(r)

        def cb_negotiation(r):
            show_negotiation(r)

        def cb_shadow(r):
            show_shadow_opinion(r)

        def cb_stress(r):
            show_stress_test(r)

        def cb_routing(r):
            show_routing(r)

        def cb_counterfactual(r):
            show_counterfactual(r)

        def cb_journey(r):
            show_journey(r)

        callbacks = {
            "compliance":    cb_compliance,
            "fraud":         cb_fraud,
            "scoring":       cb_scoring,
            "optimizer":     cb_optimizer,
            "negotiation":   cb_negotiation,
            "shadow":        cb_shadow,
            "stress":        cb_stress,
            "routing":       cb_routing,
            "counterfactual":cb_counterfactual,
            "journey":       cb_journey,
        }

        with Progress(
            SpinnerColumn(style="cyan"),
            TextColumn("[cyan]{task.description}"),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Running pipeline...", total=None)
            result = run_pipeline(applicant, callbacks=callbacks)
            progress.remove_task(task)

        # Final decision banner
        show_decision_banner(result)

        # Shadow opinion (always shown)
        if result.get("shadow_opinion"):
            show_shadow_opinion(result["shadow_opinion"])

        # --- HACKATHON PILLAR ALIGNMENT DEMO ---
        console.print()
        console.print(Rule(style="bold yellow"))
        console.print("[bold yellow]*** HACKATHON PILLAR ALIGNMENT DEMO ***[/]", justify="center")
        console.print(Rule(style="bold yellow"))
        
        decision = result.get("final_decision", "UNKNOWN")
        
        # Pillar 1
        if decision == "CONDITIONAL":
            req_amt = applicant.get("loan_amount", 0)
            app_amt = result.get("approved_terms", {}).get("amount", 0)
            console.print(f"[bold cyan]01. Customer Acquisition & Onboarding[/]: Prevented a flat rejection by actively negotiating requested Rs.{req_amt:,.0f} down to an affordable Rs.{app_amt:,.0f}. Bank wins the customer safely!")
        else:
            console.print("[bold cyan]01. Customer Acquisition & Onboarding[/]: Autonomous multi-agent engine evaluates complex applications instantly without human bias.")
            
        # Pillar 2
        alts = result.get("counterfactual", {}).get("branch_b", [])
        approved_alts = [a for a in alts if a.get("status") == "APPROVED NOW"]
        if decision == "REJECTED" and approved_alts:
            console.print(f"[bold green]02. Digital Product Adoption[/]: Autonomously cross-sold '{approved_alts[0].get('product_name')}' immediately upon loan rejection to keep the customer active in the SBI digital ecosystem.")
        else:
            console.print("[bold green]02. Digital Product Adoption[/]: Designed to seamlessly cross-sell integrated digital banking products.")

        # Pillar 3
        console.print("[bold magenta]03. Personalised Customer Engagement[/]: Layer 7 Agent translates this dense underwriting math into highly empathetic, tailored explanations for the UI.")
        
        # Pillar 4
        pd_adj = result.get("risk_profile", {}).get("pd_adjusted", "N/A")
        console.print(f"[bold blue]04. Intelligent Financial Interactions[/]: AI calculated strict DTI & PD ({pd_adj}), acting as a fiduciary to mathematically ensure the customer doesn't take on bankrupting debt.")
        
        # Pillar 5
        console.print("[bold white]05. AI-led Banking Journeys[/]: Layer 6 Counterfactual Engine generates 90-day actionable journeys (e.g., 'Save Rs.5K/mo') to convert rejections into future approvals.")
        console.print()

        elapsed = time.time() - start
        console.print()
        console.print(Rule(style="dim cyan"))
        console.print(
            f"  [dim]Pipeline completed in [bold]{elapsed:.1f}s[/] | "
            f"All 7 layers executed | "
            f"Customer memory persisted[/]"
        )
        console.print()

        again = console.input("[bold cyan]Run another case? (y/n): [/]").strip().lower()
        if again != "y":
            break

    console.print()
    console.print("[bold cyan]  Thank you for the demo. — AI Credit Copilot, SBI Hackathon 2026[/]")
    console.print()


if __name__ == "__main__":
    run_demo()

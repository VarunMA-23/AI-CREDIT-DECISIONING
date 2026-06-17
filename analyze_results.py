import json
import time
from rich.console import Console
from rich.progress import track
from rich.table import Table

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from agents.base_agent import call_llm_json

console = Console()

AUDIT_PROMPT = """You are a Senior Banking AI Auditor.
Review the provided Applicant Data and the AI's Final Decision.
Evaluate if the AI's decision is LOGICALLY CORRECT or FLAWED.

It is FLAWED if:
- It 'Fast-Path' approves a loan but the approved amount is less than the requested amount.
- It approves a loan despite massive risk (PD > 15% or 0.15) or impossible DTI.
- It rejects a loan but cites a hallucinated reason that contradicts the math.
- It approves someone under 21 or self-employed under 2.0 years.
Otherwise, it is CORRECT.

Output JSON:
{
  "is_correct": true or false,
  "reason": "1 sentence explanation"
}"""

def main():
    try:
        with open("test_results.json", "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        console.print("[red]test_results.json not found![/]")
        return

    results = data.get("results", [])
    if not results:
        console.print("[red]No results to analyze.[/]")
        return

    console.print(f"[cyan]Auditing {len(results)} cases non-deterministically using LLM...[/]")
    
    correct_count = 0
    wrong_count = 0
    flaws = []

    for case in track(results, description="Auditing..."):
        # Strip out massive unused data to save tokens
        inputs = case.get("data_sources", {})
        frontend = inputs.get("1_frontend_input", {})
        bureau = inputs.get("3_bureau_api", {})
        core = inputs.get("4_core_banking", {})
        
        slim_data = {
            "requested_amount": frontend.get("loan_amount"),
            "credit_score": bureau.get("credit_score"),
            "pd": case.get("ai_output", {}).get("pd_adjusted"),
            "age": inputs.get("2_kyc_api", {}).get("age"),
            "vintage": core.get("employment_years"),
            "employment_type": core.get("employment_type"),
            "decision": case.get("ai_output", {}).get("decision"),
            "binding_constraint": case.get("ai_output", {}).get("binding_constraint", ""),
            "rejection_reason": case.get("ai_output", {}).get("rejection_reason", ""),
            "approved_amount": case.get("ai_output", {}).get("approved_terms", {}).get("amount")
        }

        user_msg = json.dumps(slim_data, indent=2)

        try:
            audit = call_llm_json(AUDIT_PROMPT, user_msg)
            is_correct = audit.get("is_correct", True)
            
            if is_correct:
                correct_count += 1
            else:
                wrong_count += 1
                flaws.append({
                    "seed": case["seed"],
                    "reason": audit.get("reason", "Unknown")
                })
        except Exception as e:
            # If the LLM rate limits or fails, we count it as a crash, not a logic flaw
            console.print(f"[yellow]API Error on seed {case['seed']}: {e}[/]")
            time.sleep(10) # backoff
            continue

        # Rate limit protection
        time.sleep(3)

    console.print("\n[bold magenta]-- Non-Deterministic Audit Summary --[/]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Total Audited", str(correct_count + wrong_count))
    table.add_row("Logically Correct", f"[green]{correct_count}[/]")
    table.add_row("Logically Flawed", f"[red]{wrong_count}[/]")
    console.print(table)

    if flaws:
        console.print("\n[bold red]Detected Flaws:[/]")
        for f in flaws:
            console.print(f"- Seed {f['seed']}: {f['reason']}")
            
    # Save the audit report
    with open("audit_report.json", "w") as f:
        json.dump({"correct": correct_count, "wrong": wrong_count, "flaws": flaws}, f, indent=2)

if __name__ == "__main__":
    main()

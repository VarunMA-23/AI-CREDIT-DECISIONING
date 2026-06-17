import argparse
import random
import time
import json
import traceback
from rich.console import Console
from rich.table import Table
from rich.progress import track

from pipeline import run_pipeline

console = Console()

def mock_customer_input(seed: int) -> dict:
    """Simulates what the customer types into the frontend app."""
    random.seed(seed)
    
    # Valid PAN format: 5 letters, 4 digits, 1 letter
    letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    pan_str = f"{''.join(random.choices(letters, k=5))}{random.randint(1000, 9999)}{random.choice(letters)}"
    
    return {
        "customer_id": f"TEST-CUST-{seed}",
        "loan_amount": round(random.uniform(50000, 2000000), 2),
        "loan_tenure": random.choice([12, 24, 36, 48, 60, 84]),
        "loan_purpose": random.choice(["Personal", "Home", "Car", "Education"]),
        "pan": pan_str
    }

def mock_kyc_api(pan: str, seed: int) -> dict:
    """Simulates hitting NSDL/e-KYC API using the PAN."""
    random.seed(seed + 1000) # Offset seed for different random state
    age = random.randint(18, 65)
    return {
        "name": f"Test Applicant {seed}",
        "age": age,
        "dob": f"{2026 - age}-01-01",
        "address": "India",
        "residency": "IN"
    }

def mock_bureau_api(pan: str, seed: int) -> dict:
    """Simulates hitting CIBIL/Experian API using the PAN."""
    random.seed(seed + 2000)
    credit_score = random.randint(300, 900)
    repayment_history = max(0.0, min(1.0, (credit_score - 300) / 600 + random.uniform(-0.1, 0.1)))
    num_existing_loans = random.randint(0, 5)
    
    return {
        "credit_score": credit_score,
        "repayment_history": round(repayment_history, 2),
        "num_existing_loans": num_existing_loans,
        "recent_applications_30d": random.randint(0, 3)
    }

def mock_core_banking(customer_id: str, seed: int, num_loans: int) -> dict:
    """Simulates fetching internal SBI data."""
    random.seed(seed + 3000)
    income_monthly = random.uniform(15000, 200000)
    existing_emi = random.uniform(0, income_monthly * 0.5) if num_loans > 0 else 0.0
    
    return {
        "savings_balance": round(random.uniform(0, income_monthly * 24), 2),
        "salary_account_linked": random.choice([True, False]),
        "income_monthly": round(income_monthly, 2),
        "employment_type": random.choice(["Salaried", "Self-Employed"]),
        "employment_years": round(random.uniform(0, 20), 1),
        "existing_emi": round(existing_emi, 2),
        "bureau_income_estimate": round(income_monthly * random.uniform(0.8, 1.2), 2),
        "sector": random.choice(["IT", "Finance", "Retail", "Manufacturing", "Healthcare", "Construction"]),
        "has_guarantor": random.choice([True, False]),
        "has_collateral": random.choice([True, False]),
    }

def assemble_applicant_data(seed: int) -> tuple[dict, dict]:
    """
    Calls the mock APIs and assembles the final applicant dictionary.
    Returns: (applicant_dict, data_sources_log)
    """
    # 1. Customer Input
    frontend_data = mock_customer_input(seed)
    
    # 2. KYC API
    kyc_data = mock_kyc_api(frontend_data["pan"], seed)
    
    # 3. Credit Bureau API
    bureau_data = mock_bureau_api(frontend_data["pan"], seed)
    
    # 4. Internal Core Banking
    core_banking_data = mock_core_banking(frontend_data["customer_id"], seed, bureau_data["num_existing_loans"])
    
    # Assemble final
    applicant = {**frontend_data, **kyc_data, **bureau_data, **core_banking_data}
    
    # Log the exact source breakdown
    data_sources = {
        "1_frontend_input": frontend_data,
        "2_kyc_api": kyc_data,
        "3_bureau_api": bureau_data,
        "4_core_banking": core_banking_data
    }
    
    return applicant, data_sources


def run_fuzz_tests(num_cases: int, specific_seed: int = None):
    """Runs a suite of randomized inputs against the black-box AI pipeline."""
    if specific_seed is not None:
        console.print(f"[bold cyan]Starting AI Credit Copilot API Mock Simulator (Single Seed: {specific_seed})[/]")
        seeds_to_run = [specific_seed]
        num_cases = 1
    else:
        console.print(f"[bold cyan]Starting AI Credit Copilot API Mock Simulator ({num_cases} cases)[/]")
        seeds_to_run = range(1, num_cases + 1)
    
    stats = {
        "total": num_cases,
        "success": 0,
        "crashed": 0,
        "APPROVED": 0,
        "REJECTED": 0,
        "CONDITIONAL": 0,
        "total_time_s": 0.0
    }
    failed_seeds = {}
    audit_log = []

    start_time = time.time()

    for seed in track(seeds_to_run, description="Simulating Flow..."):
        applicant, data_sources = assemble_applicant_data(seed)
        
        try:
            case_start = time.time()
            result = run_pipeline(applicant)
            
            # --- Validations ---
            assert isinstance(result, dict), "Result must be a dictionary"
            assert "final_decision" in result, "Result missing 'final_decision'"
            
            decision = result["final_decision"]
            assert decision in ["APPROVED", "REJECTED", "CONDITIONAL"], f"Invalid decision state: {decision}"
            
            if decision in ["APPROVED", "CONDITIONAL"]:
                assert "selected_point" in result and result["selected_point"] is not None, "Missing selected_point on approval"
                pt = result["selected_point"]
                assert "amount" in pt and "rate" in pt and "tenure" in pt, "Selected point missing core terms"
                
            # --- Audit Logging ---
            log_entry = {
                "seed": seed,
                "customer_id": applicant["customer_id"],
                "data_sources": data_sources, # The new detailed breakdown
                "ai_output": {
                    "pd_adjusted": result.get("risk_profile", {}).get("pd_adjusted", "N/A"),
                    "trust_score": result.get("risk_profile", {}).get("trust_score", "N/A"),
                    "decision": decision,
                }
            }
            
            if decision == "REJECTED":
                log_entry["ai_output"]["rejection_reason"] = result.get("rejection_reason", "No reason provided")
                cf = result.get("counterfactual", {})
                if cf and "branch_b" in cf:
                    log_entry["ai_output"]["alternative_offers"] = [b["product_name"] for b in cf["branch_b"] if "APPROVED" in b["status"]]
            else:
                pt = result["selected_point"]
                log_entry["ai_output"]["approved_terms"] = {
                    "amount": pt["amount"],
                    "rate": f"{pt['rate']*100:.1f}%",
                    "tenure": f"{pt['tenure']} months",
                    "emi": pt["emi"]
                }
                log_entry["ai_output"]["binding_constraint"] = result.get("binding_constraint", "none (fast-path)")
            
            audit_log.append(log_entry)

            # If we reached here, the structural assertions passed
            stats["success"] += 1
            stats[decision] = stats.get(decision, 0) + 1
            
        except Exception as e:
            stats["crashed"] += 1
            failed_seeds[seed] = {
                "error": str(e),
                "traceback": traceback.format_exc(),
                "applicant": applicant
            }

        # --- Rate Limiting Protection ---
        # Groq free tier has a requests-per-minute limit. We sleep to avoid 429s.
        time.sleep(4)

    stats["total_time_s"] = time.time() - start_time

    # --- Reporting ---
    console.print("\n[bold magenta]-- Test Run Summary --[/]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric")
    table.add_column("Value")
    
    table.add_row("Total Cases", str(stats["total"]))
    table.add_row("Successful Runs", f"[green]{stats['success']}[/]")
    table.add_row("Crashed/Failed", f"[{'red' if stats['crashed'] > 0 else 'green'}]{stats['crashed']}[/]")
    table.add_row("Approvals", str(stats["APPROVED"]))
    table.add_row("Conditionals", str(stats["CONDITIONAL"]))
    table.add_row("Rejections", str(stats["REJECTED"]))
    
    avg_time = stats["total_time_s"] / num_cases if num_cases > 0 else 0
    table.add_row("Avg Execution Time", f"{avg_time:.2f}s per case")
    
    console.print(table)
    
    # --- Hackathon Pillar Alignment Demo (Single Seed Only) ---
    if specific_seed is not None and len(audit_log) > 0:
        last_run = audit_log[0]
        decision = last_run.get("ai_output", {}).get("decision", "UNKNOWN")
        
        console.print("\n[bold yellow]*** HACKATHON PILLAR ALIGNMENT DEMO ***[/]")
        
        # Pillar 1
        if decision == "CONDITIONAL":
            req_amt = last_run.get("data_sources", {}).get("1_frontend_input", {}).get("loan_amount", 0)
            app_amt = last_run.get("ai_output", {}).get("approved_terms", {}).get("amount", 0)
            console.print(f"[bold cyan]01. Customer Acquisition & Onboarding[/]: Prevented a flat rejection by actively negotiating requested Rs.{req_amt:,.0f} down to an affordable Rs.{app_amt:,.0f}. Bank wins the customer safely!")
        else:
            console.print("[bold cyan]01. Customer Acquisition & Onboarding[/]: Autonomous multi-agent engine evaluates complex applications instantly without human bias.")
            
        # Pillar 2
        alts = last_run.get("ai_output", {}).get("alternative_offers", [])
        if decision == "REJECTED" and alts:
            console.print(f"[bold green]02. Digital Product Adoption[/]: Autonomously cross-sold '{alts[0]}' immediately upon loan rejection to keep the customer active in the SBI digital ecosystem.")
        else:
            console.print("[bold green]02. Digital Product Adoption[/]: Designed to seamlessly cross-sell integrated digital banking products.")

        # Pillar 3
        console.print("[bold magenta]03. Personalised Customer Engagement[/]: Layer 7 Agent translates this dense underwriting math into highly empathetic, tailored explanations for the UI.")
        
        # Pillar 4
        pd_adj = last_run.get("ai_output", {}).get("pd_adjusted", "N/A")
        console.print(f"[bold blue]04. Intelligent Financial Interactions[/]: AI calculated strict DTI & PD ({pd_adj}), acting as a fiduciary to mathematically ensure the customer doesn't take on bankrupting debt.")
        
        # Pillar 5
        console.print("[bold white]05. AI-led Banking Journeys[/]: Layer 6 Counterfactual Engine generates 90-day actionable journeys (e.g., 'Save Rs.5K/mo') to convert rejections into future approvals.")
        console.print("\n")
    
    # Save structured audit log
    with open("test_results.json", "w") as f:
        json.dump({"summary": stats, "results": audit_log}, f, indent=2)
    console.print(f"[bold cyan]i Detailed audit log saved to test_results.json[/]")

    if failed_seeds:
        with open("failed_seeds.json", "w") as f:
            json.dump(failed_seeds, f, indent=2)
        console.print(f"[bold red]! Saved {len(failed_seeds)} failed seeds to failed_seeds.json[/]")
    else:
        console.print("[bold green]OK Zero crashes! Pipeline is structurally solid.[/]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fuzz test the AI Credit Copilot pipeline")
    parser.add_argument("--cases", type=int, default=10, help="Number of random cases to run")
    parser.add_argument("--seed", type=int, default=None, help="Run a specific seed exclusively")
    args = parser.parse_args()
    
    run_fuzz_tests(args.cases, args.seed)

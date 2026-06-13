<div align="center">
  <h1>🏦 AI Credit Copilot</h1>
  <p><strong>A Deep Point-of-Sale (POS) Underwriting & Relationship Agent</strong></p>
  
  ![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
  ![Architecture](https://img.shields.io/badge/Architecture-7--Layer%20Agentic-orange)
  ![License](https://img.shields.io/badge/License-MIT-green.svg)
</div>

<br />

> **AI Credit Copilot** is an autonomous underwriting engine that behaves like a fiduciary Junior Relationship Manager. Instead of issuing flat rejections based on static rules, it utilizes a multi-agent debate system to mathematically assess customer risk in real-time, negotiate safe counter-offers, and actively cross-sell alternative digital products.

## ✨ Core Capabilities

*   **Intelligent Customer Acquisition:** Prevents bank customer drop-off by autonomously generating Pareto-optimal loan counter-offers rather than issuing flat rejections.
*   **Dynamic Digital Cross-Selling:** The embedded *Counterfactual Engine* evaluates alternative banking products (e.g., Digital Savings Accounts) when a primary loan fails, retaining the user in the financial ecosystem.
*   **Mathematical Fiduciary:** Strictly evaluates Debt-to-Income (DTI), Loss Given Default (LGD), and dynamic Probability of Default (PD) to prevent users from taking on bankrupting debt.
*   **Actionable Financial Journeys:** Generates concrete 90-day actionable savings journeys to help rejected users become creditworthy in the future.
*   **Empathetic Engagement:** Translates complex underwriting mathematics into empathetic, personalized narratives via a dedicated *Journey Agent*.

---

## 🏗️ 7-Layer Agentic Architecture

The system is powered by a high-speed, cost-effective LLM pipeline structured into 7 distinct agentic layers:

1.  **Layer 0 (Gatekeeper):** Verifies KYC and checks for fraud/AML indicators.
2.  **Layer 1 (Trust/Scoring):** Generates custom risk & trust scores based on Bureau and Core Banking history.
3.  **Layer 2 (Optimizer):** Generates a multi-dimensional Pareto frontier of feasible loan configurations.
4.  **Layer 3 (Negotiation):** Multi-agent debate between Risk, Sales, and Profitability to select the optimal offer.
5.  **Layer 4 (Stress Test):** Simulates economic shocks (e.g., job loss, rate hikes) on the customer's capacity to repay.
6.  **Layer 5 (Compliance):** Enforces strict regulatory frameworks (e.g., Age limits, Self-Employed vintage).
7.  **Layer 6 & 7 (Counterfactual & Journey):** Cross-sells digital products and explains the final decision empathetically.

---

## 🚀 Setup & Installation

### 1. Prerequisites
Ensure you have Python 3.10+ installed on your system. You will also need an API key from Groq or OpenAI to power the LLM inference engine.

### 2. Environment Setup
```bash
# Clone the repository
git clone https://github.com/your-username/ai-credit-copilot.git
cd ai-credit-copilot

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

# Install required dependencies
pip install -r requirements.txt
```

### 3. Configuration
Set your API key as an environment variable before running the application:
```bash
# On Mac/Linux
export GROQ_API_KEY="your_api_key_here"

# On Windows (Command Prompt)
set GROQ_API_KEY=your_api_key_here

# On Windows (PowerShell)
$env:GROQ_API_KEY="your_api_key_here"
```

---

## 💻 Usage & Testing

### Interactive Terminal UI
To run the main visual presentation and watch the 7-layer pipeline execute in real-time on a simulated applicant:
```bash
python cli_demo.py
```

### Batch Fuzz Testing
To prove the system's robustness at scale, the autonomous fuzz tester randomly generates applications, processes them through the pipeline, and ensures mathematical consistency and zero logic crashes.
```bash
# Run 10 random applications automatically
python test_runner.py --cases 10

# Reproduce a specific edge-case seed
python test_runner.py --seed 1025
```

### Non-Deterministic AI Auditing
To verify the logical consistency of the pipeline outputs, you can spawn an "Audit Agent" that reads through your `test_results.json` log. It verifies that the AI didn't hallucinate or make mathematically contradictory decisions.
```bash
python analyze_results.py
```

---
<div align="center">
  <p>Built with ❤️ for the future of intelligent banking.</p>
</div>

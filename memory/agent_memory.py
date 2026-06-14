"""
Agent Memory — In-memory rolling log for department agents.
Stores cohort-level calibration observations (soft adjustments, not model retraining).
"""
from collections import deque
from datetime import datetime

# Per-agent rolling window (last 100 observations)
_MEMORY: dict[str, deque] = {
    "risk":           deque(maxlen=100),
    "sales":          deque(maxlen=100),
    "profitability":  deque(maxlen=100),
    "portfolio":      deque(maxlen=100),
    "collections":    deque(maxlen=100),
}

# Pre-seeded with realistic observations for demo richness
_MEMORY["risk"].append({
    "ts": "2026-05-01",
    "note": "Young freelancer cohort — actual defaults trending 15% below predicted"
})
_MEMORY["sales"].append({
    "ts": "2026-05-15",
    "note": "Co-applicant offers — 34% acceptance rate this month"
})
_MEMORY["portfolio"].append({
    "ts": "2026-06-01",
    "note": "Cohort 'Stable Saver' approaching concentration limit (14.2% / 15%)"
})
_MEMORY["collections"].append({
    "ts": "2026-05-20",
    "note": "Salary-linked accounts show 22% better recovery vs non-linked"
})


def log_observation(agent: str, note: str):
    if agent in _MEMORY:
        _MEMORY[agent].append({"ts": datetime.utcnow().isoformat(), "note": note})


def get_context(agent: str, last_n: int = 5) -> list[dict]:
    """Return last N observations for an agent to prepend to its LLM prompt."""
    if agent not in _MEMORY:
        return []
    items = list(_MEMORY[agent])
    return items[-last_n:]


def get_all() -> dict:
    return {k: list(v) for k, v in _MEMORY.items()}

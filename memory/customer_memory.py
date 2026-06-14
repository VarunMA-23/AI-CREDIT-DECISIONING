"""
Customer Memory — SQLite-backed persistent store for applicant history.
"""
import json
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Float, Integer, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "customer_memory.db")

class CustomerApplication(Base):
    __tablename__ = "applications"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    customer_id     = Column(String(50), index=True)
    application_date= Column(DateTime, default=datetime.utcnow)
    decision        = Column(String(20))   # APPROVED / REJECTED / CONDITIONAL / PENDING
    reason          = Column(Text)
    credit_score    = Column(Float)
    income_monthly  = Column(Float)
    savings_balance = Column(Float)
    loan_amount     = Column(Float)
    trust_score     = Column(Float)
    extra_json      = Column(Text)         # JSON blob for extra fields


engine  = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
Session = sessionmaker(bind=engine)

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    Base.metadata.create_all(engine)

def save_application(customer_id: str, decision: str, reason: str,
                     credit_score: float, income_monthly: float,
                     savings_balance: float, loan_amount: float,
                     trust_score: float = 0.0, extra: dict = None):
    init_db()
    with Session() as s:
        # Bug Fix: Update existing record instead of appending duplicates to prevent trust score drift
        rec = s.query(CustomerApplication).filter_by(customer_id=customer_id).first()
        if not rec:
            rec = CustomerApplication(customer_id=customer_id)
            s.add(rec)
            
        rec.application_date = datetime.utcnow()
        rec.decision = decision
        rec.reason = reason
        rec.credit_score = credit_score
        rec.income_monthly = income_monthly
        rec.savings_balance = savings_balance
        rec.loan_amount = loan_amount
        rec.trust_score = trust_score
        rec.extra_json = json.dumps(extra or {})
        
        s.commit()

def get_history(customer_id: str) -> list[dict]:
    init_db()
    with Session() as s:
        rows = (s.query(CustomerApplication)
                  .filter_by(customer_id=customer_id)
                  .order_by(CustomerApplication.application_date)
                  .all())
        return [
            {
                "date": r.application_date.isoformat(),
                "decision": r.decision,
                "reason": r.reason,
                "credit_score": r.credit_score,
                "income_monthly": r.income_monthly,
                "savings_balance": r.savings_balance,
                "loan_amount": r.loan_amount,
                "trust_score": r.trust_score,
                "extra": json.loads(r.extra_json or "{}"),
            }
            for r in rows
        ]

"""
Synthetic Credit Data Generator + XGBoost Model Trainer
Generates 10,000 synthetic loan applicants and trains a PD model.
Run this once: python data/synthetic_training.py
"""
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
import xgboost as xgb
import joblib
import os

np.random.seed(42)
N = 10_000

def generate_data(n=N):
    credit_score     = np.random.normal(650, 80, n).clip(300, 900)
    income_monthly   = np.random.lognormal(10.5, 0.5, n).clip(10000, 500000)
    employment_years = np.random.gamma(3, 2, n).clip(0, 40)
    existing_emi     = np.random.exponential(3000, n).clip(0, 50000)
    num_existing_loans = np.random.poisson(1.2, n).clip(0, 8)
    savings_balance  = np.random.lognormal(9, 1.2, n).clip(0, 1000000)
    repayment_history = np.random.beta(8, 2, n)          # 0-1, higher=better
    age              = np.random.normal(38, 10, n).clip(21, 70)
    loan_amount      = np.random.lognormal(12, 0.8, n).clip(50000, 2000000)
    loan_tenure      = np.random.choice([12,24,36,48,60,84], n)
    has_guarantor    = np.random.binomial(1, 0.15, n)
    has_collateral   = np.random.binomial(1, 0.20, n)

    dti = existing_emi / income_monthly.clip(1)

    # PD logit — realistic feature weights
    logit = (
        -4.0
        - 0.005  * (credit_score - 650)
        - 0.0000015 * income_monthly
        + 0.04   * dti * 100
        - 0.06   * employment_years
        + 0.15   * num_existing_loans
        - 0.003  * savings_balance / 1000
        - 2.0    * repayment_history
        - 0.02   * (age - 38)
        + 0.0000008 * loan_amount
        - 0.3    * has_guarantor
        - 0.4    * has_collateral
        + np.random.normal(0, 0.3, n)
    )
    pd_true = 1 / (1 + np.exp(-logit))
    default = (np.random.uniform(0, 1, n) < pd_true).astype(int)

    df = pd.DataFrame({
        'credit_score': credit_score,
        'income_monthly': income_monthly,
        'employment_years': employment_years,
        'existing_emi': existing_emi,
        'num_existing_loans': num_existing_loans,
        'savings_balance': savings_balance,
        'repayment_history': repayment_history,
        'age': age,
        'loan_amount': loan_amount,
        'loan_tenure': loan_tenure,
        'has_guarantor': has_guarantor,
        'has_collateral': has_collateral,
        'dti': dti,
        'default': default
    })
    return df


FEATURES = [
    'credit_score','income_monthly','employment_years','existing_emi',
    'num_existing_loans','savings_balance','repayment_history','age',
    'loan_amount','loan_tenure','has_guarantor','has_collateral','dti'
]

def train():
    print("Generating synthetic data...")
    df = generate_data()
    default_rate = df['default'].mean()
    print(f"  Samples: {len(df):,}  |  Default rate: {default_rate:.1%}")

    X = df[FEATURES]
    y = df['default']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=(y==0).sum()/(y==1).sum(),
        eval_metric='auc',
        random_state=42,
        verbosity=0,
    )
    print("Training XGBoost model...")
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    preds = model.predict_proba(X_test)[:,1]
    auc = roc_auc_score(y_test, preds)
    print(f"  AUC-ROC: {auc:.4f}")

    os.makedirs("models", exist_ok=True)
    joblib.dump(model, "models/credit_risk_model.pkl")
    joblib.dump(FEATURES, "models/feature_names.pkl")
    print("  Model saved → models/credit_risk_model.pkl")
    return model


if __name__ == "__main__":
    train()

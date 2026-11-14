import uuid
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app


def test_loan_amortization_emi_payment_and_risk_scoring():
    with TestClient(app) as client:
        tag = uuid.uuid4().hex[:6]
        email = f"loanuser.{tag}@finora.io"
        password = "Password123"

        client.post(
            "/api/v1/auth/register",
            json={"email": email, "full_name": "Surya Loan User", "password": password},
        )
        token = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Open Savings Account with 5,000 INR
        acc = client.post(
            "/api/v1/accounts",
            headers=headers,
            json={"account_type": "SAVINGS", "currency": "INR", "initial_deposit": "5000.00"},
        ).json()
        acc_no = acc["account_number"]

        # 2. Apply for 12-month Education Loan of 120,000 INR
        loan_res = client.post(
            "/api/v1/loans/apply",
            headers=headers,
            json={
                "disbursement_account_number": acc_no,
                "loan_type": "EDUCATION",
                "principal_amount": "120000.00",
                "tenure_months": 12,
                "purpose": "B.Tech Data Science Tuition",
            },
        )
        assert loan_res.status_code == 201
        loan = loan_res.json()
        assert len(loan["installments"]) == 12
        assert Decimal(loan["emi_amount"]) > Decimal("10000.0000")

        # Verify balance increased to 125,000.0000 after disbursement
        acc_after = client.get(f"/api/v1/accounts/{acc_no}", headers=headers).json()
        assert Decimal(acc_after["available_balance"]) == Decimal("125000.0000")

        # 3. Pay first EMI installment
        pay_res = client.post(
            f"/api/v1/loans/{loan['loan_number']}/pay-emi",
            headers=headers,
        )
        assert pay_res.status_code == 200
        assert pay_res.json()["status"] == "PAID"

        # 4. Evaluate High-Value Risk Alert (300,000 INR >= 250,000 threshold)
        risk_res = client.post(
            "/api/v1/risk/evaluate",
            headers=headers,
            json={
                "account_number": acc_no,
                "amount": "300000.00",
                "transaction_reference": "TXN-TEST-999",
            },
        )
        assert risk_res.status_code == 201
        risk_data = risk_res.json()
        assert risk_data["severity"] in ("HIGH", "CRITICAL")
        assert "HIGH_VALUE_THRESHOLD_EXCEEDED" in risk_data["rule_triggered"]
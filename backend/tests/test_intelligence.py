import uuid
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app


def test_ml_insights_categorization_forecast_and_savings_goal():
    with TestClient(app) as client:
        tag = uuid.uuid4().hex[:6]
        email = f"aiuser.{tag}@finora.io"
        password = "Password123"

        client.post(
            "/api/v1/auth/register",
            json={"email": email, "full_name": "Surya AI Analyst", "password": password},
        )
        token = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Open Savings Account & post varied transactions
        acc = client.post(
            "/api/v1/accounts",
            headers=headers,
            json={"account_type": "SAVINGS", "currency": "INR", "initial_deposit": "40000.00"},
        ).json()
        acc_no = acc["account_number"]

        client.post(
            "/api/v1/transactions/deposit",
            headers=headers,
            json={"account_number": acc_no, "amount": "20000.00", "description": "Monthly Salary"},
        )
        client.post(
            "/api/v1/transactions/withdraw",
            headers=headers,
            json={"account_number": acc_no, "amount": "3500.00", "description": "Swiggy food order"},
        )
        client.post(
            "/api/v1/transactions/withdraw",
            headers=headers,
            json={"account_number": acc_no, "amount": "4500.00", "description": "Electricity bill"},
        )

        # 2. Fetch ML Financial Insights & 30-day Cash-Flow Forecast
        insights_res = client.get(
            f"/api/v1/intelligence/insights/{acc_no}", headers=headers
        )
        assert insights_res.status_code == 200
        data = insights_res.json()
        assert 10 <= data["financial_health_score"] <= 100
        assert len(data["spending_by_category"]) >= 2
        assert len(data["thirty_day_forecast"]) == 4

        # 3. Compute Savings Goal Plan
        goal_res = client.post(
            "/api/v1/intelligence/savings-goal",
            headers=headers,
            json={
                "account_number": acc_no,
                "goal_name": "Emergency Reserve Fund",
                "target_amount": "150000.00",
                "months_to_goal": 12,
            },
        )
        assert goal_res.status_code == 200
        goal_data = goal_res.json()
        assert goal_data["feasibility_status"] == "ON_TRACK_PLAN_READY"
        assert Decimal(goal_data["required_monthly_contribution"]) > Decimal("0.0000")
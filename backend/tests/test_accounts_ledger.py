from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app


def test_account_creation_double_entry_and_interest():
    with TestClient(app) as client:
        email = "nikhil.finora@example.com"
        password = "Password123"

        client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "full_name": "S. Nikhil",
                "password": password,
            },
        )
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. Create Savings Account with opening deposit
        acc_res = client.post(
            "/api/v1/accounts",
            headers=headers,
            json={
                "account_type": "SAVINGS",
                "currency": "INR",
                "nickname": "Primary Savings",
                "initial_deposit": "55000.00",
            },
        )
        assert acc_res.status_code == 201
        account = acc_res.json()
        acc_no = account["account_number"]
        assert Decimal(account["available_balance"]) == Decimal("55000.0000")
        assert Decimal(account["ledger_balance"]) == Decimal("55000.0000")

        # 2. Verify double-entry CREDIT line exists
        ledger_res = client.get(f"/api/v1/accounts/{acc_no}/ledger", headers=headers)
        assert ledger_res.status_code == 200
        entries = ledger_res.json()
        assert len(entries) == 1
        assert entries[0]["direction"] == "CREDIT"
        assert Decimal(entries[0]["amount"]) == Decimal("55000.0000")

        # 3. Verify 4% annual interest calculation (55000 * 0.04 = 2200.0000)
        int_res = client.get(
            f"/api/v1/accounts/{acc_no}/interest-projection", headers=headers
        )
        assert int_res.status_code == 200
        assert Decimal(int_res.json()["projected_annual_interest"]) == Decimal("2200.0000")

        # 4. Prevent closing account with non-zero balance
        close_fail = client.patch(
            f"/api/v1/accounts/{acc_no}",
            headers=headers,
            json={"status": "CLOSED"},
        )
        assert close_fail.status_code == 400
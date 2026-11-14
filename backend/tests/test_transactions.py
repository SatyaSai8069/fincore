import uuid
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app


def _register_and_login(client: TestClient, email: str, name: str) -> dict[str, str]:
    password = "Password123"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": name, "password": password},
    )
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_deposit_withdraw_transfer_fx_idempotency_and_statement():
    with TestClient(app) as client:
        tag = uuid.uuid4().hex[:6]
        sender_headers = _register_and_login(
            client, f"sender.{tag}@finora.io", "Surya Bareddy"
        )
        receiver_headers = _register_and_login(
            client, f"receiver.{tag}@finora.io", "Anita Rao"
        )

        # 1. Create INR Savings account for sender and INR + USD accounts for receiver
        s_inr = client.post(
            "/api/v1/accounts",
            headers=sender_headers,
            json={"account_type": "SAVINGS", "currency": "INR", "initial_deposit": "10000.00"},
        ).json()

        r_inr = client.post(
            "/api/v1/accounts",
            headers=receiver_headers,
            json={"account_type": "SAVINGS", "currency": "INR", "initial_deposit": "1000.00"},
        ).json()

        r_usd = client.post(
            "/api/v1/accounts",
            headers=receiver_headers,
            json={"account_type": "CURRENT", "currency": "USD", "initial_deposit": "0.00"},
        ).json()

        # 2. Deposit with idempotency key (second call must not double-credit)
        idem_key = f"dep-{tag}"
        dep1 = client.post(
            "/api/v1/transactions/deposit",
            headers=sender_headers,
            json={
                "account_number": s_inr["account_number"],
                "amount": "5000.00",
                "description": "Salary bonus",
                "idempotency_key": idem_key,
            },
        )
        assert dep1.status_code == 201
        dep2 = client.post(
            "/api/v1/transactions/deposit",
            headers=sender_headers,
            json={
                "account_number": s_inr["account_number"],
                "amount": "5000.00",
                "idempotency_key": idem_key,
            },
        )
        assert dep2.status_code == 201
        assert dep1.json()["reference_number"] == dep2.json()["reference_number"]

        # 3. Withdraw 2000 INR -> balance should be 13000.0000
        wd = client.post(
            "/api/v1/transactions/withdraw",
            headers=sender_headers,
            json={
                "account_number": s_inr["account_number"],
                "amount": "2000.00",
                "description": "ATM withdrawal",
            },
        )
        assert wd.status_code == 201
        assert Decimal(wd.json()["source_available_balance"]) == Decimal("13000.0000")

        # 4. Register Beneficiary & Transfer 3000 INR
        ben = client.post(
            "/api/v1/transactions/beneficiaries",
            headers=sender_headers,
            json={
                "beneficiary_account_number": r_inr["account_number"],
                "nickname": "Anita INR",
            },
        )
        assert ben.status_code == 201

        tx = client.post(
            "/api/v1/transactions/transfer",
            headers=sender_headers,
            json={
                "from_account_number": s_inr["account_number"],
                "to_account_number": r_inr["account_number"],
                "amount": "3000.00",
                "description": "Project reimbursement",
            },
        )
        assert tx.status_code == 201
        assert Decimal(tx.json()["source_available_balance"]) == Decimal("10000.0000")
        assert Decimal(tx.json()["target_available_balance"]) == Decimal("4000.0000")

        # 5. Cross-currency FX Transfer (1000 INR -> USD)
        fx_tx = client.post(
            "/api/v1/transactions/transfer",
            headers=sender_headers,
            json={
                "from_account_number": s_inr["account_number"],
                "to_account_number": r_usd["account_number"],
                "amount": "1000.00",
                "description": "USD remittance",
            },
        )
        assert fx_tx.status_code == 201
        assert fx_tx.json()["transaction_type"] == "FX_TRANSFER"
        assert Decimal(fx_tx.json()["converted_amount"]) > Decimal("11.0000")

        # 6. Statement check
        stmt = client.get(
            f"/api/v1/transactions/statement/{s_inr['account_number']}",
            headers=sender_headers,
        )
        assert stmt.status_code == 200
        body = stmt.json()
        assert Decimal(body["total_credits"]) == Decimal("15000.0000")
        assert Decimal(body["total_debits"]) == Decimal("6000.0000")
        assert Decimal(body["current_available_balance"]) == Decimal("9000.0000")
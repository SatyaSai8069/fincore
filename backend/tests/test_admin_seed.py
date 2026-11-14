import asyncio
from fastapi.testclient import TestClient
from app.db.seed import seed_demo_data
from app.main import app


def test_seed_and_admin_governance_overview():
    asyncio.run(seed_demo_data())

    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@finora.io", "password": "Admin@1234"},
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        overview = client.get("/api/v1/admin/overview", headers=headers)
        assert overview.status_code == 200
        data = overview.json()
        assert data["total_customers"] >= 2
        assert data["double_entry_balanced"] is True
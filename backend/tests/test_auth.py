import uuid
import pyotp
from fastapi.testclient import TestClient
from app.main import app


def test_register_login_mfa_and_rbac():
    with TestClient(app) as client:
        email = f"satya.{uuid.uuid4().hex[:6]}@example.com"
        password = "Password123"

        # 1. Register customer
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "full_name": "Satya Sai Bareddy",
                "phone_number": "+919000000001",
                "password": password,
                "kyc_document_ref": "KYC-DEMO-101",
            },
        )
        assert reg.status_code == 201

        # 2. Login
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Profile access
        me_res = client.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["email"] == email

        # 4. RBAC protection: CUSTOMER cannot access ADMIN endpoint
        admin_res = client.get("/api/v1/auth/admin/users", headers=headers)
        assert admin_res.status_code == 403

        # 5. Setup & verify TOTP MFA
        mfa_setup = client.post("/api/v1/auth/mfa/setup", headers=headers)
        assert mfa_setup.status_code == 200
        secret = mfa_setup.json()["secret"]
        code = pyotp.TOTP(secret).now()

        mfa_enable = client.post(
            "/api/v1/auth/mfa/enable",
            headers=headers,
            json={"code": code},
        )
        assert mfa_enable.status_code == 200
        assert mfa_enable.json()["mfa_enabled"] is True
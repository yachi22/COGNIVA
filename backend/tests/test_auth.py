import asyncio
from datetime import timedelta
import uuid
import httpx
from sqlalchemy import select

from app.main import app
from app.core.database import async_engine, AsyncSessionLocal
from app.core.security import create_access_token, verify_password
from app.models.user import User


def test_user_registration_and_password_hashing():
    """
    Test requirements 1 & 2:
    - Register a user.
    - Verify password is encrypted/hashed with bcrypt and never stored as plaintext.
    """
    async def _test():
        test_email = f"auth_test_{uuid.uuid4().hex[:8]}@cogniva.ai"
        plain_password = "SecurePassword123!"
        full_name = "Auth Test User"

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Register user via API
            resp = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": test_email,
                    "password": plain_password,
                    "full_name": full_name,
                },
            )
            assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
            data = resp.json()
            assert data["email"] == test_email
            assert data["full_name"] == full_name
            assert data["is_active"] is True
            assert "password" not in data
            assert "hashed_password" not in data
            user_id = data["id"]

        # 2. Inspect database directly to verify password is never stored as plaintext
        async with AsyncSessionLocal() as session:
            stmt = select(User).where(User.id == uuid.UUID(user_id))
            res = await session.execute(stmt)
            db_user = res.scalar_one()

            assert db_user.hashed_password != plain_password, "Password MUST NOT be stored in plaintext!"
            assert db_user.hashed_password.startswith("$2b$") or db_user.hashed_password.startswith("$2a$"), "Password must be a bcrypt hash!"
            assert verify_password(plain_password, db_user.hashed_password) is True, "Stored hash must verify against original password!"
            assert verify_password("WrongPassword123!", db_user.hashed_password) is False

    asyncio.run(_test())


def test_registration_duplicate_email_rejected():
    """Verify registration rejects existing emails with 400 Bad Request."""
    async def _test():
        test_email = f"dup_{uuid.uuid4().hex[:8]}@cogniva.ai"
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp1 = await client.post(
                "/api/v1/auth/register",
                json={"email": test_email, "password": "Password123!", "full_name": "First User"},
            )
            assert resp1.status_code == 201

            # Second attempt with same email
            resp2 = await client.post(
                "/api/v1/auth/register",
                json={"email": test_email, "password": "DifferentPassword123!"},
            )
            assert resp2.status_code == 400
            assert "already exists" in resp2.json()["detail"].lower()

    asyncio.run(_test())


def test_login_success_and_invalid_credentials():
    """
    Test requirements 3, 4, 5:
    - Login with valid credentials and receive JWT.
    - Reject invalid password.
    - Reject non-existent user.
    """
    async def _test():
        test_email = f"login_test_{uuid.uuid4().hex[:8]}@cogniva.ai"
        plain_password = "CorrectPassword123!"

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Register user
            reg_resp = await client.post(
                "/api/v1/auth/register",
                json={"email": test_email, "password": plain_password},
            )
            assert reg_resp.status_code == 201

            # Login with valid credentials
            login_resp = await client.post(
                "/api/v1/auth/login",
                json={"email": test_email, "password": plain_password},
            )
            assert login_resp.status_code == 200
            token_data = login_resp.json()
            assert "access_token" in token_data
            assert token_data["token_type"] == "bearer"
            assert token_data["expires_in"] > 0
            assert len(token_data["access_token"]) > 20

            # Login with incorrect password
            bad_pw_resp = await client.post(
                "/api/v1/auth/login",
                json={"email": test_email, "password": "WrongPassword123!"},
            )
            assert bad_pw_resp.status_code == 401
            assert "incorrect" in bad_pw_resp.json()["detail"].lower()

            # Login with non-existent user
            non_existent_resp = await client.post(
                "/api/v1/auth/login",
                json={"email": "nonexistent_user@cogniva.ai", "password": plain_password},
            )
            assert non_existent_resp.status_code == 401

            # Form-based OAuth2 login (/api/v1/auth/token)
            form_resp = await client.post(
                "/api/v1/auth/token",
                data={"username": test_email, "password": plain_password},
            )
            assert form_resp.status_code == 200
            assert "access_token" in form_resp.json()

    asyncio.run(_test())


def test_protected_routes_and_token_resolution():
    """
    Test requirements 6, 7, 8, 9:
    - Access protected endpoint with valid JWT.
    - Reject protected endpoint without token.
    - Reject invalid or expired token.
    - Verify authenticated user is correctly resolved from token.
    """
    async def _test():
        test_email = f"protected_{uuid.uuid4().hex[:8]}@cogniva.ai"
        plain_password = "SecretPassword123!"

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Register & login
            reg_resp = await client.post(
                "/api/v1/auth/register",
                json={"email": test_email, "password": plain_password, "full_name": "Protected Tester"},
            )
            assert reg_resp.status_code == 201
            user_id = reg_resp.json()["id"]

            login_resp = await client.post(
                "/api/v1/auth/login",
                json={"email": test_email, "password": plain_password},
            )
            token = login_resp.json()["access_token"]

            # 2. Access protected endpoint with valid JWT (Requirement 6 & 9)
            auth_headers = {"Authorization": f"Bearer {token}"}
            me_resp = await client.get("/api/v1/auth/me", headers=auth_headers)
            assert me_resp.status_code == 200
            me_data = me_resp.json()
            assert me_data["id"] == user_id
            assert me_data["email"] == test_email
            assert me_data["full_name"] == "Protected Tester"

            # Access /protected route
            prot_resp = await client.get("/api/v1/auth/protected", headers=auth_headers)
            assert prot_resp.status_code == 200
            assert prot_resp.json()["status"] == "authenticated"
            assert prot_resp.json()["user_id"] == user_id

            # 3. Reject protected endpoint without token (Requirement 7)
            no_token_resp = await client.get("/api/v1/auth/me")
            assert no_token_resp.status_code == 401

            # 4. Reject malformed / invalid token (Requirement 8)
            bad_token_resp = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer this-is-not-a-valid-token"},
            )
            assert bad_token_resp.status_code == 401

            # 5. Reject expired token (Requirement 8)
            expired_token = create_access_token(
                subject=user_id,
                expires_delta=timedelta(seconds=-60),  # expired 60 seconds ago
            )
            expired_resp = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {expired_token}"},
            )
            assert expired_resp.status_code == 401

    asyncio.run(_test())

"""
Tests for Authentication Endpoints

This module demonstrates:
- Testing user registration
- Testing login flow
- Testing protected endpoints
- Testing API key management
"""

import uuid

from fastapi.testclient import TestClient


class TestUserRegistration:
    """Tests for user registration endpoint."""

    def test_register_success(self, client: TestClient) -> None:
        """Test successful user registration."""
        unique_email = f"newuser_{uuid.uuid4().hex[:8]}@example.com"

        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": unique_email,
                "password": "SecurePass123",
                "full_name": "New User",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == unique_email
        assert data["full_name"] == "New User"
        assert data["is_active"] is True
        assert data["is_verified"] is False
        assert "id" in data
        assert "hashed_password" not in data  # Should not expose password

    def test_register_duplicate_email(self, client: TestClient) -> None:
        """Test registration fails with duplicate email."""
        unique_email = f"duplicate_{uuid.uuid4().hex[:8]}@example.com"

        # First registration should succeed
        response1 = client.post(
            "/api/v1/auth/register",
            json={
                "email": unique_email,
                "password": "SecurePass123",
            },
        )
        assert response1.status_code == 201

        # Second registration with same email should fail
        response2 = client.post(
            "/api/v1/auth/register",
            json={
                "email": unique_email,
                "password": "DifferentPass123",
            },
        )
        assert response2.status_code == 400
        assert "already registered" in response2.json()["detail"].lower()

    def test_register_invalid_email(self, client: TestClient) -> None:
        """Test registration fails with invalid email format."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "SecurePass123",
            },
        )
        assert response.status_code == 422  # Validation error

    def test_register_weak_password(self, client: TestClient) -> None:
        """Test registration fails with weak password."""
        unique_email = f"weakpass_{uuid.uuid4().hex[:8]}@example.com"

        # Too short
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": unique_email,
                "password": "short",
            },
        )
        assert response.status_code == 422

    def test_register_password_requirements(self, client: TestClient) -> None:
        """Test password must meet requirements."""
        unique_email = f"passreq_{uuid.uuid4().hex[:8]}@example.com"

        # Missing uppercase
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": unique_email,
                "password": "alllowercase123",
            },
        )
        assert response.status_code == 422


class TestLogin:
    """Tests for login endpoint."""

    def test_login_success(self, client: TestClient) -> None:
        """Test successful login returns token."""
        unique_email = f"logintest_{uuid.uuid4().hex[:8]}@example.com"

        # Register first
        client.post(
            "/api/v1/auth/register",
            json={
                "email": unique_email,
                "password": "SecurePass123",
            },
        )

        # Login
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": unique_email,
                "password": "SecurePass123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    def test_login_wrong_password(self, client: TestClient) -> None:
        """Test login fails with wrong password."""
        unique_email = f"wrongpass_{uuid.uuid4().hex[:8]}@example.com"

        # Register
        client.post(
            "/api/v1/auth/register",
            json={
                "email": unique_email,
                "password": "SecurePass123",
            },
        )

        # Login with wrong password
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": unique_email,
                "password": "WrongPassword123",
            },
        )

        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    def test_login_nonexistent_user(self, client: TestClient) -> None:
        """Test login fails for non-existent user."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "SomePassword123",
            },
        )

        assert response.status_code == 401


class TestProtectedEndpoints:
    """Tests for endpoints that require authentication."""

    def test_get_me_authenticated(self, client: TestClient, auth_headers: dict) -> None:
        """Test /me endpoint with valid authentication."""
        response = client.get("/api/v1/auth/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "email" in data
        assert "id" in data

    def test_get_me_unauthenticated(self, client: TestClient) -> None:
        """Test /me endpoint without authentication."""
        response = client.get("/api/v1/auth/me")

        assert response.status_code == 401

    def test_get_me_invalid_token(self, client: TestClient) -> None:
        """Test /me endpoint with invalid token."""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"},
        )

        assert response.status_code == 401


class TestAPIKeys:
    """Tests for API key management."""

    def test_create_api_key(self, client: TestClient, auth_headers: dict) -> None:
        """Test creating a new API key."""
        response = client.post(
            "/api/v1/auth/api-keys",
            headers=auth_headers,
            json={
                "name": "Test Key",
                "expires_in_days": 30,
                "scopes": ["read", "write"],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Key"
        assert "key" in data  # Full key only shown once
        assert data["key"].startswith("vv_")
        assert "key_prefix" in data
        assert data["is_active"] is True
        assert data["scopes"] == ["read", "write"]

    def test_list_api_keys(self, client: TestClient, auth_headers: dict) -> None:
        """Test listing user's API keys."""
        # Create a key first
        client.post(
            "/api/v1/auth/api-keys",
            headers=auth_headers,
            json={"name": "List Test Key"},
        )

        # List keys
        response = client.get("/api/v1/auth/api-keys", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should have at least the key we just created
        assert len(data) >= 1
        # Keys in list should not expose full key
        for key in data:
            assert "key" not in key or not key.get("key", "").startswith("vv_")

    def test_authenticate_with_api_key(self, client: TestClient, auth_headers: dict) -> None:
        """Test authenticating with API key instead of JWT."""
        # Create API key
        create_response = client.post(
            "/api/v1/auth/api-keys",
            headers=auth_headers,
            json={"name": "Auth Test Key"},
        )
        api_key = create_response.json()["key"]

        # Use API key to access protected endpoint
        response = client.get(
            "/api/v1/auth/me",
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 200

    def test_revoke_api_key(self, client: TestClient, auth_headers: dict) -> None:
        """Test revoking an API key."""
        # Create API key
        create_response = client.post(
            "/api/v1/auth/api-keys",
            headers=auth_headers,
            json={"name": "Revoke Test Key"},
        )
        key_id = create_response.json()["id"]
        api_key = create_response.json()["key"]

        # Verify key works
        assert client.get(
            "/api/v1/auth/me", headers={"X-API-Key": api_key}
        ).status_code == 200

        # Revoke the key
        revoke_response = client.delete(
            f"/api/v1/auth/api-keys/{key_id}",
            headers=auth_headers,
        )
        assert revoke_response.status_code == 204

        # Verify key no longer works
        assert client.get(
            "/api/v1/auth/me", headers={"X-API-Key": api_key}
        ).status_code == 401

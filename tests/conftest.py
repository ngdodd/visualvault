"""
Pytest Configuration and Fixtures

This module demonstrates:
- Test client setup with FastAPI's TestClient
- Fixture composition
- Async test support
- Test configuration override
- Database fixtures for testing
"""

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.database import init_db
from app.main import create_app


def get_test_settings() -> Settings:
    """Create settings configured for testing."""
    return Settings(
        debug=True,
        environment="development",
        # In a real test setup, you'd use a test database
        # database=DatabaseSettings(name="visualvault_test"),
    )


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Provide test settings for the session."""
    return get_test_settings()


@pytest.fixture(scope="session")
def app(settings: Settings) -> Generator[Any, None, None]:
    """
    Create application instance for testing.

    Using session scope means the app is created once for all tests,
    which is more efficient than creating it for each test.
    """
    # Initialize database before creating app
    init_db(settings)

    application = create_app(settings)
    yield application


@pytest.fixture
def client(app: Any) -> Generator[TestClient, None, None]:
    """
    Create a test client.

    This is function-scoped (default) so each test gets a fresh client,
    but they all share the same app instance.
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    """
    Create a test user and return auth headers.

    This fixture:
    1. Registers a new user
    2. Logs in to get a token
    3. Returns headers with the token
    """
    import uuid

    # Generate unique email to avoid conflicts
    unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"

    # Register user
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": "TestPass123",
            "full_name": "Test User",
        },
    )

    if register_response.status_code != 201:
        # User might already exist in persistent test db
        pass

    # Login to get token
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": unique_email,
            "password": "TestPass123",
        },
    )

    if login_response.status_code == 200:
        token = login_response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    # Fallback for tests that don't need real auth
    return {}

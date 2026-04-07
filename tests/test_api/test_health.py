"""
Tests for Health Check Endpoints

This module demonstrates:
- Basic API endpoint testing
- Response schema validation
- Status code assertions
- Testing with TestClient
"""

from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Test suite for health check endpoints."""

    def test_basic_health_check(self, client: TestClient) -> None:
        """Test the basic health endpoint returns 200 and correct structure."""
        response = client.get("/api/v1/health")

        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

    def test_health_check_version_matches(
        self, client: TestClient, settings
    ) -> None:
        """Test that health check returns correct app version."""
        response = client.get("/api/v1/health")
        data = response.json()

        assert data["version"] == settings.app_version

    def test_readiness_check(self, client: TestClient) -> None:
        """Test the detailed readiness endpoint."""
        response = client.get("/api/v1/health/ready")

        assert response.status_code == 200

        data = response.json()
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert "timestamp" in data
        assert "version" in data
        assert "environment" in data
        assert "components" in data

        # Check component structure
        components = data["components"]
        assert "database" in components
        assert "redis" in components
        assert "storage" in components
        assert "ml_models" in components

    def test_readiness_check_component_structure(self, client: TestClient) -> None:
        """Test that each component has the expected fields."""
        response = client.get("/api/v1/health/ready")
        data = response.json()

        for component_name, component in data["components"].items():
            assert "status" in component, f"{component_name} missing status"
            # latency_ms and message are optional


class TestHealthCheckResponses:
    """Test health check response formats."""

    def test_health_response_is_json(self, client: TestClient) -> None:
        """Test that health endpoints return JSON."""
        response = client.get("/api/v1/health")
        assert response.headers["content-type"] == "application/json"

    def test_timestamp_is_iso_format(self, client: TestClient) -> None:
        """Test that timestamps are in ISO format."""
        from datetime import datetime

        response = client.get("/api/v1/health")
        data = response.json()

        # This should not raise an exception
        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

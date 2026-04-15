"""Tests for the API endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with mocked dependencies."""
    from app.main import app
    from app.services.pii_detector import PiiDetector

    # Initialize components that would normally be set up in lifespan
    app.state.pii_detector = PiiDetector()

    # MappingStore: async methods need AsyncMock
    mock_store = MagicMock()
    mock_store.save = AsyncMock(return_value="test-request-id")
    mock_store.load = AsyncMock(return_value={})
    mock_store.delete = AsyncMock()
    mock_store._redis = MagicMock()
    mock_store._redis.ping = AsyncMock(return_value=True)
    app.state.mapping_store = mock_store

    app.state.llm_client = MagicMock()

    return TestClient(app)


class TestHealthEndpoint:
    def test_health_check(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["redis"] == "connected"

    def test_health_check_redis_down(self, client: TestClient):
        app = client.app
        app.state.mapping_store._redis.ping = AsyncMock(
            side_effect=Exception("Connection refused")
        )

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["redis"] == "disconnected"


class TestGenerateEndpoint:
    def test_generate_with_pii(self, client: TestClient):
        app = client.app
        app.state.llm_client.generate = AsyncMock(
            return_value="[EMAIL_1]にメールを送りました"
        )

        response = client.post(
            "/gateway/generate",
            json={"prompt": "test@example.com にメールを送って"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == "test-request-id"
        assert "test@example.com" not in data["masked_prompt"]
        # The response should be unmasked
        assert "test@example.com" in data["llm_response"]

    def test_generate_without_unmask(self, client: TestClient):
        app = client.app
        app.state.llm_client.generate = AsyncMock(
            return_value="[EMAIL_1]にメールを送りました"
        )

        response = client.post(
            "/gateway/generate",
            json={
                "prompt": "test@example.com にメールを送って",
                "unmask_response": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        # Response should remain masked
        assert data["llm_response"] == data["llm_response_raw"]

    def test_generate_no_pii(self, client: TestClient):
        app = client.app
        app.state.llm_client.generate = AsyncMock(
            return_value="はい、いい天気ですね"
        )

        response = client.post(
            "/gateway/generate",
            json={"prompt": "今日はいい天気ですね"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["masked_prompt"] == data["original_prompt"]

    def test_generate_llm_error(self, client: TestClient):
        app = client.app
        app.state.llm_client.generate = AsyncMock(
            side_effect=Exception("LLM unavailable")
        )

        response = client.post(
            "/gateway/generate",
            json={"prompt": "test@example.com にメールして"},
        )
        assert response.status_code == 502

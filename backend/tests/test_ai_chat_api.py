"""Tests for AI Analyst API endpoints."""

from unittest.mock import MagicMock, patch

from api import router
from fastapi import FastAPI
from fastapi.testclient import TestClient

_test_app = FastAPI()
_test_app.include_router(router)
_client = TestClient(_test_app, raise_server_exceptions=False)


class TestAIChatTestEndpoint:
    def test_test_connection_success(self):
        mock_service = MagicMock()

        async def fake_test(overrides=None):
            return {"ok": True, "message": "Claude connection OK"}

        mock_service.test_connection = fake_test

        with patch("api._get_ai_service", return_value=(mock_service, MagicMock())):
            response = _client.post(
                "/api/ai/chat/test",
                json={
                    "provider": "anthropic",
                    "anthropic": {"apiKey": "sk-ant-test"},
                },
            )

        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_test_connection_failure(self):
        mock_service = MagicMock()

        async def fake_test(overrides=None):
            return {"ok": False, "message": "Invalid Anthropic API key."}

        mock_service.test_connection = fake_test

        with patch("api._get_ai_service", return_value=(mock_service, MagicMock())):
            response = _client.post("/api/ai/chat/test", json={})

        assert response.status_code == 200
        assert response.json()["ok"] is False

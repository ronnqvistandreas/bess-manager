"""Tests for GET /api/savings/history."""

import sys
from datetime import date, datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from api import router
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.bess.daily_savings_store import DailySavingsRecord, DailySavingsStore

_test_app = FastAPI()
_test_app.include_router(router)
_client = TestClient(_test_app, raise_server_exceptions=False)

TIMEZONE = ZoneInfo("Europe/Stockholm")


@pytest.fixture()
def mock_controller(tmp_path):
    ctrl = MagicMock()
    ctrl.system.is_configured = True

    store = DailySavingsStore(persist_path=tmp_path / "bess_daily_savings.json")
    store.save_record(
        DailySavingsRecord(
            date=date(2026, 3, 21),
            grid_only_cost=40.0,
            solar_only_cost=30.0,
            optimized_cost=25.0,
            total_savings=15.0,
            solar_savings=10.0,
            battery_contribution=5.0,
            predicted_total_savings=12.0,
            period_count=96,
            complete=True,
            currency="SEK",
            finalized_at=datetime(2026, 3, 22, 0, 5, tzinfo=TIMEZONE),
        )
    )
    store.save_record(
        DailySavingsRecord(
            date=date(2026, 3, 22),
            grid_only_cost=42.0,
            solar_only_cost=31.0,
            optimized_cost=26.0,
            total_savings=16.0,
            solar_savings=11.0,
            battery_contribution=5.0,
            predicted_total_savings=13.0,
            period_count=95,
            complete=False,
            currency="SEK",
            finalized_at=datetime(2026, 3, 23, 0, 5, tzinfo=TIMEZONE),
        )
    )

    ctrl.system.daily_savings_store = store
    ctrl.system.home_settings.currency = "SEK"
    sys.modules["app"].bess_controller = ctrl
    return ctrl


class TestSavingsHistoryApi:
    def test_returns_records_with_currency(self, mock_controller):
        resp = _client.get("/api/savings/history", params={"days": 30})

        assert resp.status_code == 200
        body = resp.json()
        assert body["currency"] == "SEK"
        assert body["count"] == 2
        assert body["records"][0]["date"] == "2026-03-22"
        assert body["records"][0]["totalSavings"] == pytest.approx(16.0)
        assert body["records"][0]["complete"] is False

    def test_days_zero_returns_all_records(self, mock_controller):
        resp = _client.get("/api/savings/history", params={"days": 0})

        assert resp.status_code == 200
        assert resp.json()["count"] == 2

    def test_days_filter_limits_results(self, mock_controller):
        resp = _client.get("/api/savings/history", params={"days": 1})

        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert body["records"][0]["date"] == "2026-03-22"

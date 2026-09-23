"""Integration tests for daily savings rollover finalization."""

from datetime import date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from core.bess.models import DecisionData, EconomicData, EnergyData, PeriodData

TIMEZONE = ZoneInfo("Europe/Stockholm")
YESTERDAY = date(2026, 3, 22)
TODAY = date(2026, 3, 23)


def _actual_period(period_index: int) -> PeriodData:
    return PeriodData(
        period=period_index,
        energy=EnergyData(
            solar_production=1.0,
            home_consumption=0.5,
            battery_charged=0.0,
            battery_discharged=0.0,
            grid_imported=0.0,
            grid_exported=0.5,
            battery_soe_start=15.0,
            battery_soe_end=15.0,
        ),
        timestamp=datetime(2026, 3, 22, 0, 0, tzinfo=TIMEZONE),
        data_source="actual",
        economic=EconomicData(
            buy_price=1.0,
            sell_price=0.5,
            grid_only_cost=10.0,
            solar_only_cost=8.0,
            hourly_cost=7.0,
        ),
        decision=DecisionData(),
    )


class TestDailySavingsRollover:
    def test_finalize_previous_day_on_first_run(self, battery_system, tmp_path):
        savings_path = tmp_path / "bess_daily_savings.json"
        battery_system.daily_savings_store = (
            battery_system.daily_savings_store.__class__(persist_path=savings_path)
        )

        with patch("core.bess.time_utils.today", return_value=YESTERDAY):
            battery_system.historical_store.record_period(0, _actual_period(0))

        with (
            patch("core.bess.time_utils.today", return_value=TODAY),
            patch(
                "core.bess.time_utils.now",
                return_value=datetime(2026, 3, 23, 0, 5, tzinfo=TIMEZONE),
            ),
        ):
            battery_system._finalize_daily_savings_if_needed()

        records = battery_system.daily_savings_store.list_records(days=0)
        assert len(records) == 1
        assert records[0].date == YESTERDAY
        assert records[0].total_savings == pytest.approx(3.0)
        assert battery_system.historical_store.get_stored_count() == 0
        assert battery_system.prediction_snapshot_store.get_snapshot_count() == 0

    def test_skips_finalization_when_store_date_is_today(
        self, battery_system, tmp_path
    ):
        savings_path = tmp_path / "bess_daily_savings.json"
        battery_system.daily_savings_store = (
            battery_system.daily_savings_store.__class__(persist_path=savings_path)
        )

        with patch("core.bess.time_utils.today", return_value=TODAY):
            battery_system.historical_store.record_period(0, _actual_period(0))
            battery_system._finalize_daily_savings_if_needed()

        assert battery_system.daily_savings_store.get_record_count() == 0
        assert battery_system.historical_store.get_stored_count() == 1

"""Unit tests for daily savings finalization aggregation."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from core.bess.daily_savings_store import build_daily_savings_record
from core.bess.daily_view_builder import DailyView
from core.bess.models import DecisionData, EconomicData, EnergyData, PeriodData
from core.bess.prediction_snapshot import PredictionSnapshot

TIMEZONE = ZoneInfo("Europe/Stockholm")
STORE_DATE = date(2026, 3, 23)


def _actual_period(
    period_index: int,
    *,
    grid_only: float,
    solar_only: float,
    optimized: float,
) -> PeriodData:
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
        timestamp=datetime(2026, 3, 23, 0, 0, tzinfo=TIMEZONE),
        data_source="actual",
        economic=EconomicData(
            buy_price=1.0,
            sell_price=0.5,
            grid_only_cost=grid_only,
            solar_only_cost=solar_only,
            hourly_cost=optimized,
        ),
        decision=DecisionData(),
    )


def _snapshot(
    optimization_period: int,
    predicted_savings: float,
    timestamp: datetime,
) -> PredictionSnapshot:
    return PredictionSnapshot(
        snapshot_timestamp=timestamp,
        optimization_period=optimization_period,
        daily_view=DailyView(
            date=STORE_DATE,
            periods=[],
            total_savings=0.0,
            actual_count=0,
            predicted_count=0,
        ),
        growatt_schedule=[],
        predicted_daily_savings=predicted_savings,
    )


class TestBuildDailySavingsRecord:
    def test_aggregates_actual_periods_only(self):
        periods = [
            _actual_period(0, grid_only=10.0, solar_only=8.0, optimized=7.0),
            _actual_period(1, grid_only=20.0, solar_only=15.0, optimized=12.0),
            PeriodData(
                period=2,
                energy=EnergyData(
                    home_consumption=1.0,
                    solar_production=0.0,
                    battery_charged=0.0,
                    battery_discharged=0.0,
                    grid_imported=0.0,
                    grid_exported=0.0,
                    battery_soe_start=15.0,
                    battery_soe_end=15.0,
                ),
                timestamp=datetime(2026, 3, 23, 0, 30, tzinfo=TIMEZONE),
                data_source="predicted",
                economic=EconomicData(
                    buy_price=1.0,
                    sell_price=0.5,
                    grid_only_cost=999.0,
                    solar_only_cost=999.0,
                    hourly_cost=999.0,
                ),
                decision=DecisionData(),
            ),
            None,
        ]

        record = build_daily_savings_record(
            store_date=STORE_DATE,
            periods=periods,
            prediction_snapshots=[],
            currency="SEK",
            finalized_at=datetime(2026, 3, 24, 0, 5, tzinfo=TIMEZONE),
        )

        assert record is not None
        assert record.grid_only_cost == pytest.approx(30.0)
        assert record.solar_only_cost == pytest.approx(23.0)
        assert record.optimized_cost == pytest.approx(19.0)
        assert record.total_savings == pytest.approx(11.0)
        assert record.solar_savings == pytest.approx(7.0)
        assert record.battery_contribution == pytest.approx(4.0)
        assert record.period_count == 2
        assert record.complete is False

    def test_uses_first_prediction_snapshot_of_day(self):
        periods = [
            _actual_period(0, grid_only=10.0, solar_only=8.0, optimized=7.0),
        ]
        snapshots = [
            _snapshot(
                optimization_period=8,
                predicted_savings=12.0,
                timestamp=datetime(2026, 3, 23, 2, 0, tzinfo=TIMEZONE),
            ),
            _snapshot(
                optimization_period=0,
                predicted_savings=14.0,
                timestamp=datetime(2026, 3, 23, 1, 0, tzinfo=TIMEZONE),
            ),
            _snapshot(
                optimization_period=0,
                predicted_savings=99.0,
                timestamp=datetime(2026, 3, 23, 0, 30, tzinfo=TIMEZONE),
            ),
        ]

        record = build_daily_savings_record(
            store_date=STORE_DATE,
            periods=periods,
            prediction_snapshots=snapshots,
            currency="SEK",
        )

        assert record is not None
        assert record.predicted_total_savings == pytest.approx(99.0)

    def test_returns_none_when_no_actual_periods(self):
        record = build_daily_savings_record(
            store_date=STORE_DATE,
            periods=[None, None],
            prediction_snapshots=[],
            currency="SEK",
        )

        assert record is None

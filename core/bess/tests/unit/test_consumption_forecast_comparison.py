"""Tests for consumption forecast comparison across strategies."""

import pytest

from core.bess.battery_system_manager import BatterySystemManager
from core.bess.price_manager import MockSource
from core.bess.settings import PlannedLoadEvent
from core.bess.tests.conftest import MockHomeAssistantController


def _make_bsm() -> BatterySystemManager:
    controller = MockHomeAssistantController()
    source = MockSource([1.0] * 96)
    return BatterySystemManager(
        controller=controller,
        price_source=source,
        addon_options={"inverter": {"platform": "growatt_server_min"}},
    )


def _strategy_by_name(comparison: dict, name: str) -> dict:
    for strat in comparison["strategies"]:
        if strat["name"] == name:
            return strat
    raise KeyError(f"Strategy {name!r} not found")


def test_fixed_planned_events_strategy_is_included():
    bsm = _make_bsm()
    comparison = bsm.get_consumption_forecast_comparison()
    names = [s["name"] for s in comparison["strategies"]]
    assert "fixed_planned_events" in names


def test_fixed_planned_events_matches_fixed_without_events():
    bsm = _make_bsm()
    bsm.home_settings.default_hourly = 4.0
    bsm.home_settings.planned_load_events = []

    comparison = bsm.get_consumption_forecast_comparison()
    fixed = _strategy_by_name(comparison, "fixed")
    fixed_planned = _strategy_by_name(comparison, "fixed_planned_events")

    assert fixed["available"]
    assert fixed_planned["available"]
    assert fixed_planned["forecast"] == fixed["forecast"]


def test_fixed_planned_events_adds_planned_load_in_window():
    bsm = _make_bsm()
    bsm.home_settings.default_hourly = 4.0  # 1.0 kWh per quarter
    bsm.home_settings.planned_load_events = [
        PlannedLoadEvent(
            label="EV", start_period=40, end_period=43, extra_kw=4.0, active=True
        )
    ]

    comparison = bsm.get_consumption_forecast_comparison()
    fixed_planned = _strategy_by_name(comparison, "fixed_planned_events")
    forecast = fixed_planned["forecast"]

    assert forecast is not None
    extra = 4.0 * 0.25
    for p in range(40, 44):
        assert forecast[p] == pytest.approx(1.0 + extra), f"period {p}"
    assert forecast[39] == pytest.approx(1.0)
    assert forecast[44] == pytest.approx(1.0)


def test_fixed_planned_events_respects_solar_guard():
    bsm = _make_bsm()
    bsm.home_settings.default_hourly = 4.0
    bsm.home_settings.planned_load_events = [
        PlannedLoadEvent(
            label="EV",
            start_period=40,
            end_period=43,
            extra_kw=4.0,
            active=True,
            solar_min_kwh=5.0,
        )
    ]
    bsm.controller.solar_forecast = [0.0] * 96

    comparison = bsm.get_consumption_forecast_comparison()
    fixed = _strategy_by_name(comparison, "fixed")
    fixed_planned = _strategy_by_name(comparison, "fixed_planned_events")

    assert fixed_planned["forecast"] == fixed["forecast"]

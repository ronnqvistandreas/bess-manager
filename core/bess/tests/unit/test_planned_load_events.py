"""Tests for the planned high-load event feature.

Verifies that when a planned load event is configured the optimizer sees an
elevated consumption forecast for the event window and therefore pre-charges
before the window when solar (or cheap prices) make it economic.  Behavioural
tests only — no assertions on internal field names or slot counts.
"""

import pytest

from core.bess.battery_system_manager import BatterySystemManager
from core.bess.price_manager import MockSource
from core.bess.settings import PlannedLoadEvent
from core.bess.tests.conftest import MockHomeAssistantController

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bsm(prices: list[float] | None = None) -> BatterySystemManager:
    controller = MockHomeAssistantController()
    source = MockSource(prices if prices is not None else [1.0] * 96)
    bsm = BatterySystemManager(
        controller=controller,
        price_source=source,
        addon_options={"inverter": {"platform": "growatt_server_min"}},
    )
    return bsm


def _flat_solar(value: float = 0.0, length: int = 96) -> list[float]:
    return [value] * length


# ---------------------------------------------------------------------------
# Unit: _apply_planned_load_events
# ---------------------------------------------------------------------------


def test_no_events_leaves_consumption_unchanged():
    bsm = _make_bsm()
    bsm.home_settings.planned_load_events = []
    consumption = [0.5] * 96
    result = bsm._apply_planned_load_events(consumption, _flat_solar(), 0)
    assert result == consumption


def test_active_event_raises_consumption_in_window():
    bsm = _make_bsm()
    bsm.home_settings.planned_load_events = [
        PlannedLoadEvent(
            label="EV", start_period=40, end_period=43, extra_kw=4.0, active=True
        )
    ]
    consumption = [0.5] * 96
    result = bsm._apply_planned_load_events(consumption, _flat_solar(), 0)

    extra = 4.0 * 0.25  # = 1.0 kWh per period
    for p in range(40, 44):
        assert result[p] == pytest.approx(0.5 + extra), f"period {p} not elevated"
    # Periods outside the window are untouched
    assert result[39] == pytest.approx(0.5)
    assert result[44] == pytest.approx(0.5)


def test_inactive_event_leaves_consumption_unchanged():
    bsm = _make_bsm()
    bsm.home_settings.planned_load_events = [
        PlannedLoadEvent(
            label="EV", start_period=40, end_period=43, extra_kw=4.0, active=False
        )
    ]
    consumption = [0.5] * 96
    result = bsm._apply_planned_load_events(consumption, _flat_solar(), 0)
    assert result == consumption


def test_event_with_solar_guard_suppressed_on_no_solar():
    bsm = _make_bsm()
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
    consumption = [0.5] * 96
    # No solar at all
    result = bsm._apply_planned_load_events(consumption, _flat_solar(0.0), 0)
    assert result == consumption


def test_event_with_solar_guard_active_when_enough_solar():
    bsm = _make_bsm()
    bsm.home_settings.planned_load_events = [
        PlannedLoadEvent(
            label="EV",
            start_period=40,
            end_period=43,
            extra_kw=4.0,
            active=True,
            solar_min_kwh=1.0,  # 4 periods x 0.5 kWh = 2 kWh > 1.0 kWh
        )
    ]
    consumption = [0.5] * 96
    result = bsm._apply_planned_load_events(consumption, _flat_solar(0.5), 0)
    extra = 4.0 * 0.25
    for p in range(40, 44):
        assert result[p] == pytest.approx(0.5 + extra)


def test_past_periods_not_modified():
    """Periods before optimization_period must not be modified (hold actuals)."""
    bsm = _make_bsm()
    bsm.home_settings.planned_load_events = [
        PlannedLoadEvent(
            label="EV", start_period=10, end_period=15, extra_kw=4.0, active=True
        )
    ]
    consumption = [0.5] * 96
    # optimization_period = 20 means periods 10-15 are in the past
    result = bsm._apply_planned_load_events(consumption, _flat_solar(), 20)
    for p in range(10, 16):
        assert result[p] == pytest.approx(0.5), f"past period {p} was wrongly modified"

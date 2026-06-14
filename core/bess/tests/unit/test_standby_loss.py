"""Standby loss: fixed pack-side drain while the battery is online above reserve."""

import pytest

from core.bess.dp_battery_algorithm import (
    _build_period_data,
    _state_transition,
    optimize_battery_schedule,
)
from core.bess.settings import BatterySettings


def _battery_settings(**kwargs) -> BatterySettings:
    defaults = {
        "total_capacity": 20.0,
        "min_soc": 20,
        "max_soc": 100,
        "standby_loss_kw": 0.3,
        "min_action_profit_threshold": 0.0,
    }
    defaults.update(kwargs)
    return BatterySettings(**defaults)


def test_idle_hold_drains_soe_when_standby_loss_configured():
    """Holding energy with no solar still costs standby loss from the pack."""
    settings = _battery_settings(standby_loss_kw=0.3)

    next_soe, standby_drain = _state_transition(
        soe=10.0,
        power=0.0,
        battery_settings=settings,
        dt=1.0,
        solar_production=0.0,
        home_consumption=1.0,
    )

    assert standby_drain == pytest.approx(0.3)
    assert next_soe == pytest.approx(9.7)


def test_standby_loss_default_zero_is_no_op():
    """Default standby loss preserves existing optimizer behaviour."""
    settings = _battery_settings(standby_loss_kw=0.0)

    next_soe, standby_drain = _state_transition(
        soe=10.0,
        power=0.0,
        battery_settings=settings,
        dt=1.0,
        solar_production=0.0,
        home_consumption=1.0,
    )

    assert standby_drain == 0.0
    assert next_soe == pytest.approx(10.0)


def test_standby_loss_does_not_drain_below_minimum_reserve():
    """Standby loss stops at minSoe — reserve is not consumed."""
    settings = _battery_settings(standby_loss_kw=0.3)

    next_soe, standby_drain = _state_transition(
        soe=settings.min_soe_kwh,
        power=0.0,
        battery_settings=settings,
        dt=1.0,
        solar_production=0.0,
        home_consumption=1.0,
    )

    assert standby_drain == 0.0
    assert next_soe == pytest.approx(settings.min_soe_kwh)


def test_standby_loss_capped_by_usable_energy_above_reserve():
    """Standby drain cannot exceed energy available above reserve."""
    settings = _battery_settings(standby_loss_kw=0.3)

    next_soe, standby_drain = _state_transition(
        soe=4.1,
        power=0.0,
        battery_settings=settings,
        dt=1.0,
        solar_production=0.0,
        home_consumption=0.5,
    )

    assert standby_drain == pytest.approx(0.1)
    assert next_soe == pytest.approx(settings.min_soe_kwh)


def test_grid_charge_standby_comes_from_pack_not_grid():
    """Parasitic standby during grid charge is pack-side, not extra grid import."""
    settings = _battery_settings(standby_loss_kw=0.3)
    dt = 1.0
    soe = 10.0
    power = 5.0

    next_soe, standby_drain = _state_transition(
        soe=soe,
        power=power,
        battery_settings=settings,
        dt=dt,
        solar_production=0.0,
        home_consumption=1.0,
    )

    period = _build_period_data(
        power=power,
        soe=soe,
        next_soe=next_soe,
        standby_drain_kwh=standby_drain,
        period=0,
        home_consumption=1.0,
        battery_settings=settings,
        dt=dt,
        buy_price=[2.0],
        sell_price=[1.0],
        solar_production=0.0,
        new_cost_basis=0.5,
        currency="SEK",
    )

    assert period.energy.battery_discharged == pytest.approx(0.3)
    assert period.energy.grid_imported == pytest.approx(6.0)


def test_battery_settings_accepts_standby_loss_kw_via_camel_case():
    settings = BatterySettings()
    settings.update(standbyLossKw=0.25)
    assert settings.standby_loss_kw == 0.25


def test_all_idle_schedule_drains_soe_when_standby_configured():
    """Fallback all-IDLE schedule must model standby bleed, not flat SOE."""
    settings = _battery_settings(
        standby_loss_kw=0.3,
        min_action_profit_threshold=999.0,
    )

    result = optimize_battery_schedule(
        buy_price=[1.0, 1.0],
        sell_price=[0.5, 0.5],
        home_consumption=[1.0, 1.0],
        solar_production=[0.0, 0.0],
        initial_soe=10.0,
        battery_settings=settings,
        period_duration_hours=1.0,
    )

    assert result.period_data[0].energy.battery_soe_end == pytest.approx(9.7)
    assert result.period_data[1].energy.battery_soe_end == pytest.approx(9.4)
    assert result.period_data[0].energy.battery_discharged == pytest.approx(0.3)

"""Standby loss: AC-side inverter load; pack debit only when solar cannot cover it."""

import pytest

from core.bess.decision_intelligence import classify_strategic_intent
from core.bess.dp_battery_algorithm import (
    _build_period_data,
    _state_transition,
    optimize_battery_schedule,
)
from core.bess.growatt_min_controller import GrowattMinController
from core.bess.models import EnergyData
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


def test_at_floor_home_consumption_excludes_standby():
    """At minSoe the sensor reads ~standbyLossKw less; DP must use that load."""
    settings = _battery_settings(
        standby_loss_kw=0.3,
        min_action_profit_threshold=999.0,
    )

    result = optimize_battery_schedule(
        buy_price=[1.0],
        sell_price=[0.5],
        home_consumption=[1.0],
        solar_production=[0.0],
        initial_soe=settings.min_soe_kwh,
        battery_settings=settings,
        period_duration_hours=1.0,
    )

    period = result.period_data[0]
    assert period.energy.home_consumption == pytest.approx(0.7)
    assert period.energy.battery_discharged == pytest.approx(0.0)
    assert period.energy.battery_soe_end == pytest.approx(settings.min_soe_kwh)


def test_sunny_idle_does_not_discharge_standby_from_pack():
    """High solar covering measured load (including standby) leaves the pack flat."""
    settings = _battery_settings(
        standby_loss_kw=0.3,
        min_action_profit_threshold=999.0,
    )

    result = optimize_battery_schedule(
        buy_price=[1.0],
        sell_price=[0.5],
        home_consumption=[0.832],
        solar_production=[8.0],
        initial_soe=10.0,
        battery_settings=settings,
        period_duration_hours=1.0,
    )

    period = result.period_data[0]
    assert period.energy.battery_discharged == pytest.approx(0.0, abs=1e-6)
    assert period.energy.battery_soe_end >= period.energy.battery_soe_start


def test_idle_pack_debit_capped_by_solar_deficit():
    """Pack covers only the AC deficit up to standbyLossKw, not a flat 0.3 kW bleed."""
    settings = _battery_settings(standby_loss_kw=0.3)

    next_soe, standby_drain = _state_transition(
        soe=10.0,
        power=0.0,
        battery_settings=settings,
        dt=1.0,
        solar_production=0.75,
        home_consumption=0.832,
    )

    assert standby_drain == pytest.approx(0.082)
    assert next_soe == pytest.approx(9.918)


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


def test_discharge_does_not_add_extra_standby_debit():
    """Strategic discharge already serves AC load including standby; no extra bleed."""
    settings = _battery_settings(standby_loss_kw=0.3)
    dt = 1.0
    soe = 10.0
    power = -1.0

    next_soe, standby_drain = _state_transition(
        soe=soe,
        power=power,
        battery_settings=settings,
        dt=dt,
        solar_production=0.0,
        home_consumption=1.0,
    )

    expected_soe = soe - abs(power) * dt / settings.efficiency_discharge
    assert standby_drain == pytest.approx(0.0)
    assert next_soe == pytest.approx(expected_soe)


def test_night_idle_pack_standby_is_not_double_counted_as_grid_import():
    """AC-side standby served from the pack must not also appear as grid import."""
    settings = _battery_settings(standby_loss_kw=0.3)
    dt = 1.0
    soe = 10.0

    next_soe, standby_drain = _state_transition(
        soe=soe,
        power=0.0,
        battery_settings=settings,
        dt=dt,
        solar_production=0.0,
        home_consumption=1.0,
    )
    period = _build_period_data(
        power=0.0,
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
    assert period.energy.grid_imported == pytest.approx(0.7)


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
    assert period.energy.grid_imported == pytest.approx(5.7)


def test_battery_settings_accepts_standby_loss_kw_via_camel_case():
    settings = BatterySettings()
    settings.update(standbyLossKw=0.25)
    assert settings.standby_loss_kw == 0.25


def _standby_hold_scenario(**settings_kwargs):
    """Prices and load where DP holds charge; only standby drains the pack."""
    settings = _battery_settings(
        standby_loss_kw=0.2,
        min_action_profit_threshold=0.0,
        cycle_cost_per_kwh=10.0,
        min_soc=10,
        **settings_kwargs,
    )
    horizon = 16
    return settings, dict(
        buy_price=[2.0] * horizon,
        sell_price=[0.01] * horizon,
        home_consumption=[0.125] * horizon,
        solar_production=[0.0] * horizon,
        initial_soe=9.7,
        battery_settings=settings,
        period_duration_hours=0.25,
        initial_cost_basis=5.0,
    )


def test_optimize_schedule_chains_soe_under_standby_loss():
    """DP path extraction must chain SOE down each quarter, not reset to grid point."""
    settings, kwargs = _standby_hold_scenario()
    drain_per_quarter = settings.standby_loss_kw * kwargs["period_duration_hours"]

    result = optimize_battery_schedule(**kwargs)

    for idx, period in enumerate(result.period_data):
        expected_start = kwargs["initial_soe"] - idx * drain_per_quarter
        expected_end = expected_start - drain_per_quarter
        assert period.energy.battery_soe_start == pytest.approx(expected_start)
        assert period.energy.battery_soe_end == pytest.approx(expected_end)
        assert period.energy.battery_discharged == pytest.approx(drain_per_quarter)


def test_optimize_schedule_float_boundary_does_not_stall_soe():
    """Chained SOE must keep decreasing when initial SOE sits on a float grid boundary."""
    settings, kwargs = _standby_hold_scenario()
    kwargs["initial_soe"] = 9.700000000000006
    drain_per_quarter = settings.standby_loss_kw * kwargs["period_duration_hours"]

    result = optimize_battery_schedule(**kwargs)

    for idx in range(1, len(result.period_data)):
        prev = result.period_data[idx - 1].energy.battery_soe_start
        curr = result.period_data[idx].energy.battery_soe_start
        assert curr < prev
    assert result.period_data[0].energy.battery_soe_end == pytest.approx(
        kwargs["initial_soe"] - drain_per_quarter
    )


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


def test_standby_only_idle_period_classifies_as_idle():
    """Power=0 with only standby drain must be IDLE, not LOAD_SUPPORT."""
    _, kwargs = _standby_hold_scenario()
    result = optimize_battery_schedule(**kwargs)

    for idx, period in enumerate(result.period_data):
        assert (
            period.decision.strategic_intent == "IDLE"
        ), f"period {idx}: expected IDLE, got {period.decision.strategic_intent}"
        assert period.decision.battery_action == pytest.approx(0.0)


def test_classify_strategic_intent_standby_only_is_idle():
    standby = 0.2
    energy = EnergyData(
        solar_production=0.0,
        home_consumption=0.5,
        battery_charged=0.0,
        battery_discharged=standby,
        grid_imported=0.5,
        grid_exported=0.0,
        battery_soe_start=10.0,
        battery_soe_end=9.8,
    )
    assert classify_strategic_intent(0.0, energy, standby_drain_kwh=standby) == "IDLE"


def test_standby_idle_maps_to_zero_discharge_rate():
    """IDLE intent must program discharge_rate=0 so grid can cover home load."""
    settings, kwargs = _standby_hold_scenario()
    result = optimize_battery_schedule(**kwargs)
    controller = GrowattMinController(settings)

    for idx, period in enumerate(result.period_data):
        _, discharge_rate = controller._map_intent_to_rates(
            period.decision.strategic_intent, 0.0
        )
        assert discharge_rate == 0, (
            f"period {idx}: {period.decision.strategic_intent} "
            f"got discharge_rate={discharge_rate}"
        )

"""SOLAR_EXPORT strategic intent: optimizer exports solar rather than storing it.

When the cost of keeping energy in the battery (standby drain, cycle cost) exceeds
the value of discharging it later, the optimizer should prefer exporting solar
immediately at sell price over storing it for a later period.
"""

import pytest

from core.bess.dp_battery_algorithm import optimize_battery_schedule
from core.bess.growatt_min_controller import GrowattMinController
from core.bess.settings import BatterySettings


def _settings(**kwargs) -> BatterySettings:
    defaults = {
        "total_capacity": 10.0,
        "min_soc": 10,
        "max_soc": 100,
        "max_charge_power_kw": 5.0,
        "max_discharge_power_kw": 5.0,
        "efficiency_charge": 1.0,
        "efficiency_discharge": 1.0,
        "cycle_cost_per_kwh": 0.0,
        "standby_loss_kw": 0.3,
        "min_action_profit_threshold": 0.0,
    }
    defaults.update(kwargs)
    return BatterySettings(**defaults)


def _intents(result) -> list[str]:
    return [p.decision.strategic_intent for p in result.period_data]


class TestSolarExportChosen:
    def test_solar_export_chosen_when_buy_equals_sell(self):
        """When buy price equals sell price, exporting solar earns more than storing
        and later being blocked from discharge due to break-even cost basis."""
        settings = _settings(standby_loss_kw=0.3)

        result = optimize_battery_schedule(
            buy_price=[1.0, 1.0],
            sell_price=[1.0, 1.0],
            home_consumption=[0.0, 0.5],
            solar_production=[2.0, 0.0],
            initial_soe=settings.min_soe_kwh,  # start at floor
            battery_settings=settings,
            period_duration_hours=1.0,
        )

        assert "SOLAR_EXPORT" in _intents(result)

    def test_solar_export_period_exports_solar_not_stores_it(self):
        """In a SOLAR_EXPORT period, all solar goes to grid export, not battery."""
        settings = _settings(standby_loss_kw=0.3)

        result = optimize_battery_schedule(
            buy_price=[1.0, 1.0],
            sell_price=[1.0, 1.0],
            home_consumption=[0.0, 0.5],
            solar_production=[2.0, 0.0],
            initial_soe=settings.min_soe_kwh,
            battery_settings=settings,
            period_duration_hours=1.0,
        )

        export_period = next(
            p
            for p in result.period_data
            if p.decision.strategic_intent == "SOLAR_EXPORT"
        )
        assert export_period.energy.battery_charged == pytest.approx(0.0)
        assert export_period.energy.grid_exported == pytest.approx(2.0)

    def test_solar_export_soe_unchanged_when_at_floor(self):
        """When battery is already at the floor, SOLAR_EXPORT leaves SOE unchanged."""
        settings = _settings(standby_loss_kw=0.3)
        floor = settings.min_soe_kwh

        result = optimize_battery_schedule(
            buy_price=[1.0, 1.0],
            sell_price=[1.0, 1.0],
            home_consumption=[0.0, 0.5],
            solar_production=[2.0, 0.0],
            initial_soe=floor,
            battery_settings=settings,
            period_duration_hours=1.0,
        )

        export_period = next(
            p
            for p in result.period_data
            if p.decision.strategic_intent == "SOLAR_EXPORT"
        )
        assert export_period.energy.battery_soe_start == pytest.approx(floor)
        assert export_period.energy.battery_soe_end == pytest.approx(floor)


class TestSolarExportNotChosen:
    def test_idle_preferred_when_discharge_clearly_profitable(self):
        """When buy price >> sell price, storing solar and discharging later is better."""
        settings = _settings(standby_loss_kw=0.0, cycle_cost_per_kwh=0.0)

        result = optimize_battery_schedule(
            buy_price=[2.0, 2.0],
            sell_price=[0.2, 0.2],
            home_consumption=[0.0, 2.0],
            solar_production=[2.0, 0.0],
            initial_soe=settings.min_soe_kwh,
            battery_settings=settings,
            period_duration_hours=1.0,
        )

        assert "SOLAR_EXPORT" not in _intents(result)

    def test_solar_export_not_selected_when_no_solar(self):
        """SOLAR_EXPORT should not appear in periods with no solar production."""
        settings = _settings(standby_loss_kw=0.3)

        result = optimize_battery_schedule(
            buy_price=[1.0, 1.0],
            sell_price=[1.0, 1.0],
            home_consumption=[1.0, 1.0],
            solar_production=[0.0, 0.0],
            initial_soe=settings.min_soe_kwh,
            battery_settings=settings,
            period_duration_hours=1.0,
        )

        assert "SOLAR_EXPORT" not in _intents(result)


class TestSolarExportInverterMapping:
    """SOLAR_EXPORT intent must map to grid_first mode in the inverter controller."""

    def test_solar_export_hours_use_grid_first_mode(self):
        """Periods with SOLAR_EXPORT intent must produce grid_first mode."""
        settings = _settings(standby_loss_kw=0.3)
        controller = GrowattMinController(settings)

        intents = ["SOLAR_EXPORT"] * 24 + ["IDLE"] * 72
        controller.current_hour = 0
        controller.strategic_intents = intents
        controller._consolidate_and_convert_with_strategic_intents()

        for hour in range(6):
            assert controller.get_hour_battery_mode(hour) == "grid_first"

    def test_idle_hours_still_use_load_first_alongside_solar_export(self):
        """IDLE periods adjacent to SOLAR_EXPORT must remain load_first."""
        settings = _settings(standby_loss_kw=0.3)
        controller = GrowattMinController(settings)

        intents = ["SOLAR_EXPORT"] * 24 + ["IDLE"] * 72
        controller.current_hour = 0
        controller.strategic_intents = intents
        controller._consolidate_and_convert_with_strategic_intents()

        for hour in range(6, 24):
            assert controller.get_hour_battery_mode(hour) == "load_first"

    def test_solar_export_does_not_enable_grid_charging(self):
        """SOLAR_EXPORT should not enable grid charging."""
        assert (
            GrowattMinController.INTENT_TO_CONTROL["SOLAR_EXPORT"]["grid_charge"]
            is False
        )

    def test_solar_export_sets_zero_charge_rate(self):
        """SOLAR_EXPORT should not allow battery charging from any source."""
        assert (
            GrowattMinController.INTENT_TO_CONTROL["SOLAR_EXPORT"]["charge_rate"] == 0
        )

"""Tests for InfluxDB 7-day average consumption forecast."""

from datetime import date
from unittest.mock import patch

from core.bess.battery_system_manager import BatterySystemManager
from core.bess.runtime_failure_tracker import RuntimeFailureTracker
from core.bess.settings import BatterySettings, HomeSettings
from core.bess.tests.conftest import MockHomeAssistantController


def _make_influxdb_profile(kw_value: float) -> dict:
    """Build a mock influxdb period_data dict with a constant kW value for all 96 periods."""
    sensor_key = "sensor.local_load_power"
    return {period: {sensor_key: kw_value} for period in range(96)}


def _create_manager_with_influxdb(
    kw_value: float,
    standby_loss_kw: float = 0.0,
    default_hourly: float = 1.0,
) -> BatterySystemManager:
    controller = MockHomeAssistantController()
    controller.sensors = {"local_load_power": "local_load_power"}

    battery_settings = BatterySettings()
    battery_settings.standby_loss_kw = standby_loss_kw

    home_settings = HomeSettings()
    home_settings.consumption_strategy = "influxdb_7d_avg"
    home_settings.default_hourly = default_hourly

    manager = BatterySystemManager.__new__(BatterySystemManager)
    manager._controller = controller
    manager.home_settings = home_settings
    manager.battery_settings = battery_settings
    manager._runtime_failure_tracker = RuntimeFailureTracker()

    return manager, kw_value


def _run_forecast(manager: BatterySystemManager, kw_value: float) -> list[float]:
    period_data = _make_influxdb_profile(kw_value)

    def mock_batch(sensors, target_date):
        return {"status": "success", "data": period_data}

    with patch(
        "core.bess.battery_system_manager.get_power_sensor_data_batch", mock_batch
    ), patch("core.bess.battery_system_manager.time_utils") as mock_tu:
        mock_tu.today.return_value = date(2026, 5, 12)
        return manager._get_influxdb_7d_avg_forecast()


class TestInfluxdbStandbyCorrection:
    """influxdb_7d_avg forecast must apply the same standby-loss correction
    as the ha_statistics path, so both strategies produce true home load."""

    def test_standby_loss_subtracted_from_influxdb_forecast(self):
        """With standby_loss_kw=0.3, each period value is reduced by 0.075 kWh.

        The influxdb profile stores kWh per quarter-hour period. At 0.5 kWh/qh,
        after subtracting standby drain (0.3 kW × 0.25 h = 0.075 kWh):
        0.5 - 0.075 = 0.425 kWh/qh.
        """
        manager, kwh_value = _create_manager_with_influxdb(
            kw_value=0.5, standby_loss_kw=0.3, default_hourly=1.0
        )
        result = _run_forecast(manager, kwh_value)

        assert len(result) == 96
        assert all(abs(v - 0.425) < 0.001 for v in result)

    def test_no_correction_when_standby_loss_is_zero(self):
        """With standby_loss_kw=0, influxdb forecast is unmodified."""
        manager, kwh_value = _create_manager_with_influxdb(
            kw_value=0.5, standby_loss_kw=0.0, default_hourly=1.0
        )
        result = _run_forecast(manager, kwh_value)

        assert all(abs(v - 0.5) < 0.001 for v in result)

    def test_correction_floored_at_default_hourly(self):
        """Correction is skipped for samples already at or near the configured baseline."""
        # 0.3 kWh/qh - 0.075 = 0.225 < floor (0.25) → no subtraction, stays 0.3.
        manager, kwh_value = _create_manager_with_influxdb(
            kw_value=0.3, standby_loss_kw=0.3, default_hourly=1.0
        )
        result = _run_forecast(manager, kwh_value)

        assert all(abs(v - 0.3) < 0.001 for v in result)

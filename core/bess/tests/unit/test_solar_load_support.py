"""Tests for the solar load-support override.

When live PV production >= solar_pv_min_watts AND total home load exceeds
solar_discharge_load_multiplier x defaultHourly watts, apply_discharge_inhibit
forces discharge to 100% regardless of the scheduled rate.

Discharge inhibit always takes priority: the override cannot fire when inhibit
is active.
"""

from types import SimpleNamespace

import pytest

from core.bess.battery_system_manager import BatterySystemManager
from core.bess.price_manager import MockSource
from core.bess.tests.conftest import MockHomeAssistantController

pytestmark = pytest.mark.slow

PERIOD = 20  # Arbitrary test period

# With default_hourly=1.0 kWh/h (=1000 W) and multiplier=2.0:
# load threshold = 2000 W
# Default mock phase currents: l1=10, l2=8, l3=12 (total 30 A x 230 V = 6900 W > 2000 W)
DEFAULT_HOURLY = 1.0  # kWh/h — simple baseline that makes thresholds easy to reason about


class SolarController(MockHomeAssistantController):
    """Mock controller with controllable PV power and inhibit flag."""

    def __init__(self, pv_watts: float = 200.0, inhibit_active: bool = False) -> None:
        super().__init__()
        self.pv_watts = pv_watts
        self.inhibit_active = inhibit_active

    def get_pv_power(self) -> float:
        return self.pv_watts

    def get_discharge_inhibit_active(self) -> bool:
        return self.inhibit_active


def _make_bsm(
    pv_watts: float = 200.0,
    inhibit_active: bool = False,
) -> tuple[BatterySystemManager, SolarController]:
    controller = SolarController(pv_watts=pv_watts, inhibit_active=inhibit_active)
    bsm = BatterySystemManager(
        controller=controller,
        price_source=MockSource([1.0] * 96),
        addon_options={"inverter": {"platform": "growatt_server_min"}},
    )
    bsm.home_settings.default_hourly = DEFAULT_HOURLY
    return bsm, controller


def _set_intent(bsm: BatterySystemManager, period: int, intent: str) -> None:
    intents = ["IDLE"] * 96
    intents[period] = intent
    bsm._inverter_controller.strategic_intents = intents


def _set_discharge_action(bsm: BatterySystemManager, period: int, kwh: float) -> None:
    actions = [0.0] * 96
    actions[period] = kwh
    bsm._inverter_controller.current_schedule = SimpleNamespace(actions=actions)


# ── Tracer bullet ─────────────────────────────────────────────────────────────


class TestSolarLoadSupportOverrideFires:
    def test_forces_discharge_to_100_when_pv_and_load_spike(self):
        """Override must engage when PV >= 100 W and load > 2x base (no inhibit)."""
        # pv=200 W (≥ 100 W threshold), load=6900 W (> 2000 W threshold)
        bsm, controller = _make_bsm(pv_watts=200.0, inhibit_active=False)

        bsm.apply_discharge_inhibit()

        assert controller.calls["discharge_rate"][-1] == 100


# ── Inhibit wins ──────────────────────────────────────────────────────────────


class TestInhibitWinsOverSolarOverride:
    def test_does_not_override_when_inhibit_active(self):
        """Discharge inhibit must take priority — solar override cannot fire when inhibit is on."""
        # Start with inhibit inactive so LOAD_SUPPORT applies discharge at 100%
        bsm, controller = _make_bsm(pv_watts=200.0, inhibit_active=False)
        _set_intent(bsm, PERIOD, "LOAD_SUPPORT")
        bsm._apply_period_schedule(PERIOD)  # desired=100, applied=100
        assert controller.calls["discharge_rate"][-1] == 100

        # Inhibit becomes active — must suppress both schedule rate and solar override
        controller.inhibit_active = True
        bsm.apply_discharge_inhibit()

        assert controller.calls["discharge_rate"][-1] == 0


# ── PV threshold ──────────────────────────────────────────────────────────────


class TestSolarPvThreshold:
    def test_does_not_override_when_pv_below_threshold(self):
        """Override must not fire when PV production is below solar_pv_min_watts (100 W)."""
        bsm, controller = _make_bsm(pv_watts=50.0)  # 50 W < 100 W
        writes_before = len(controller.calls["discharge_rate"])

        bsm.apply_discharge_inhibit()

        assert len(controller.calls["discharge_rate"]) == writes_before

    def test_override_fires_exactly_at_pv_threshold(self):
        """Override must fire when PV equals the configured minimum (boundary value)."""
        bsm, controller = _make_bsm(pv_watts=100.0)  # exactly at threshold

        bsm.apply_discharge_inhibit()

        assert controller.calls["discharge_rate"][-1] == 100


# ── Load threshold ────────────────────────────────────────────────────────────


class TestLoadSpikeThreshold:
    def test_does_not_override_when_load_below_threshold(self):
        """Override must not fire when total load is below multiplier x defaultHourly."""
        bsm, controller = _make_bsm(pv_watts=200.0)
        # Set phase currents to give ~690 W < 2000 W threshold
        controller.settings["l1_current"] = 1.0
        controller.settings["l2_current"] = 1.0
        controller.settings["l3_current"] = 1.0
        writes_before = len(controller.calls["discharge_rate"])

        bsm.apply_discharge_inhibit()

        assert len(controller.calls["discharge_rate"]) == writes_before

    def test_override_fires_exactly_above_threshold(self):
        """Override must fire when load just exceeds the multiplier threshold."""
        bsm, controller = _make_bsm(pv_watts=200.0)
        # threshold = 2.0 x 1.0 kWh/h x 1000 = 2000 W
        # Set load to 2001 W: 2001 / (3 phases x 230 V) ≈ 2.9 A per phase
        controller.settings["l1_current"] = 2.91
        controller.settings["l2_current"] = 2.91
        controller.settings["l3_current"] = 2.91  # 3 x 2.91 x 230 ≈ 2007 W

        bsm.apply_discharge_inhibit()

        assert controller.calls["discharge_rate"][-1] == 100


# ── State restoration + no duplicate writes ───────────────────────────────────


class TestOverrideRelease:
    def test_restores_desired_rate_when_conditions_clear(self):
        """Discharge must return to the scheduled rate once solar/load conditions clear."""
        bsm, controller = _make_bsm(pv_watts=200.0)
        _set_intent(bsm, PERIOD, "IDLE")
        bsm._apply_period_schedule(PERIOD)  # desired=0, applied=0

        bsm.apply_discharge_inhibit()  # Override fires → write 100
        assert controller.calls["discharge_rate"][-1] == 100

        controller.pv_watts = 50.0  # Solar drops below threshold
        bsm.apply_discharge_inhibit()  # Override clears → restore desired=0

        assert controller.calls["discharge_rate"][-1] == 0

    def test_no_repeated_writes_while_conditions_unchanged(self):
        """Must not write to the inverter on every tick — only when state changes."""
        bsm, controller = _make_bsm(pv_watts=200.0)

        bsm.apply_discharge_inhibit()  # Override fires → first write
        writes_after_first = len(controller.calls["discharge_rate"])

        bsm.apply_discharge_inhibit()  # Conditions unchanged — no new write
        bsm.apply_discharge_inhibit()

        assert len(controller.calls["discharge_rate"]) == writes_after_first


# ── Local load power preferred over phase currents ────────────────────────────


class TestLocalLoadPowerPreference:
    def test_uses_local_load_power_when_available(self):
        """local_load_power (actual consumption) must be preferred over phase currents."""

        class LocalLoadController(SolarController):
            def get_local_load_power(self) -> float:
                return 5000.0  # 5 kW — above 2000 W threshold

        controller = LocalLoadController(pv_watts=200.0)
        # Set phase currents low so they would NOT trigger the override alone
        controller.settings["l1_current"] = 0.1
        controller.settings["l2_current"] = 0.1
        controller.settings["l3_current"] = 0.1  # 0.3 A x 230 V = 69 W total
        bsm = BatterySystemManager(
            controller=controller,
            price_source=MockSource([1.0] * 96),
            addon_options={"inverter": {"platform": "growatt_server_min"}},
        )
        bsm.home_settings.default_hourly = DEFAULT_HOURLY

        bsm.apply_discharge_inhibit()

        # local_load_power=5000W > threshold=2000W → must fire despite low phase currents
        assert controller.calls["discharge_rate"][-1] == 100

    def test_falls_back_to_phase_currents_when_local_load_returns_none(self):
        """Phase currents must be used when local_load_power sensor returns None."""

        class NullLocalLoadController(SolarController):
            def get_local_load_power(self):
                return None  # sensor unavailable

        controller = NullLocalLoadController(pv_watts=200.0)
        # Default phase currents give 6900 W > 2000 W threshold
        bsm = BatterySystemManager(
            controller=controller,
            price_source=MockSource([1.0] * 96),
            addon_options={"inverter": {"platform": "growatt_server_min"}},
        )
        bsm.home_settings.default_hourly = DEFAULT_HOURLY

        bsm.apply_discharge_inhibit()

        assert controller.calls["discharge_rate"][-1] == 100


# ── Prediction-based threshold ────────────────────────────────────────────────


class TestPredictionBasedThreshold:
    def test_uses_current_slot_prediction_when_available(self):
        """When predictions are loaded, threshold is multiplier x current-slot kW, not defaultHourly."""
        bsm, controller = _make_bsm(pv_watts=200.0)

        # Inject a flat prediction: 0.1 kWh/15min = 0.4 kW.
        # threshold = 2.0 x 0.4 kW x 1000 = 800 W
        # Default phase loads = 6900 W >> 800 W  → override fires
        bsm._consumption_predictions = [0.1] * 96

        bsm.apply_discharge_inhibit()

        assert controller.calls["discharge_rate"][-1] == 100

    def test_prediction_threshold_suppresses_override_when_load_is_expected(self):
        """If predicted load is high enough that actual load is NOT a spike, override must not fire."""
        bsm, controller = _make_bsm(pv_watts=200.0)

        # Phase loads: l1=10, l2=8, l3=12 → 6900 W
        # Inject prediction: 1.5 kWh/15min = 6.0 kW per hour
        # threshold = 2.0 x 6.0 kW x 1000 = 12000 W
        # 6900 W < 12000 W → no spike → no override
        bsm._consumption_predictions = [1.5] * 96
        writes_before = len(controller.calls["discharge_rate"])

        bsm.apply_discharge_inhibit()

        assert len(controller.calls["discharge_rate"]) == writes_before

    def test_falls_back_to_default_hourly_when_predictions_not_yet_loaded(self):
        """Before the first prediction fetch, threshold must use defaultHourly as fallback."""
        bsm, controller = _make_bsm(pv_watts=200.0)
        # _consumption_predictions is None by default (not yet fetched)
        assert bsm._consumption_predictions is None

        # default_hourly=1.0 kWh/h → threshold = 2.0 x 1.0 x 1000 = 2000 W
        # Phase loads = 6900 W > 2000 W → override fires
        bsm.apply_discharge_inhibit()

        assert controller.calls["discharge_rate"][-1] == 100


# ── Graceful degradation ──────────────────────────────────────────────────────


class TestSolarSensorDegradation:
    def test_no_op_when_pv_sensor_raises_exception(self):
        """Override must be silently inactive when the PV sensor is unavailable."""

        class BrokenPvController(MockHomeAssistantController):
            def get_pv_power(self):
                raise RuntimeError("sensor unavailable")

            def get_discharge_inhibit_active(self) -> bool:
                return False

        controller = BrokenPvController()
        bsm = BatterySystemManager(
            controller=controller,
            price_source=MockSource([1.0] * 96),
            addon_options={"inverter": {"platform": "growatt_server_min"}},
        )
        bsm.home_settings.default_hourly = DEFAULT_HOURLY
        writes_before = len(controller.calls["discharge_rate"])

        bsm.apply_discharge_inhibit()

        assert len(controller.calls["discharge_rate"]) == writes_before

    def test_no_op_when_phase_current_sensors_raise_exception(self):
        """Override must not fire when load cannot be measured (sensors unavailable)."""

        class BrokenPhaseController(SolarController):
            def get_l1_current(self):
                raise RuntimeError("sensor unavailable")

        controller = BrokenPhaseController(pv_watts=500.0)
        bsm = BatterySystemManager(
            controller=controller,
            price_source=MockSource([1.0] * 96),
            addon_options={"inverter": {"platform": "growatt_server_min"}},
        )
        bsm.home_settings.default_hourly = DEFAULT_HOURLY
        writes_before = len(controller.calls["discharge_rate"])

        bsm.apply_discharge_inhibit()

        assert len(controller.calls["discharge_rate"]) == writes_before

    def test_pv_sensor_returning_none_is_treated_as_no_solar(self):
        """None from get_pv_power must not trigger the override."""

        class NullPvController(MockHomeAssistantController):
            def get_pv_power(self):
                return None

            def get_discharge_inhibit_active(self) -> bool:
                return False

        controller = NullPvController()
        bsm = BatterySystemManager(
            controller=controller,
            price_source=MockSource([1.0] * 96),
            addon_options={"inverter": {"platform": "growatt_server_min"}},
        )
        bsm.home_settings.default_hourly = DEFAULT_HOURLY
        writes_before = len(controller.calls["discharge_rate"])

        bsm.apply_discharge_inhibit()

        assert len(controller.calls["discharge_rate"]) == writes_before

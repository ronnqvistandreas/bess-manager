import React from 'react';
import { numField, radioGroup, toggle, SectionCard } from './FormHelpers';
import type { PlannedLoadEvent } from '../../types';

export interface HomeForm {
  consumption: number;
  consumptionStrategy: string;
  maxFuseCurrent: number;
  voltage: number;
  safetyMarginFactor: number;
  phaseCount: number;
  powerMonitoringEnabled: boolean;
  solarPvMinWatts: number;
  solarDischargeLoadMultiplier: number;
  plannedLoadEvents: PlannedLoadEvent[];
}

interface Props {
  form: HomeForm;
  onChange: (f: HomeForm) => void;
  sensors?: Record<string, string>;
}

export function HomeFormSection({ form, onChange, sensors }: Props) {
  const haStatsSensorConfigured = Boolean(sensors?.['lifetime_load_consumption']);
  const localLoadSensorConfigured = Boolean(sensors?.['local_load_power']);
  const chargeRateSensorConfigured = Boolean(sensors?.['battery_charging_power_rate']);
  return (
    <div className="space-y-3">
      <SectionCard
        title="Home Consumption Prediction"
        description="The data source the optimizer uses for home load prediction."
      >
        {radioGroup(
          'Data source',
          [
            { value: 'fixed', label: 'Fixed value' },
            { value: 'sensor', label: 'Home Assistant sensor' },
            { value: 'influxdb_7d_avg', label: 'InfluxDB (requires InfluxDB integration)', disabled: !localLoadSensorConfigured },
            { value: 'ha_statistics', label: 'HA Statistics (7-day hourly profile)', disabled: !haStatsSensorConfigured },
          ],
          form.consumptionStrategy,
          v => onChange({ ...form, consumptionStrategy: v }),
        )}
        {!localLoadSensorConfigured && (
          <p className="text-xs text-amber-600 dark:text-amber-400 pt-1">
            InfluxDB requires the <strong>Local Load Power</strong> sensor to be configured in the{' '}
            <strong>Sensors</strong> tab. This sensor is not available on all inverter platforms (e.g. Growatt SPH).
          </p>
        )}
        {!haStatsSensorConfigured && (
          <p className="text-xs text-amber-600 dark:text-amber-400 pt-1">
            HA Statistics requires the <strong>Lifetime Load Consumption</strong> sensor to be
            configured in the <strong>Sensors</strong> tab.
          </p>
        )}
        {form.consumptionStrategy === 'fixed' && (
          <div className="pt-1">
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">Always uses the value below — no sensor required.</p>
            {numField('Default Hourly Consumption', form.consumption,
              v => onChange({ ...form, consumption: v }), { unit: 'kWh', min: 0, step: 0.1 })}
          </div>
        )}
        {form.consumptionStrategy === 'sensor' && (
          <p className="text-xs text-gray-500 dark:text-gray-400 pt-1">
            Reads any HA sensor that provides an hourly consumption estimate — for example a custom helper
            that computes a 48h rolling average of grid import.
            Configure the sensor entity ID in the <strong>Sensors</strong> tab under Consumption Forecast.
          </p>
        )}
        {form.consumptionStrategy === 'influxdb_7d_avg' && (
          <p className="text-xs text-gray-500 dark:text-gray-400 pt-1">
            Queries InfluxDB directly for the past 7 days of local load power and uses the hourly average
            profile. Requires the InfluxDB integration to be configured.
            Configure the local load power sensor entity ID in the <strong>Sensors</strong> tab under Growatt Server.
          </p>
        )}
        {form.consumptionStrategy === 'ha_statistics' && (
          <p className="text-xs text-gray-500 dark:text-gray-400 pt-1">
            Uses Home Assistant's built-in long-term statistics to build a time-of-day consumption profile
            from the past 7 days. Captures daily patterns (morning/evening peaks, overnight baseline) using
            a trimmed average that filters out outlier spikes like EV charging. No extra integrations needed.
            Configure the load consumption sensor in the <strong>Sensors</strong> tab under Consumption Forecast.
          </p>
        )}
      </SectionCard>

      <SectionCard
        title="Power Monitoring"
        description="Monitors real-time load and limits battery charge power to prevent blowing the main fuse. Enable to configure."
      >
        {!chargeRateSensorConfigured && (
          <p className="text-xs text-amber-600 dark:text-amber-400">
            Fuse protection requires a <strong>Battery Charging Power Rate</strong> entity, which is not
            available on all inverter platforms (e.g. Growatt SPH).
          </p>
        )}
        {toggle('Enable fuse protection', form.powerMonitoringEnabled,
          v => onChange({ ...form, powerMonitoringEnabled: v }),
          { disabled: !chargeRateSensorConfigured })}
        {form.powerMonitoringEnabled && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-1">
              {numField('Fuse Current', form.maxFuseCurrent,
                v => onChange({ ...form, maxFuseCurrent: Math.round(v) }), { unit: 'A', min: 1, step: 1 })}
              {numField('Voltage', form.voltage,
                v => onChange({ ...form, voltage: Math.round(v) }), { unit: 'V', min: 100, step: 1 })}
              {numField('Safety Margin Factor', form.safetyMarginFactor,
                v => onChange({ ...form, safetyMarginFactor: v }), { min: 0, max: 2, step: 0.05 })}
            </div>
            <div className="pt-1">
              {radioGroup(
                'Phase count',
                [{ value: '1', label: '1-phase' }, { value: '3', label: '3-phase' }],
                String(form.phaseCount),
                v => onChange({ ...form, phaseCount: parseInt(v, 10) }),
              )}
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 pt-1">
              Configure per-phase current sensor entity IDs in the <strong>Sensors</strong> tab
              under Phase Current Monitoring.
            </p>
          </>
        )}
      </SectionCard>

      <SectionCard
        title="Solar Load-Support Override"
        description="Forces battery discharge to 100% when live solar production and a load spike are both detected, regardless of the optimizer's schedule."
      >
        <p className="text-xs text-gray-500 dark:text-gray-400 pb-2">
          When PV production is at or above the minimum and total home load exceeds the multiplier
          times the default hourly consumption, the battery will discharge to cover the load.
          Discharge inhibit always takes priority over this override.
          Requires the PV Power sensor to be configured in the <strong>Sensors</strong> tab.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {numField('Solar PV Minimum', form.solarPvMinWatts,
            v => onChange({ ...form, solarPvMinWatts: v }),
            { unit: 'W', min: 0, step: 10 })}
          {numField('Load Multiplier', form.solarDischargeLoadMultiplier,
            v => onChange({ ...form, solarDischargeLoadMultiplier: v }),
            { min: 1, step: 0.1 })}
        </div>
      </SectionCard>

      <SectionCard
        title="Planned High-Load Events"
        description="Tell the optimizer when you expect a high load (e.g. EV charging). It will pre-charge the battery in preparation using solar when available."
      >
        <p className="text-xs text-gray-500 dark:text-gray-400 pb-2">
          Each event adds the specified load to the consumption forecast for the time window, so
          the optimizer naturally pre-charges before the window. Set a Solar Minimum to suppress
          pre-charging on cloudy days — the grid will then serve the load directly.
        </p>
        <div className="space-y-3">
          {form.plannedLoadEvents.map((evt, idx) => (
            <PlannedEventRow
              key={idx}
              event={evt}
              onChange={updated => {
                const next = [...form.plannedLoadEvents];
                next[idx] = updated;
                onChange({ ...form, plannedLoadEvents: next });
              }}
              onRemove={() => {
                const next = form.plannedLoadEvents.filter((_, i) => i !== idx);
                onChange({ ...form, plannedLoadEvents: next });
              }}
            />
          ))}
          <button
            type="button"
            onClick={() => onChange({
              ...form,
              plannedLoadEvents: [
                ...form.plannedLoadEvents,
                { label: 'EV charging', startPeriod: 52, endPeriod: 67, extraKw: 7.0, active: true, solarMinKwh: 0 },
              ],
            })}
            className="flex items-center gap-1.5 text-sm text-blue-600 dark:text-blue-400 hover:underline"
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            Add event
          </button>
        </div>
      </SectionCard>
    </div>
  );
}

function periodToTime(period: number): string {
  const h = Math.floor(period / 4).toString().padStart(2, '0');
  const m = ((period % 4) * 15).toString().padStart(2, '0');
  return `${h}:${m}`;
}

function timeToPeriod(time: string): number {
  const [h, m] = time.split(':').map(Number);
  return (h ?? 0) * 4 + Math.floor((m ?? 0) / 15);
}

interface RowProps {
  event: PlannedLoadEvent;
  onChange: (e: PlannedLoadEvent) => void;
  onRemove: () => void;
}

function PlannedEventRow({ event, onChange, onRemove }: RowProps) {
  return (
    <div className={`rounded-lg border p-3 space-y-3 ${event.active ? 'border-blue-200 dark:border-blue-800 bg-blue-50/30 dark:bg-blue-900/10' : 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/40 opacity-60'}`}>
      <div className="flex items-center gap-3">
        <input
          type="text"
          value={event.label}
          onChange={e => onChange({ ...event, label: e.target.value })}
          placeholder="Label"
          className="flex-1 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-1.5 text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          type="button"
          role="switch"
          aria-checked={event.active}
          onClick={() => onChange({ ...event, active: !event.active })}
          className={`relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 ${event.active ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-600'}`}
        >
          <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${event.active ? 'translate-x-6' : 'translate-x-1'}`} />
        </button>
        <button
          type="button"
          onClick={onRemove}
          className="text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-colors"
          aria-label="Remove event"
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>
        </button>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <label className="block">
          <span className="text-xs font-medium text-gray-600 dark:text-gray-400">Start</span>
          <input
            type="time"
            step="900"
            value={periodToTime(event.startPeriod)}
            onChange={e => onChange({ ...event, startPeriod: timeToPeriod(e.target.value) })}
            className="mt-1 block w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-1.5 text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-gray-600 dark:text-gray-400">End</span>
          <input
            type="time"
            step="900"
            value={periodToTime(event.endPeriod)}
            onChange={e => onChange({ ...event, endPeriod: timeToPeriod(e.target.value) })}
            className="mt-1 block w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-1.5 text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-gray-600 dark:text-gray-400">Extra load (kW)</span>
          <input
            type="number"
            min={0.1}
            step={0.5}
            value={event.extraKw}
            onChange={e => { const n = parseFloat(e.target.value); if (!Number.isNaN(n)) onChange({ ...event, extraKw: n }); }}
            className="mt-1 block w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-1.5 text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-gray-600 dark:text-gray-400">Solar min (kWh)</span>
          <input
            type="number"
            min={0}
            step={0.5}
            value={event.solarMinKwh}
            onChange={e => { const n = parseFloat(e.target.value); if (!Number.isNaN(n)) onChange({ ...event, solarMinKwh: n }); }}
            className="mt-1 block w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-1.5 text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </label>
      </div>
      <p className="text-xs text-gray-400 dark:text-gray-500">
        {periodToTime(event.startPeriod)}–{periodToTime(event.endPeriod)}, +{event.extraKw} kW
        {event.solarMinKwh > 0 ? ` · only when solar forecast ≥ ${event.solarMinKwh} kWh in window` : ' · always active'}
      </p>
    </div>
  );
}

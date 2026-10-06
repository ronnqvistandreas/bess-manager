import React, { useEffect, useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
// @ts-expect-error lucide-react .d.ts is too large for TS to resolve all exports
import { ChevronDown, ChevronUp, History } from 'lucide-react';
import { SavingsHistoryDays, useSavingsHistory } from '../hooks/useSavingsHistory';

const COLORS = {
  solar: '#fbbf24',
  battery: '#10b981',
};

interface ChartPoint {
  date: string;
  solarSavings: number;
  batteryContribution: number;
  totalSavings: number;
}

const HistoryTooltip = ({
  active,
  payload,
  currency,
}: {
  active?: boolean;
  payload?: Array<{ payload: ChartPoint }>;
  currency: string;
}) => {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg p-3 shadow-lg">
      <p className="font-semibold text-gray-900 dark:text-white mb-2">{point.date}</p>
      <div className="space-y-1 text-sm">
        <p className="text-gray-700 dark:text-gray-300">
          Solar: {point.solarSavings.toFixed(2)} {currency}
        </p>
        <p className="text-gray-700 dark:text-gray-300">
          Battery: {point.batteryContribution.toFixed(2)} {currency}
        </p>
        <p className="font-medium text-gray-900 dark:text-white">
          Total: {point.totalSavings.toFixed(2)} {currency}
        </p>
      </div>
    </div>
  );
};

const formatCurrency = (value: number, currency: string): string =>
  `${value.toFixed(2)} ${currency}`;

const DailySavingsHistory: React.FC = () => {
  const [expanded, setExpanded] = useState(false);
  const [days, setDays] = useState<SavingsHistoryDays>(30);
  const { data, loading, error } = useSavingsHistory(days);

  const [isDarkMode, setIsDarkMode] = useState(
    document.documentElement.classList.contains('dark'),
  );

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsDarkMode(document.documentElement.classList.contains('dark'));
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  const colors = {
    text: isDarkMode ? '#9CA3AF' : '#374151',
    gridLines: isDarkMode ? '#374151' : '#e5e7eb',
  };

  const currency = data?.currency ?? '';
  const records = data?.records ?? [];

  const chartData = useMemo<ChartPoint[]>(
    () =>
      [...records]
        .reverse()
        .map((record) => ({
          date: record.date,
          solarSavings: record.solarSavings,
          batteryContribution: record.batteryContribution,
          totalSavings: record.totalSavings,
        })),
    [records],
  );

  const dayOptions: Array<{ label: string; value: SavingsHistoryDays }> = [
    { label: '30 days', value: 30 },
    { label: '90 days', value: 90 },
    { label: 'All', value: 0 },
  ];

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700">
      <button
        type="button"
        onClick={() => setExpanded((current) => !current)}
        className="w-full flex items-center justify-between p-6 text-left"
      >
        <div className="flex items-center gap-3">
          <History className="h-5 w-5 text-gray-500 dark:text-gray-400" />
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Daily Savings History
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Finalized daily savings from actual sensor data
            </p>
          </div>
        </div>
        {expanded ? (
          <ChevronUp className="h-5 w-5 text-gray-400" />
        ) : (
          <ChevronDown className="h-5 w-5 text-gray-400" />
        )}
      </button>

      {expanded && (
        <div className="px-6 pb-6 space-y-6 border-t border-gray-200 dark:border-gray-700 pt-6">
          <div className="flex justify-end">
            <div className="flex bg-gray-100 dark:bg-gray-700 rounded-lg p-1">
              {dayOptions.map((option) => (
                <button
                  key={option.label}
                  type="button"
                  onClick={() => setDays(option.value)}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    days === option.value
                      ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
                      : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          {loading && (
            <div className="flex items-center justify-center h-32">
              <div className="animate-spin h-8 w-8 border-2 border-blue-500 rounded-full border-t-transparent" />
              <span className="ml-2 text-gray-900 dark:text-white">Loading history...</span>
            </div>
          )}

          {error && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md p-4">
              <p className="text-red-600 dark:text-red-300">{error}</p>
            </div>
          )}

          {!loading && !error && records.length === 0 && (
            <p className="text-gray-500 dark:text-gray-400 text-center py-8">
              No finalized daily savings yet. History appears after the first full day rollover.
            </p>
          )}

          {!loading && !error && records.length > 0 && (
            <>
              <div style={{ width: '100%', height: '300px' }}>
                <ResponsiveContainer>
                  <BarChart
                    data={chartData}
                    stackOffset="sign"
                    margin={{ top: 10, right: 10, left: 0, bottom: 30 }}
                  >
                    <CartesianGrid
                      stroke={colors.gridLines}
                      strokeOpacity={isDarkMode ? 0.12 : 0.3}
                      strokeWidth={0.5}
                    />
                    <XAxis
                      dataKey="date"
                      stroke={colors.text}
                      tick={{ fill: colors.text, fontSize: 11 }}
                      angle={-35}
                      textAnchor="end"
                      height={60}
                    />
                    <YAxis
                      width={60}
                      stroke={colors.text}
                      tick={{ fill: colors.text, fontSize: 11 }}
                      label={{
                        value: currency,
                        angle: -90,
                        position: 'insideLeft',
                        style: { textAnchor: 'middle', fill: colors.text },
                        fontSize: 12,
                      }}
                    />
                    <Tooltip content={<HistoryTooltip currency={currency} />} />
                    <Bar
                      dataKey="solarSavings"
                      name="Solar"
                      stackId="savings"
                      fill={COLORS.solar}
                      fillOpacity={0.85}
                      isAnimationActive={false}
                    />
                    <Bar
                      dataKey="batteryContribution"
                      name="Battery"
                      stackId="savings"
                      fill={COLORS.battery}
                      fillOpacity={0.85}
                      isAnimationActive={false}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="flex justify-center gap-6 text-sm">
                <div className="flex items-center">
                  <div
                    className="w-3 h-3 rounded mr-1.5"
                    style={{ backgroundColor: COLORS.solar }}
                  />
                  <span className="text-gray-600 dark:text-gray-400">Solar</span>
                </div>
                <div className="flex items-center">
                  <div
                    className="w-3 h-3 rounded mr-1.5"
                    style={{ backgroundColor: COLORS.battery }}
                  />
                  <span className="text-gray-600 dark:text-gray-400">Battery</span>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                  <thead className="bg-gray-50 dark:bg-gray-900/40">
                    <tr>
                      {[
                        'Date',
                        'Total',
                        'Solar',
                        'Battery',
                        'Predicted',
                        'Δ',
                        'Grid-only',
                        'Optimized',
                        'Periods',
                        'Status',
                      ].map((heading) => (
                        <th
                          key={heading}
                          className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider whitespace-nowrap"
                        >
                          {heading}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {records.map((record) => {
                      const delta = record.totalSavings - record.predictedTotalSavings;
                      return (
                        <tr key={record.date}>
                          <td className="px-3 py-2 text-sm text-gray-900 dark:text-white whitespace-nowrap">
                            {record.date}
                          </td>
                          <td className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300 whitespace-nowrap">
                            {formatCurrency(record.totalSavings, currency)}
                          </td>
                          <td className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300 whitespace-nowrap">
                            {formatCurrency(record.solarSavings, currency)}
                          </td>
                          <td className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300 whitespace-nowrap">
                            {formatCurrency(record.batteryContribution, currency)}
                          </td>
                          <td className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300 whitespace-nowrap">
                            {formatCurrency(record.predictedTotalSavings, currency)}
                          </td>
                          <td className="px-3 py-2 text-sm whitespace-nowrap">
                            <span
                              className={
                                delta >= 0
                                  ? 'text-green-600 dark:text-green-400'
                                  : 'text-red-600 dark:text-red-400'
                              }
                            >
                              {delta >= 0 ? '+' : ''}
                              {formatCurrency(delta, currency)}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300 whitespace-nowrap">
                            {formatCurrency(record.gridOnlyCost, currency)}
                          </td>
                          <td className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300 whitespace-nowrap">
                            {formatCurrency(record.optimizedCost, currency)}
                          </td>
                          <td className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300 whitespace-nowrap">
                            {record.periodCount}
                          </td>
                          <td className="px-3 py-2 text-sm whitespace-nowrap">
                            <span
                              className={
                                record.complete
                                  ? 'text-green-600 dark:text-green-400'
                                  : 'text-amber-600 dark:text-amber-400'
                              }
                            >
                              {record.complete ? 'Complete' : 'Partial'}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default DailySavingsHistory;

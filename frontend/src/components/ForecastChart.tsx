import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  TooltipProps,
} from 'recharts';
import type { HourlyRecord } from '../types';
import { formatMW } from '../utils/format';

export interface ForecastChartProps {
  forecastRecords?: HourlyRecord[];
  actualsRecords?: HourlyRecord[];
  vintage?: string;
  gateClosure?: string;
  isLoading: boolean;
  error: string | null;
  onRetry?: () => void;
}

interface MergedChartPoint {
  time: string;
  forecast: number;
  actual: number | null;
}

/**
 * Custom Tooltip with dark background, tabular numbers, and difference delta.
 */
function CustomForecastTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload || !payload.length) return null;

  const forecastEntry = payload.find((p) => p.dataKey === 'forecast');
  const actualEntry = payload.find((p) => p.dataKey === 'actual');

  const forecastVal = typeof forecastEntry?.value === 'number' ? forecastEntry.value : null;
  const actualVal = typeof actualEntry?.value === 'number' ? actualEntry.value : null;

  const hasDiff = forecastVal !== null && actualVal !== null;
  const diff = hasDiff ? forecastVal - actualVal : null;

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-secondary)',
        border: '1px solid var(--border-card)',
        borderRadius: 'var(--radius-sm)',
        padding: '0.75rem 1rem',
        boxShadow: 'var(--shadow-card)',
        minWidth: '220px',
      }}
    >
      <div
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.8125rem',
          color: 'var(--text-muted)',
          marginBottom: '0.5rem',
          borderBottom: '1px solid var(--border-subtle)',
          paddingBottom: '0.25rem',
        }}
      >
        Time: <strong style={{ color: 'var(--text-primary)' }}>{label} UTC</strong>
      </div>

      <div
        className="tabular-nums"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: '0.875rem',
          marginBottom: '0.25rem',
        }}
      >
        <span style={{ color: 'var(--color-forecast)' }}>● Day-Ahead Forecast:</span>
        <strong>{formatMW(forecastVal)}</strong>
      </div>

      <div
        className="tabular-nums"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: '0.875rem',
          marginBottom: '0.4rem',
        }}
      >
        <span style={{ color: 'var(--color-actual)' }}>● Settled Actual:</span>
        <strong>{formatMW(actualVal)}</strong>
      </div>

      {hasDiff && diff !== null && (
        <div
          className="tabular-nums"
          style={{
            borderTop: '1px dashed var(--border-card)',
            paddingTop: '0.35rem',
            marginTop: '0.35rem',
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: '0.8125rem',
            fontWeight: 600,
            color: diff > 0 ? 'var(--color-danger)' : 'var(--color-success)',
          }}
        >
          <span>{diff > 0 ? 'Overestimate:' : 'Underestimate:'}</span>
          <span>
            {diff > 0 ? '+' : ''}
            {formatMW(diff)}
          </span>
        </div>
      )}
    </div>
  );
}

/**
 * ForecastChart — Recharts dual-line visualization with vintage audit badge,
 * shimmer loading skeleton, and error card.
 */
export function ForecastChart({
  forecastRecords = [],
  actualsRecords = [],
  vintage,
  gateClosure,
  isLoading,
  error,
  onRetry,
}: ForecastChartProps) {
  // Format Y-axis ticks with thousands commas but without the " MW" suffix
  const yTickFormatter = (val: number | string): string => {
    return Number(val).toLocaleString('en-GB');
  };

  // Align forecast and actuals on startTime
  const actualMap = new Map<string, number>(
    (actualsRecords || []).map((r) => [r.startTime, r.generation])
  );

  const chartData: MergedChartPoint[] = (forecastRecords || []).map((f) => {
    // Plain string slicing for HH:mm (e.g., '2026-01-15T14:00:00Z' -> '14:00')
    const timeLabel = f.startTime ? f.startTime.slice(11, 16) : '';
    const actualVal = actualMap.has(f.startTime) ? actualMap.get(f.startTime)! : null;
    return {
      time: timeLabel,
      forecast: f.generation,
      actual: actualVal,
    };
  });

  return (
    <div>
      {/* Vintage & Gate Closure Audit Badge */}
      <div className="audit-badge-bar">
        <div className="audit-badge-left">
          <span className="audit-pulse-dot" />
          <span className="audit-badge-content">
            Vintage: <span className="audit-badge-highlight">{vintage || 'Pending...'}</span>
            {'  |  '}
            Gate closure: <span className="audit-badge-highlight">{gateClosure || 'Pending...'}</span>
          </span>
        </div>
        <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
          Resolution: 1 hour
        </div>
      </div>

      {/* Main Chart Card */}
      <div className="chart-container" style={{ minHeight: '420px', height: '420px' }}>
        <div className="chart-header">
          <h2 className="chart-title">Day-Ahead Wind Forecast vs Actual Generation</h2>
          <div className="chart-legend-custom">
            <div className="legend-item">
              <span className="legend-line" style={{ backgroundColor: 'var(--color-forecast)' }} />
              <span>Forecast</span>
            </div>
            <div className="legend-item">
              <span className="legend-line" style={{ backgroundColor: 'var(--color-actual)' }} />
              <span>Actual (FUELHH)</span>
            </div>
          </div>
        </div>

        {/* State 1: Loading Skeleton */}
        {isLoading && (
          <div className="chart-overlay">
            <div className="shimmer-bar" />
            <div className="overlay-message">Aligning hourly forecast & actuals...</div>
            {/* Static axis label placeholders to maintain layout stability */}
            <div
              style={{
                position: 'absolute',
                left: '1.5rem',
                bottom: '1.5rem',
                color: 'var(--text-muted)',
                fontSize: '0.75rem',
                fontFamily: 'var(--font-mono)',
              }}
            >
              MW ↑
            </div>
            <div
              style={{
                position: 'absolute',
                right: '1.5rem',
                bottom: '1.5rem',
                color: 'var(--text-muted)',
                fontSize: '0.75rem',
                fontFamily: 'var(--font-mono)',
              }}
            >
              Time (UTC) →
            </div>
          </div>
        )}

        {/* State 2: Error Card with Retry Button */}
        {!isLoading && error && (
          <div className="chart-overlay">
            <div className="error-card">
              <div className="error-title">Unable to Load Settlement Data</div>
              <div className="error-detail">{error}</div>
              {onRetry && (
                <button type="button" className="btn-retry" onClick={onRetry}>
                  Retry Request
                </button>
              )}
            </div>
          </div>
        )}

        {/* State 3: Normal LineChart Render */}
        {!isLoading && !error && (
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
              <XAxis
                dataKey="time"
                stroke="var(--text-muted)"
                tick={{ fill: 'var(--text-secondary)', fontSize: 12, fontFamily: 'var(--font-mono)' }}
                tickLine={false}
              />
              <YAxis
                stroke="var(--text-muted)"
                tickFormatter={yTickFormatter}
                tick={{ fill: 'var(--text-secondary)', fontSize: 12, fontFamily: 'var(--font-mono)' }}
                tickLine={false}
                axisLine={false}
                label={{
                  value: 'MW',
                  angle: -90,
                  position: 'insideLeft',
                  fill: 'var(--text-secondary)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 12,
                }}
              />
              <Tooltip content={<CustomForecastTooltip />} />
              <Line
                type="monotone"
                dataKey="forecast"
                name="Forecast"
                stroke="var(--color-forecast)"
                strokeWidth={2.5}
                dot={false}
                activeDot={{ r: 6, fill: 'var(--color-forecast)', stroke: 'var(--bg-primary)', strokeWidth: 2 }}
              />
              <Line
                type="monotone"
                dataKey="actual"
                name="Actual"
                stroke="var(--color-actual)"
                strokeWidth={2.5}
                dot={false}
                activeDot={{ r: 6, fill: 'var(--color-actual)', stroke: 'var(--bg-primary)', strokeWidth: 2 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

export default ForecastChart;

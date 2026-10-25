import { useMemo } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  TooltipProps,
} from 'recharts';
import type { DailyAccuracy } from '../types';
import { formatMW, formatPct } from '../utils/format';

export interface AccuracyChartsProps {
  daily: DailyAccuracy[];
  insight: string;
  isLoading: boolean;
  error: string | null;
}

interface ProcessedDayPoint {
  day: number;
  date: string;
  value: number;
  meanBias?: number;
}

/**
 * Three-tier bar colouring computed dynamically from the actual data range:
 * - Bottom third of range: var(--tier-good) — blue (#38BDF8)
 * - Middle third of range: var(--tier-mod)  — amber (#F59E0B)
 * - Top third of range:    var(--tier-bad)  — red (#EF4444)
 *
 * @param value - The metric value for this day
 * @param min - Minimum metric value observed across all 31 days
 * @param max - Maximum metric value observed across all 31 days
 * @returns CSS variable reference for the fill color
 */
export function getTierColor(value: number, min: number, max: number): string {
  if (typeof value !== 'number' || Number.isNaN(value) || max <= min) {
    return 'var(--tier-good)';
  }
  const range = max - min;
  const t1 = min + range / 3;
  const t2 = min + (2 * range) / 3;

  if (value <= t1) return 'var(--tier-good)';
  if (value <= t2) return 'var(--tier-mod)';
  return 'var(--tier-bad)';
}

interface CustomTooltipExtraProps {
  unit: string;
  isPct: boolean;
}

/**
 * Custom Tooltip for Daily Accuracy Bar Charts
 */
function DailyMetricTooltip({
  active,
  payload,
  isPct,
}: TooltipProps<number, string> & CustomTooltipExtraProps) {
  if (!active || !payload || !payload.length) return null;
  const item = payload[0].payload as ProcessedDayPoint;
  const val = item.value;

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-secondary)',
        border: '1px solid var(--border-card)',
        borderRadius: 'var(--radius-sm)',
        padding: '0.6rem 0.85rem',
        boxShadow: 'var(--shadow-card)',
        fontFamily: 'var(--font-mono)',
        fontSize: '0.8125rem',
      }}
    >
      <div style={{ color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
        Date: <strong style={{ color: 'var(--text-primary)' }}>{item.date}</strong>
      </div>
      <div className="tabular-nums" style={{ color: 'var(--text-primary)' }}>
        {payload[0].name}:{' '}
        <strong style={{ color: 'var(--color-forecast)' }}>
          {isPct ? formatPct(val) : formatMW(val)}
        </strong>
      </div>
      {typeof item.meanBias === 'number' && (
        <div
          className="tabular-nums"
          style={{
            fontSize: '0.75rem',
            color: item.meanBias >= 0 ? 'var(--color-danger)' : 'var(--color-success)',
            marginTop: '0.2rem',
          }}
        >
          Bias: {item.meanBias >= 0 ? '+' : ''}
          {formatMW(item.meanBias)}
        </div>
      )}
    </div>
  );
}

interface MetricBarSectionProps {
  title: string;
  subtitle: string;
  data: ProcessedDayPoint[];
  dataKey: string;
  yFormatter: (val: number | string) => string;
  isPct: boolean;
  unit: string;
}

/**
 * Individual Single Metric Bar Chart Card
 */
function MetricBarSection({
  title,
  subtitle,
  data,
  yFormatter,
  isPct,
  unit,
}: MetricBarSectionProps) {
  const values = data.map((d) => d.value).filter((v) => typeof v === 'number' && !Number.isNaN(v));
  const min = values.length > 0 ? Math.min(...values) : 0;
  const max = values.length > 0 ? Math.max(...values) : 100;

  return (
    <div className="chart-container" style={{ minHeight: '260px', marginBottom: '1.5rem' }}>
      <div className="chart-header">
        <div>
          <h3 className="chart-title" style={{ fontSize: '1rem' }}>{title}</h3>
          <p className="page-subtitle" style={{ fontSize: '0.75rem' }}>{subtitle}</p>
        </div>
        <div style={{ display: 'flex', gap: '1rem', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
          <span style={{ color: 'var(--tier-good)' }}>■ Low</span>
          <span style={{ color: 'var(--tier-mod)' }}>■ Moderate</span>
          <span style={{ color: 'var(--tier-bad)' }}>■ High</span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
          <XAxis
            dataKey="day"
            stroke="var(--text-muted)"
            tick={{ fill: 'var(--text-secondary)', fontSize: 11, fontFamily: 'var(--font-mono)' }}
            tickLine={false}
          />
          <YAxis
            stroke="var(--text-muted)"
            tickFormatter={yFormatter}
            tick={{ fill: 'var(--text-secondary)', fontSize: 11, fontFamily: 'var(--font-mono)' }}
            tickLine={false}
            axisLine={false}
            width={45}
          />
          <Tooltip content={<DailyMetricTooltip unit={unit} isPct={isPct} />} />
          <Bar dataKey="value" name={title} radius={[2, 2, 0, 0]}>
            {data.map((entry, index) => (
              <Cell key={`bar-${index}`} fill={getTierColor(entry.value, min, max)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/**
 * AccuracyCharts — Three stacked bar charts (MAE, RMSE, MAPE) with three-tier dynamic colouring
 * and the executive insight callout banner.
 */
export function AccuracyCharts({ daily = [], insight = '', isLoading, error }: AccuracyChartsProps) {
  // Extract day of month as integer (1 - 31)
  const maeData = useMemo<ProcessedDayPoint[]>(() => {
    return (daily || []).map((d) => ({
      day: parseInt(d.date.slice(8, 10), 10),
      date: d.date,
      value: d.mae,
      meanBias: d.mean_bias,
    }));
  }, [daily]);

  const rmseData = useMemo<ProcessedDayPoint[]>(() => {
    return (daily || []).map((d) => ({
      day: parseInt(d.date.slice(8, 10), 10),
      date: d.date,
      value: d.rmse,
      meanBias: d.mean_bias,
    }));
  }, [daily]);

  const mapeData = useMemo<ProcessedDayPoint[]>(() => {
    return (daily || []).map((d) => ({
      day: parseInt(d.date.slice(8, 10), 10),
      date: d.date,
      value: d.mape,
      meanBias: d.mean_bias,
    }));
  }, [daily]);

  // Determine insight banner styling from verbatim API string
  const isOverestimated = (insight || '').toLowerCase().includes('overestimated');
  const insightBorderColor = isOverestimated ? 'var(--tier-bad)' : 'var(--tier-good)';
  const insightTagColor = isOverestimated ? 'var(--color-danger)' : 'var(--color-success)';

  // Loading state: three placeholder bars matching real charts height
  if (isLoading) {
    return (
      <div>
        {[1, 2, 3].map((idx) => (
          <div
            key={idx}
            className="chart-container"
            style={{
              height: '240px',
              minHeight: '240px',
              marginBottom: '1.5rem',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              alignItems: 'center',
            }}
          >
            <div className="shimmer-bar" />
            <div className="overlay-message">Loading daily accuracy metrics...</div>
          </div>
        ))}
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="chart-container" style={{ minHeight: '280px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div className="error-card">
          <div className="error-title">Unable to Load Monthly Accuracy Data</div>
          <div className="error-detail">{error}</div>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Chart 1: Daily MAE */}
      <MetricBarSection
        title="Daily Mean Absolute Error (MAE)"
        subtitle="Average magnitude of hourly forecast error per day (MW)"
        data={maeData}
        dataKey="mae"
        unit="MW"
        isPct={false}
        yFormatter={(val) => Number(val).toLocaleString('en-GB')}
      />

      {/* Chart 2: Daily RMSE */}
      <MetricBarSection
        title="Daily Root Mean Square Error (RMSE)"
        subtitle="Error penalising extreme deviation spikes (MW)"
        data={rmseData}
        dataKey="rmse"
        unit="MW"
        isPct={false}
        yFormatter={(val) => Number(val).toLocaleString('en-GB')}
      />

      {/* Chart 3: Daily MAPE */}
      <MetricBarSection
        title="Daily Mean Absolute Percentage Error (MAPE)"
        subtitle="Relative error (% of actual generation, calm slots < 5 MW excluded)"
        data={mapeData}
        dataKey="mape"
        unit="%"
        isPct={true}
        yFormatter={(val) => `${Number(val).toFixed(0)}%`}
      />

      {/* Insight Callout Box */}
      {insight && (
        <div
          className="insight-banner"
          style={{ borderLeftColor: insightBorderColor }}
        >
          <span
            className="insight-tag"
            style={{
              color: insightTagColor,
              backgroundColor: isOverestimated
                ? 'rgba(239, 68, 68, 0.15)'
                : 'rgba(16, 185, 129, 0.15)',
            }}
          >
            {isOverestimated ? 'Systematic Overestimation' : 'Systematic Underestimation'}
          </span>
          <div className="insight-text">
            <strong>Executive Takeaway:</strong> {insight}
          </div>
        </div>
      )}
    </div>
  );
}

export default AccuracyCharts;

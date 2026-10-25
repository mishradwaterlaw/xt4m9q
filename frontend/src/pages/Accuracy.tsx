import { useMemo } from 'react';
import { fetchAccuracy } from '../services/api';
import { useApi } from '../hooks/useApi';
import { SummaryCard } from '../components/SummaryCards';
import AccuracyCharts from '../components/AccuracyCharts';
import { formatMW, formatPct } from '../utils/format';
import type { AccuracyResponse } from '../types';

interface BiasMetrics {
  value: string;
  isOverestimated: boolean;
  isUnderestimated: boolean;
  delta: number | null;
  deltaLabel?: string;
  subtext: string;
}

export default function Accuracy() {
  // Fetch monthly accuracy metrics once on mount
  const { data, isLoading, error } = useApi<AccuracyResponse>(
    (signalOrUnknown?: unknown) => fetchAccuracy(signalOrUnknown as AbortSignal | undefined)
  );

  // Derive Avg Bias metric from the server-computed insight string
  const biasMetrics = useMemo<BiasMetrics>(() => {
    const insightStr = data?.insight || '';
    const isOverestimated = insightStr.toLowerCase().includes('overestimated');
    const isUnderestimated = insightStr.toLowerCase().includes('underestimated');

    // Extract numerical MW value from string: e.g. "Forecasts overestimated by 1714 MW..."
    const match = insightStr.match(/(\d+(?:\.\d+)?)\s*MW/i);
    const biasValue = match ? parseFloat(match[1]) : null;

    return {
      value: biasValue !== null ? formatMW(biasValue) : '-- MW',
      isOverestimated,
      isUnderestimated,
      // When isOverestimated is true, pass delta as negative so card shows red downward arrow
      delta: biasValue !== null ? (isOverestimated ? -biasValue : biasValue) : null,
      deltaLabel: isOverestimated
        ? 'systematic over-forecast'
        : isUnderestimated
        ? 'systematic under-forecast'
        : undefined,
      subtext: isOverestimated
        ? 'Systematic over-procurement risk'
        : isUnderestimated
        ? 'Systematic under-hedging risk'
        : 'Awaiting monthly calculation...',
    };
  }, [data?.insight]);

  return (
    <div>
      {/* Page Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Monthly Forecast Accuracy Analytics</h1>
          <p className="page-subtitle">
            Settlement error metrics (MAE, RMSE, MAPE) across January 2026
          </p>
        </div>
      </div>

      {/* Monthly KPI Summary Cards */}
      <div className="card-grid">
        <SummaryCard
          label="Monthly MAE"
          value={formatMW(data?.monthly?.mae)}
          subtext="Mean absolute error across all hours"
        />
        <SummaryCard
          label="Monthly RMSE"
          value={formatMW(data?.monthly?.rmse)}
          subtext="Root mean square error (outlier sensitivity)"
        />
        <SummaryCard
          label="Monthly MAPE"
          value={formatPct(data?.monthly?.mape)}
          subtext="Percentage error (excluding < 5 MW slots)"
        />
        <SummaryCard
          label="Avg Bias"
          value={biasMetrics.value}
          delta={biasMetrics.delta ?? undefined}
          deltaLabel={biasMetrics.deltaLabel}
          subtext={biasMetrics.subtext}
        />
      </div>

      {/* 3-Tier Daily Bar Charts & Verbatim Insight Callout */}
      <AccuracyCharts
        daily={data?.daily || []}
        insight={data?.insight || ''}
        isLoading={isLoading}
        error={error}
      />
    </div>
  );
}

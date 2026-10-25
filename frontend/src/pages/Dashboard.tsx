import { useState, useMemo } from 'react';
import { fetchForecast, fetchActuals } from '../services/api';
import { useApi } from '../hooks/useApi';
import { SummaryCard } from '../components/SummaryCards';
import ForecastChart from '../components/ForecastChart';
import { formatMW } from '../utils/format';
import type { HourlyRecord, ForecastResponse, ActualsResponse } from '../types';

export interface PeakMetrics {
  peakHourTime: string | null;
  peakActual: number | null;
  peakForecast: number | null;
  difference: number | null;
}

/**
 * Generate an array of 31 dates for January 2026: ['2026-01-01', ..., '2026-01-31']
 */
const JANUARY_2026_DATES: string[] = Array.from({ length: 31 }, (_, i) => {
  const day = String(i + 1).padStart(2, '0');
  return `2026-01-${day}`;
});

export default function Dashboard() {
  const [selectedDate, setSelectedDate] = useState<string>('2026-01-15');

  // Fetch actuals and forecast in parallel using the generic useApi hook
  const {
    data: forecastData,
    isLoading: isForecastLoading,
    error: forecastError,
    refetch: refetchForecast,
  } = useApi<ForecastResponse>(
    // Type-safe fetch wrapper: useApi params object values map directly to fetchForecast args
    (dateOrSignal?: unknown, maybeSignal?: unknown) => {
      if (typeof dateOrSignal === 'string') {
        return fetchForecast(dateOrSignal, maybeSignal as AbortSignal | undefined);
      }
      return fetchForecast(selectedDate, dateOrSignal as AbortSignal | undefined);
    },
    { date: selectedDate },
    [selectedDate]
  );

  const {
    data: actualsData,
    isLoading: isActualsLoading,
    error: actualsError,
    refetch: refetchActuals,
  } = useApi<ActualsResponse>(
    // Type-safe fetch wrapper: useApi params object values map directly to fetchActuals args
    (dateOrSignal?: unknown, maybeSignal?: unknown) => {
      if (typeof dateOrSignal === 'string') {
        return fetchActuals(dateOrSignal, maybeSignal as AbortSignal | undefined);
      }
      return fetchActuals(selectedDate, dateOrSignal as AbortSignal | undefined);
    },
    { date: selectedDate },
    [selectedDate]
  );

  const forecastRecords: HourlyRecord[] = forecastData?.records || [];
  const actualsRecords: HourlyRecord[] = actualsData?.records || [];

  // Derive peak hour client-side from the actuals array (highest actual generation)
  const peakMetrics: PeakMetrics = useMemo<PeakMetrics>(() => {
    if (!actualsRecords || actualsRecords.length === 0) {
      return {
        peakHourTime: null,
        peakActual: null,
        peakForecast: null,
        difference: null,
      };
    }

    // Find the record in actuals with highest generation
    const highestActualRecord = actualsRecords.reduce((max, current) => {
      return current.generation > max.generation ? current : max;
    }, actualsRecords[0]);

    const peakTime = highestActualRecord.startTime;
    const peakActual = highestActualRecord.generation;

    // Find corresponding forecast generation at that identical peak slot
    const matchingForecastRecord = forecastRecords.find((f) => f.startTime === peakTime);
    const peakForecast = matchingForecastRecord ? matchingForecastRecord.generation : null;

    const difference =
      typeof peakForecast === 'number' && typeof peakActual === 'number'
        ? peakForecast - peakActual
        : null;

    return {
      peakHourTime: peakTime ? peakTime.slice(11, 16) : null,
      peakActual,
      peakForecast,
      difference,
    };
  }, [actualsRecords, forecastRecords]);

  // Combined loading and error states for the chart
  const combinedIsLoading = isForecastLoading || isActualsLoading;
  const combinedError = forecastError || actualsError;

  const handleRetry = () => {
    refetchForecast();
    refetchActuals();
  };

  return (
    <div>
      {/* Page Header & Date Selector */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Day-Ahead Wind Forecast vs Actuals</h1>
          <p className="page-subtitle">
            Hourly generation profiles and gate closure verification for January 2026
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <label
            htmlFor="date-select"
            style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', fontWeight: 500 }}
          >
            Delivery Date:
          </label>
          <select
            id="date-select"
            className="custom-select"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
          >
            {JANUARY_2026_DATES.map((dateStr) => (
              <option key={dateStr} value={dateStr}>
                {dateStr}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Summary Cards Row (Peak Hour Metrics) */}
      <div className="card-grid">
        <SummaryCard
          label="Forecast at Peak"
          value={formatMW(peakMetrics.peakForecast)}
          subtext={
            peakMetrics.peakHourTime
              ? `Forecast at peak actual hour (${peakMetrics.peakHourTime} UTC)`
              : 'Awaiting data...'
          }
        />
        <SummaryCard
          label="Actual at Peak"
          value={formatMW(peakMetrics.peakActual)}
          subtext={
            peakMetrics.peakHourTime
              ? `Peak actual demand at ${peakMetrics.peakHourTime} UTC`
              : 'Awaiting data...'
          }
        />
        <SummaryCard
          label="Difference"
          value={
            peakMetrics.difference !== null
              ? formatMW(Math.abs(peakMetrics.difference))
              : '-- MW'
          }
          delta={peakMetrics.difference ?? undefined}
          subtext={
            peakMetrics.difference !== null
              ? peakMetrics.difference > 0
                ? 'Forecast exceeded actual'
                : 'Forecast was under actual'
              : undefined
          }
        />
      </div>

      {/* Interactive Forecast vs Actuals Chart */}
      <ForecastChart
        forecastRecords={forecastRecords}
        actualsRecords={actualsRecords}
        vintage={forecastData?.vintage}
        gateClosure={forecastData?.gate_closure}
        isLoading={combinedIsLoading}
        error={combinedError}
        onRetry={handleRetry}
      />
    </div>
  );
}

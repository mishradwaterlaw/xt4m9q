/**
 * src/services/api.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * HTTP API client for communicating with the FastAPI backend.
 * Uses `import.meta.env.VITE_API_URL || ''` as base URL so in local development
 * it falls back to an empty string (triggering Vite's proxy configured in
 * vite.config.ts to http://localhost:8000), while in production it points
 * directly to the deployed backend URL (Railway/Render) without code changes.
 */

import type {
  ActualsResponse,
  ForecastResponse,
  AccuracyResponse,
  HealthResponse,
} from '../types';

const BASE_URL: string = import.meta.env.VITE_API_URL || '';

/**
 * Type guard to safely extract backend error details without unchecked casting.
 */
function isErrorPayload(data: unknown): data is { detail: string } {
  return (
    typeof data === 'object' &&
    data !== null &&
    'detail' in data &&
    typeof (data as Record<string, unknown>).detail === 'string'
  );
}

/**
 * Internal request helper that checks response status and extracts JSON error details.
 *
 * @param endpoint - Path relative to base URL (e.g., '/api/actuals?date=...')
 * @param options - Fetch options including signal for AbortController
 * @returns Parsed JSON response typed as T
 */
async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    headers: {
      Accept: 'application/json',
    },
    ...options,
  });

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errorJson: unknown = await response.json();
      if (isErrorPayload(errorJson)) {
        errorMessage = errorJson.detail;
      }
    } catch {
      // Body was not JSON; fallback to status text
    }
    throw new Error(errorMessage);
  }

  // response.json() returns Promise<any> in DOM types; type assertion to Promise<T> is required to establish the generic boundary
  return response.json() as Promise<T>;
}

/**
 * Fetch hourly wind generation actuals for a specific date (YYYY-MM-DD).
 *
 * @param date - Date in YYYY-MM-DD format within January 2026
 * @param signal - Optional signal to cancel in-flight request
 * @returns Hourly actuals response
 */
export async function fetchActuals(date: string, signal?: AbortSignal): Promise<ActualsResponse> {
  return request<ActualsResponse>(`/api/actuals?date=${encodeURIComponent(date)}`, { signal });
}

/**
 * Fetch hourly day-ahead forecast for a specific date (YYYY-MM-DD).
 * Includes vintage and gate_closure metadata.
 *
 * @param date - Date in YYYY-MM-DD format within January 2026
 * @param signal - Optional signal to cancel in-flight request
 * @returns Day-ahead forecast response
 */
export async function fetchForecast(date: string, signal?: AbortSignal): Promise<ForecastResponse> {
  return request<ForecastResponse>(`/api/forecast?date=${encodeURIComponent(date)}`, { signal });
}

/**
 * Fetch monthly accuracy metrics (MAE, RMSE, MAPE) for January 2026.
 *
 * @param signal - Optional signal to cancel in-flight request
 * @returns Monthly and daily accuracy metrics
 */
export async function fetchAccuracy(signal?: AbortSignal): Promise<AccuracyResponse> {
  return request<AccuracyResponse>('/api/accuracy', { signal });
}

/**
 * Check backend health status and DB connectivity.
 *
 * @param signal - Optional signal to cancel on timeout
 * @returns Backend health probe status
 */
export async function checkHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>('/health', { signal });
}

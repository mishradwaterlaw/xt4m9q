/**
 * src/utils/format.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Central formatting utilities for numeric values across all components.
 * Enforces consistency and tabular numeric layout:
 *   - MW: comma separators, 1 decimal place (e.g., "14,456.5 MW")
 *   - %:  1 decimal place, % suffix        (e.g., "18.1%")
 */

/**
 * Format a generation or error value in Megawatts (MW).
 * Formats with comma thousands separators and exactly one decimal place.
 * Returns "-- MW" if value is null, undefined, or NaN.
 *
 * @param value - Numeric value in MW
 * @returns Formatted string with comma separators and 1 decimal place
 */
export function formatMW(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '-- MW';
  }
  const num = Number(value);
  return `${num.toLocaleString('en-GB', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })} MW`;
}

/**
 * Format a percentage value (such as MAPE).
 * Formats with exactly one decimal place and a '%' suffix.
 * Returns "--%" if value is null, undefined, or NaN.
 *
 * @param value - Percentage value (0 - 100)
 * @returns Formatted string with 1 decimal place and '%' suffix
 */
export function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '--%';
  }
  const num = Number(value);
  return `${num.toLocaleString('en-GB', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}%`;
}

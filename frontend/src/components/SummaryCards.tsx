import { formatMW } from '../utils/format';

export interface SummaryCardProps {
  label: string;
  value: string;
  unit?: string;
  delta?: number;
  deltaLabel?: string;
  subtext?: string;
}

export interface SummaryCardsProps {
  cards?: SummaryCardProps[];
}

/**
 * SummaryCard — Individual metric card presentation.
 */
export function SummaryCard({
  label,
  value,
  unit,
  delta,
  deltaLabel,
  subtext,
}: SummaryCardProps) {
  const hasDelta = typeof delta === 'number' && !Number.isNaN(delta);
  const isPositiveDelta = hasDelta && delta > 0;
  const isNegativeDelta = hasDelta && delta < 0;

  // Derive card background styling from delta if provided
  let cardClassName = 'metric-card';
  if (hasDelta) {
    if (delta > 500) {
      cardClassName += ' diff-alert';
    } else if (Math.abs(delta) <= 500) {
      cardClassName += ' diff-ok';
    }
  }

  return (
    <div className={cardClassName}>
      <div className="metric-label">{label}</div>
      <div className="metric-value tabular-nums">
        {value}
        {unit && <span className="metric-unit">{unit}</span>}
      </div>

      {hasDelta && (
        <div
          className="metric-subtext tabular-nums"
          style={{
            color: isPositiveDelta
              ? 'var(--color-success)'
              : isNegativeDelta
              ? 'var(--color-danger)'
              : 'var(--text-muted)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.25rem',
            fontWeight: 600,
          }}
        >
          <span>{isPositiveDelta ? '▲' : isNegativeDelta ? '▼' : '•'}</span>
          <span>{formatMW(Math.abs(delta))}</span>
          <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>
            {deltaLabel || (isPositiveDelta ? 'above actual' : isNegativeDelta ? 'below actual' : 'exact match')}
          </span>
        </div>
      )}

      {subtext && !hasDelta && (
        <div className="metric-subtext">{subtext}</div>
      )}
    </div>
  );
}

/**
 * SummaryCards — Row container.
 * When `cards` prop is passed, renders that array.
 * Defaults to four hardcoded cards for layout demonstration as requested.
 */
export function SummaryCards({ cards }: SummaryCardsProps) {
  const defaultHardcodedCards: SummaryCardProps[] = [
    {
      label: 'Forecast at Peak',
      value: '16,500.0',
      unit: 'MW',
      subtext: 'Peak demand hour 18:00 UTC',
    },
    {
      label: 'Actual at Peak',
      value: '14,456.5',
      unit: 'MW',
      subtext: 'Elexon FUELHH settled actual',
    },
    {
      label: 'Difference',
      value: '2,043.5',
      unit: 'MW',
      delta: -2043.5, // Negative delta to verify red indicator
    },
    {
      label: 'Monthly MAE',
      value: '1,935.7',
      unit: 'MW',
      subtext: 'Full month January 2026',
    },
  ];

  const items = cards && cards.length > 0 ? cards : defaultHardcodedCards;

  return (
    <div className="card-grid">
      {items.map((card, idx) => (
        <SummaryCard
          key={card.label || idx}
          label={card.label}
          value={card.value}
          unit={card.unit}
          delta={card.delta}
          deltaLabel={card.deltaLabel}
          subtext={card.subtext}
        />
      ))}
    </div>
  );
}

export default SummaryCards;

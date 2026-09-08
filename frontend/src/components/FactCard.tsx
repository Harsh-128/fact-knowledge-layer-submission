import type { Fact } from '../api/client';

interface FactCardProps {
  fact: Fact;
  onSelect?: (fact: Fact) => void;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) {
    return 'N/A';
  }

  if (typeof value === 'object') {
    return JSON.stringify(value, null, 2);
  }

  return String(value);
}

function confidenceLabel(confidence: number): string {
  if (confidence >= 0.8) {
    return 'High confidence';
  }

  if (confidence >= 0.5) {
    return 'Medium confidence';
  }

  return 'Low confidence';
}

function FactCard({ fact, onSelect }: FactCardProps) {
  const value = formatValue(fact.value);
  const confidence = Math.max(0, Math.min(1, fact.confidence));

  return (
    <article
      className="fact-card"
      onClick={() => onSelect?.(fact)}
      role={onSelect ? 'button' : undefined}
      tabIndex={onSelect ? 0 : undefined}
      onKeyDown={(event) => {
        if (onSelect && (event.key === 'Enter' || event.key === ' ')) {
          event.preventDefault();
          onSelect(fact);
        }
      }}
    >
      <div className="fact-card-header">
        <div>
          <span className="fact-type">{fact.fact_type_id}</span>
          <h3>{fact.attribute}</h3>
        </div>

        {fact.needs_review && (
          <span className="review-badge">Needs review</span>
        )}
      </div>

      <div className="fact-value">
        <strong>{value}</strong>
        {fact.unit && <span className="fact-unit">{fact.unit}</span>}
      </div>

      <div className="fact-metadata">
        <span>
          {confidenceLabel(confidence)} · {Math.round(confidence * 100)}%
        </span>

        <span>Entity: {fact.entity_id}</span>
      </div>

      {fact.temporal_scope && (
        <div className="fact-period">
          <strong>Period:</strong>{' '}
          {String(
            fact.temporal_scope.period_label ??
              fact.temporal_scope.granularity ??
              'Not specified',
          )}
        </div>
      )}

      {fact.evidence.length > 0 && (
        <div className="fact-evidence">
          <strong>Evidence</strong>
          <p>
            “{fact.evidence[0].quoted_text}”
          </p>
          <span>Page {fact.evidence[0].page_number}</span>
        </div>
      )}
    </article>
  );
}

export default FactCard;

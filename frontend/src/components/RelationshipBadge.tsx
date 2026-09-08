import type { Relationship } from '../api/client';

interface RelationshipBadgeProps {
  relationship: Relationship;
}

const relationshipLabels: Record<string, string> = {
  CORROBORATES: 'Corroborates',
  CONTRADICTS: 'Contradicts',
  RECONCILES: 'Reconciles',
  UNRELATED: 'Unrelated',
};

function RelationshipBadge({
  relationship,
}: RelationshipBadgeProps) {
  const type = relationship.relationship_type.toUpperCase();

  const label = relationshipLabels[type] ?? relationship.relationship_type;

  const confidence = Math.max(
    0,
    Math.min(1, relationship.confidence),
  );

  return (
    <div className={`relationship-badge relationship-${type.toLowerCase()}`}>
      <div className="relationship-badge-main">
        <span className="relationship-label">{label}</span>

        <span className="relationship-confidence">
          {Math.round(confidence * 100)}%
        </span>
      </div>

      {relationship.explanation && (
        <p className="relationship-explanation">
          {relationship.explanation}
        </p>
      )}

      {relationship.needs_review && (
        <span className="relationship-review">
          Needs review
        </span>
      )}
    </div>
  );
}

export default RelationshipBadge;

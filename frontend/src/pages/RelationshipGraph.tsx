import { useEffect, useState } from 'react';

import {
  Fact,
  getFacts,
  getRelationships,
  Relationship,
} from '../api/client';
import RelationshipBadge from '../components/RelationshipBadge';

function RelationshipGraph() {
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [facts, setFacts] = useState<Record<string, Fact>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadRelationships = async () => {
      setLoading(true);
      setError('');

      try {
        const relationshipResult = await getRelationships({
          limit: 100,
          offset: 0,
        });

        setRelationships(relationshipResult);

        const factResult = await getFacts({
          limit: 100,
          offset: 0,
        });

        const factMap: Record<string, Fact> = {};

        for (const fact of factResult) {
          factMap[fact.id] = fact;
        }

        setFacts(factMap);
      } catch (loadError) {
        setRelationships([]);
        setFacts({});

        if (loadError instanceof Error && loadError.message) {
          setError(loadError.message);
        } else {
          setError(
            'Unable to load relationships. Make sure the FastAPI backend is running.',
          );
        }
      } finally {
        setLoading(false);
      }
    };

    void loadRelationships();
  }, []);

  return (
    <section className="relationship-graph">
      <div className="page-heading">
        <span className="eyebrow">Cross-document reasoning</span>

        <h2>Relationship Explorer</h2>

        <p>
          Inspect how extracted facts relate to one another across
          documents.
        </p>
      </div>

      <div className="relationship-summary">
        <div>
          <strong>{relationships.length}</strong>
          <span>Relationships</span>
        </div>

        <div>
          <strong>
            {
              relationships.filter(
                (item) => item.relationship_type.toLowerCase() === 'corroborates',
              ).length
            }
          </strong>
          <span>Corroborations</span>
        </div>

        <div>
          <strong>
            {
              relationships.filter(
                (item) => item.relationship_type.toLowerCase() === 'contradicts',
              ).length
            }
          </strong>
          <span>Contradictions</span>
        </div>

        <div>
          <strong>
            {
              relationships.filter(
                (item) => item.relationship_type.toLowerCase() === 'reconciles',
              ).length
            }
          </strong>
          <span>Reconciliations</span>
        </div>
      </div>

      {error && (
        <div className="page-message page-error">
          {error}
        </div>
      )}

      {loading && (
        <div className="empty-state">
          Loading relationships...
        </div>
      )}

      {!loading && !error && relationships.length === 0 && (
        <div className="empty-state">
          No fact relationships have been created yet.
        </div>
      )}

      {!loading && relationships.length > 0 && (
        <div className="relationship-list">
          {relationships.map((relationship) => {
            const sourceFact = facts[relationship.source_fact_id];
            const targetFact = facts[relationship.target_fact_id];

            return (
              <article
                className="relationship-card"
                key={relationship.id}
              >
                <div className="relationship-facts">
                  <div className="relationship-fact">
                    <span>Source fact</span>
                    <strong>
                      {sourceFact?.attribute ??
                        relationship.source_fact_id}
                    </strong>

                    {sourceFact && (
                      <p>
                        {String(sourceFact.value)}
                        {sourceFact.unit
                          ? ` ${sourceFact.unit}`
                          : ''}
                      </p>
                    )}
                  </div>

                  <div className="relationship-arrow">
                    →
                  </div>

                  <div className="relationship-fact">
                    <span>Target fact</span>
                    <strong>
                      {targetFact?.attribute ??
                        relationship.target_fact_id}
                    </strong>

                    {targetFact && (
                      <p>
                        {String(targetFact.value)}
                        {targetFact.unit
                          ? ` ${targetFact.unit}`
                          : ''}
                      </p>
                    )}
                  </div>
                </div>

                <RelationshipBadge
                  relationship={relationship}
                />
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

export default RelationshipGraph;

import { useEffect, useState } from 'react';

import {
  Document,
  Fact,
  getFact,
  getDocuments,
  getRelationships,
  Relationship,
} from '../api/client';
import RelationshipBadge from '../components/RelationshipBadge';

function RelationshipGraph() {
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [facts, setFacts] = useState<Record<string, Fact>>({});
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Load document list for the filter dropdown
  useEffect(() => {
    getDocuments({ limit: 100 }).then(setDocuments).catch(() => {});
  }, []);

  useEffect(() => {
    const loadRelationships = async () => {
      setLoading(true);
      setError('');

      try {
        const relationshipResult = await getRelationships({
          document_id: selectedDocumentId || undefined,
          limit: 500,
          offset: 0,
        });

        setRelationships(relationshipResult);

        const neededIds = new Set<string>();
        for (const rel of relationshipResult) {
          neededIds.add(rel.source_fact_id);
          neededIds.add(rel.target_fact_id);
        }

        const factEntries = await Promise.allSettled(
          [...neededIds].map((id) => getFact(id)),
        );

        const factMap: Record<string, Fact> = {};
        for (const entry of factEntries) {
          if (entry.status === 'fulfilled') {
            factMap[entry.value.id] = entry.value;
          }
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
  }, [selectedDocumentId]);

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

      {/* Document filter */}
      <div className="fact-filters">
        <div className="filter-field">
          <label htmlFor="doc-filter">Filter by document</label>
          <select
            id="doc-filter"
            value={selectedDocumentId}
            onChange={(e) => setSelectedDocumentId(e.target.value)}
          >
            <option value="">All documents</option>
            {documents.map((doc) => (
              <option key={doc.id} value={doc.id}>
                {doc.filename.replace(/^document:[a-f0-9]+_/, '')}
              </option>
            ))}
          </select>
        </div>
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

import { useEffect, useState } from 'react';

import {
  CompareResponse,
  Document,
  compareDocuments,
  getDocuments,
} from '../api/client';
import RelationshipBadge from '../components/RelationshipBadge';

function ComparePage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [docsLoading, setDocsLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setDocsLoading(true);
    getDocuments({ limit: 100 })
      .then(setDocuments)
      .catch(() => setError('Unable to load documents.'))
      .finally(() => setDocsLoading(false));
  }, []);

  const toggleDocument = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const selectAll = () => {
    setSelectedIds(new Set(documents.map((d) => d.id)));
  };

  const clearAll = () => {
    setSelectedIds(new Set());
  };

  const handleCompare = async () => {
    if (selectedIds.size < 2) {
      setError('Select at least 2 documents to compare.');
      return;
    }

    setLoading(true);
    setError('');
    setResult(null);

    try {
      const response = await compareDocuments([...selectedIds]);
      setResult(response);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Comparison failed. Make sure the backend is running.');
      }
    } finally {
      setLoading(false);
    }
  };

  const cleanFilename = (filename: string) =>
    filename.replace(/^document:[a-f0-9]+_/, '');

  return (
    <section className="compare-page">
      <div className="page-heading">
        <span className="eyebrow">Selective comparison</span>
        <h2>Compare Documents</h2>
        <p>
          Choose which documents to compare. Only facts shared between
          the selected documents will be analysed — others are ignored.
        </p>
      </div>

      {/* Document selector */}
      <div className="compare-selector">
        <div className="compare-selector-header">
          <h3>Select documents ({selectedIds.size} selected)</h3>
          <div className="compare-selector-actions">
            <button type="button" className="secondary-button" onClick={selectAll}>
              Select all
            </button>
            <button type="button" className="secondary-button" onClick={clearAll}>
              Clear
            </button>
          </div>
        </div>

        {docsLoading ? (
          <div className="empty-state">Loading documents...</div>
        ) : (
          <div className="compare-doc-list">
            {documents.map((doc) => (
              <label
                key={doc.id}
                className={`compare-doc-item ${selectedIds.has(doc.id) ? 'selected' : ''}`}
              >
                <input
                  type="checkbox"
                  checked={selectedIds.has(doc.id)}
                  onChange={() => toggleDocument(doc.id)}
                />
                <div className="compare-doc-info">
                  <strong>{cleanFilename(doc.filename)}</strong>
                  <span>{doc.status} · {doc.page_count ?? 0} pages</span>
                </div>
              </label>
            ))}
          </div>
        )}

        <div className="compare-actions">
          <button
            type="button"
            className="upload-button"
            disabled={selectedIds.size < 2 || loading}
            onClick={handleCompare}
          >
            {loading
              ? 'Comparing...'
              : `Compare ${selectedIds.size} document${selectedIds.size !== 1 ? 's' : ''}`}
          </button>
          {selectedIds.size < 2 && (
            <span className="compare-hint">Select at least 2 documents</span>
          )}
        </div>
      </div>

      {error && (
        <div className="page-message page-error">{error}</div>
      )}

      {/* Results */}
      {result && (
        <div className="compare-results">
          <div className="compare-summary">
            <div>
              <strong>{result.facts_considered}</strong>
              <span>Facts analysed</span>
            </div>
            <div>
              <strong>{result.relationships_created}</strong>
              <span>Relationships found</span>
            </div>
            <div>
              <strong>
                {result.relationships.filter(
                  (r) => r.relationship_type.toLowerCase() === 'corroborates',
                ).length}
              </strong>
              <span>Corroborations</span>
            </div>
            <div>
              <strong>
                {result.relationships.filter(
                  (r) => r.relationship_type.toLowerCase() === 'contradicts',
                ).length}
              </strong>
              <span>Contradictions</span>
            </div>
            <div>
              <strong>
                {result.relationships.filter(
                  (r) => r.relationship_type.toLowerCase() === 'reconciles',
                ).length}
              </strong>
              <span>Reconciliations</span>
            </div>
          </div>

          {result.relationships.length === 0 ? (
            <div className="empty-state">
              No relationships found between the selected documents.
              They may not share the same entities or attributes.
            </div>
          ) : (
            <div className="relationship-list">
              {result.relationships.map((rel) => (
                <article className="relationship-card" key={rel.id}>
                  <div className="relationship-facts">
                    <div className="relationship-fact">
                      <span>Source fact</span>
                      <strong>{rel.source_fact_id}</strong>
                    </div>
                    <div className="relationship-arrow">→</div>
                    <div className="relationship-fact">
                      <span>Target fact</span>
                      <strong>{rel.target_fact_id}</strong>
                    </div>
                  </div>
                  <RelationshipBadge relationship={rel} />
                  {rel.explanation && (
                    <p className="relationship-explanation">
                      {rel.explanation}
                    </p>
                  )}
                </article>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

export default ComparePage;

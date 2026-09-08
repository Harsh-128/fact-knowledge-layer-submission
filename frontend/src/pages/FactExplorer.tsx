import { FormEvent, useCallback, useEffect, useState } from 'react';

import { Fact, getFacts } from '../api/client';
import FactCard from '../components/FactCard';

function FactExplorer() {
  const [facts, setFacts] = useState<Fact[]>([]);
  const [documentId, setDocumentId] = useState('');
  const [entityId, setEntityId] = useState('');
  const [attribute, setAttribute] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedFact, setSelectedFact] = useState<Fact | null>(null);

  const loadFacts = useCallback(async () => {
    setLoading(true);
    setError('');

    try {
      const result = await getFacts({
        document_id: documentId.trim() || undefined,
        entity_id: entityId.trim() || undefined,
        attribute: attribute.trim() || undefined,
        limit: 100,
        offset: 0,
      });

      setFacts(result);

      if (
        selectedFact &&
        !result.some((fact) => fact.id === selectedFact.id)
      ) {
        setSelectedFact(null);
      }
    } catch (loadError) {
      setFacts([]);

      if (loadError instanceof Error && loadError.message) {
        setError(loadError.message);
      } else {
        setError(
          'Unable to load facts. Make sure the FastAPI backend is running.',
        );
      }
    } finally {
      setLoading(false);
    }
  }, [attribute, documentId, entityId]);

  useEffect(() => {
    void loadFacts();
  }, []);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void loadFacts();
  };

  const clearFilters = () => {
    setDocumentId('');
    setEntityId('');
    setAttribute('');
    setSelectedFact(null);
  };

  return (
    <section className="fact-explorer">
      <div className="page-heading">
        <span className="eyebrow">Knowledge layer</span>

        <h2>Fact Explorer</h2>

        <p>
          Search extracted facts and inspect the evidence behind
          each claim.
        </p>
      </div>

      <form className="fact-filters" onSubmit={handleSubmit}>
        <div className="filter-field">
          <label htmlFor="document-id">Document ID</label>
          <input
            id="document-id"
            value={documentId}
            onChange={(event) => setDocumentId(event.target.value)}
            placeholder="document:..."
          />
        </div>

        <div className="filter-field">
          <label htmlFor="entity-id">Entity ID</label>
          <input
            id="entity-id"
            value={entityId}
            onChange={(event) => setEntityId(event.target.value)}
            placeholder="entity:..."
          />
        </div>

        <div className="filter-field">
          <label htmlFor="attribute">Attribute</label>
          <input
            id="attribute"
            value={attribute}
            onChange={(event) => setAttribute(event.target.value)}
            placeholder="e.g. revenue"
          />
        </div>

        <div className="filter-actions">
          <button type="submit" disabled={loading}>
            {loading ? 'Loading...' : 'Search facts'}
          </button>

          <button
            type="button"
            className="secondary-button"
            onClick={clearFilters}
          >
            Clear
          </button>
        </div>
      </form>

      {error && (
        <div className="page-message page-error">
          {error}
        </div>
      )}

      <div className="fact-explorer-layout">
        <div className="fact-results">
          <div className="results-header">
            <h3>Facts</h3>
            <span>
              {facts.length} result{facts.length !== 1 ? 's' : ''}
            </span>
          </div>

          {loading && (
            <div className="empty-state">
              Loading facts...
            </div>
          )}

          {!loading && !error && facts.length === 0 && (
            <div className="empty-state">
              No facts found. Upload and process a document first.
            </div>
          )}

          {!loading &&
            facts.map((fact) => (
              <FactCard
                key={fact.id}
                fact={fact}
                onSelect={setSelectedFact}
              />
            ))}
        </div>

        <aside className="fact-selection">
          <h3>Selected fact</h3>

          {selectedFact ? (
            <>
              <div className="selected-fact-title">
                {selectedFact.attribute}
              </div>

              <div className="selected-fact-value">
                {String(selectedFact.value)}
                {selectedFact.unit
                  ? ` ${selectedFact.unit}`
                  : ''}
              </div>

              <dl>
                <div>
                  <dt>Fact ID</dt>
                  <dd>{selectedFact.id}</dd>
                </div>

                <div>
                  <dt>Entity</dt>
                  <dd>{selectedFact.entity_id}</dd>
                </div>

                <div>
                  <dt>Document</dt>
                  <dd>{selectedFact.document_id}</dd>
                </div>

                <div>
                  <dt>Confidence</dt>
                  <dd>
                    {Math.round(selectedFact.confidence * 100)}%
                  </dd>
                </div>
              </dl>

              {selectedFact.evidence.length > 0 && (
                <div className="selected-evidence-preview">
                  <h4>Evidence</h4>
                  <p>
                    “{selectedFact.evidence[0].quoted_text}”
                  </p>
                  <span>
                    Page {selectedFact.evidence[0].page_number}
                  </span>
                </div>
              )}
            </>
          ) : (
            <p className="selection-placeholder">
              Select a fact to inspect its details.
            </p>
          )}
        </aside>
      </div>
    </section>
  );
}

export default FactExplorer;

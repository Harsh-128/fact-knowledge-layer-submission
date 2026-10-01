import { FormEvent, useCallback, useEffect, useState } from 'react';

import { Fact, exportFactsAsCsv, getFacts } from '../api/client';
import FactCard from '../components/FactCard';

const PAGE_SIZE = 50;

type SortOrder = 'default' | 'confidence_desc' | 'confidence_asc';

function FactExplorer() {
  const [facts, setFacts] = useState<Fact[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);

  const [documentId, setDocumentId] = useState('');
  const [entityId, setEntityId] = useState('');
  const [attribute, setAttribute] = useState('');
  const [minConfidence, setMinConfidence] = useState(0);
  const [sortOrder, setSortOrder] = useState<SortOrder>('default');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedFact, setSelectedFact] = useState<Fact | null>(null);

  const loadFacts = useCallback(async (pageOverride?: number) => {
    const currentPage = pageOverride ?? page;
    setLoading(true);
    setError('');

    try {
      const result = await getFacts({
        document_id: documentId.trim() || undefined,
        entity_id: entityId.trim() || undefined,
        attribute: attribute.trim() || undefined,
        limit: 500, // fetch more so we can sort/filter client-side
        offset: 0,
      });

      // Client-side confidence filter
      const filtered = minConfidence > 0
        ? result.filter((f) => f.confidence >= minConfidence / 100)
        : result;

      // Client-side sort
      const sorted = [...filtered].sort((a, b) => {
        if (sortOrder === 'confidence_desc') return b.confidence - a.confidence;
        if (sortOrder === 'confidence_asc') return a.confidence - b.confidence;
        return 0;
      });

      setTotal(sorted.length);

      // Paginate
      const start = currentPage * PAGE_SIZE;
      setFacts(sorted.slice(start, start + PAGE_SIZE));

      setSelectedFact((prev) =>
        prev && !sorted.some((f) => f.id === prev.id) ? null : prev,
      );
    } catch (loadError) {
      setFacts([]);
      if (loadError instanceof Error) setError(loadError.message);
      else setError('Unable to load facts. Make sure the FastAPI backend is running.');
    } finally {
      setLoading(false);
    }
  }, [attribute, documentId, entityId, minConfidence, sortOrder, page]);

  useEffect(() => {
    void loadFacts();
  }, [loadFacts]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setPage(0);
    void loadFacts(0);
  };

  const clearFilters = () => {
    setDocumentId('');
    setEntityId('');
    setAttribute('');
    setMinConfidence(0);
    setSortOrder('default');
    setPage(0);
    setSelectedFact(null);
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const handleExport = async () => {
    // Fetch all matching facts for export (not just current page)
    try {
      const all = await getFacts({
        document_id: documentId.trim() || undefined,
        entity_id: entityId.trim() || undefined,
        attribute: attribute.trim() || undefined,
        limit: 500,
        offset: 0,
      });
      const filtered = minConfidence > 0
        ? all.filter((f) => f.confidence >= minConfidence / 100)
        : all;
      exportFactsAsCsv(filtered);
    } catch {
      setError('Export failed.');
    }
  };

  return (
    <section className="fact-explorer">
      <div className="page-heading">
        <span className="eyebrow">Knowledge layer</span>
        <h2>Fact Explorer</h2>
        <p>Search extracted facts and inspect the evidence behind each claim.</p>
      </div>

      <form className="fact-filters" onSubmit={handleSubmit}>
        <div className="filter-field">
          <label htmlFor="document-id">Document ID</label>
          <input
            id="document-id"
            value={documentId}
            onChange={(e) => setDocumentId(e.target.value)}
            placeholder="document:..."
          />
        </div>

        <div className="filter-field">
          <label htmlFor="entity-id">Entity ID</label>
          <input
            id="entity-id"
            value={entityId}
            onChange={(e) => setEntityId(e.target.value)}
            placeholder="entity:..."
          />
        </div>

        <div className="filter-field">
          <label htmlFor="attribute">Attribute</label>
          <input
            id="attribute"
            value={attribute}
            onChange={(e) => setAttribute(e.target.value)}
            placeholder="e.g. revenue"
          />
        </div>

        <div className="filter-field">
          <label htmlFor="min-confidence">Min confidence: {minConfidence}%</label>
          <input
            id="min-confidence"
            type="range"
            min={0}
            max={100}
            step={5}
            value={minConfidence}
            onChange={(e) => setMinConfidence(Number(e.target.value))}
          />
        </div>

        <div className="filter-field">
          <label htmlFor="sort-order">Sort by</label>
          <select
            id="sort-order"
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value as SortOrder)}
          >
            <option value="default">Default</option>
            <option value="confidence_desc">Confidence ↓ (highest first)</option>
            <option value="confidence_asc">Confidence ↑ (lowest first)</option>
          </select>
        </div>

        <div className="filter-actions">
          <button type="submit" disabled={loading}>
            {loading ? 'Loading...' : 'Search facts'}
          </button>
          <button type="button" className="secondary-button" onClick={clearFilters}>
            Clear
          </button>
          <button
            type="button"
            className="secondary-button"
            onClick={handleExport}
            disabled={total === 0}
            title="Download all matching facts as CSV"
          >
            ⬇️ Export CSV
          </button>
        </div>
      </form>

      {error && <div className="page-message page-error">{error}</div>}

      <div className="fact-explorer-layout">
        <div className="fact-results">
          <div className="results-header">
            <h3>Facts</h3>
            <span>
              {total} result{total !== 1 ? 's' : ''}
              {totalPages > 1 && ` · page ${page + 1} of ${totalPages}`}
            </span>
          </div>

          {loading && <div className="empty-state">Loading facts...</div>}

          {!loading && !error && facts.length === 0 && (
            <div className="empty-state">
              No facts found. Upload and process a document first.
            </div>
          )}

          {!loading && facts.map((fact) => (
            <FactCard key={fact.id} fact={fact} onSelect={setSelectedFact} />
          ))}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="pagination">
              <button
                type="button"
                className="secondary-button"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              >
                ← Previous
              </button>
              <span>{page + 1} / {totalPages}</span>
              <button
                type="button"
                className="secondary-button"
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
              >
                Next →
              </button>
            </div>
          )}
        </div>

        <aside className="fact-selection">
          <h3>Selected fact</h3>

          {selectedFact ? (
            <>
              <div className="selected-fact-title">{selectedFact.attribute}</div>
              <div className="selected-fact-value">
                {String(selectedFact.value)}
                {selectedFact.unit ? ` ${selectedFact.unit}` : ''}
              </div>

              <dl>
                <div><dt>Fact ID</dt><dd>{selectedFact.id}</dd></div>
                <div><dt>Entity</dt><dd>{selectedFact.entity_id}</dd></div>
                <div><dt>Document</dt><dd>{selectedFact.document_id}</dd></div>
                <div>
                  <dt>Confidence</dt>
                  <dd>{Math.round(selectedFact.confidence * 100)}%</dd>
                </div>
              </dl>

              {selectedFact.evidence.length > 0 && (
                <div className="selected-evidence-preview">
                  <h4>Evidence</h4>
                  <p>"{selectedFact.evidence[0].quoted_text}"</p>
                  <span>Page {selectedFact.evidence[0].page_number}</span>
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

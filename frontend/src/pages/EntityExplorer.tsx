import { FormEvent, useEffect, useState } from 'react';

import {
  EntityDetail,
  EntitySummary,
  getEntities,
  getEntity,
} from '../api/client';

const TYPE_COLORS: Record<string, string> = {
  company: '#3b82f6',
  organization: '#8b5cf6',
  person: '#10b981',
  country: '#f59e0b',
  industry: '#ef4444',
  unknown: '#9ca3af',
};

function EntityBadge({ type }: { type: string }) {
  const color = TYPE_COLORS[type.toLowerCase()] ?? TYPE_COLORS.unknown;
  return (
    <span className="entity-type-badge" style={{ background: color + '20', color }}>
      {type}
    </span>
  );
}

function EntityExplorer() {
  const [entities, setEntities] = useState<EntitySummary[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [selectedEntity, setSelectedEntity] = useState<EntityDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const loadEntities = async (searchVal = search, typeVal = typeFilter) => {
    setLoading(true);
    setError('');
    try {
      const result = await getEntities({
        search: searchVal.trim() || undefined,
        entity_type: typeVal || undefined,
        limit: 200,
      });
      setEntities(result.items);
      setTotal(result.total);
    } catch {
      setError('Unable to load entities.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadEntities();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    void loadEntities();
  };

  const handleSelectEntity = async (entity: EntitySummary) => {
    if (selectedEntity?.id === entity.id) {
      setSelectedEntity(null);
      return;
    }
    setDetailLoading(true);
    try {
      const detail = await getEntity(entity.id);
      setSelectedEntity(detail);
    } catch {
      setError('Unable to load entity details.');
    } finally {
      setDetailLoading(false);
    }
  };

  const cleanDocId = (id: string) =>
    id.replace(/^document:[a-f0-9]+_/, '').slice(0, 40);

  return (
    <section className="entity-explorer">
      <div className="page-heading">
        <span className="eyebrow">Knowledge graph</span>
        <h2>Entity Explorer</h2>
        <p>
          Browse all canonical entities extracted from your documents.
          Click any entity to see all facts about it across sources.
        </p>
      </div>

      {/* Filters */}
      <form className="fact-filters" onSubmit={handleSubmit}>
        <div className="filter-field">
          <label htmlFor="entity-search">Search entities</label>
          <input
            id="entity-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="e.g. Delhivery, India..."
          />
        </div>
        <div className="filter-field">
          <label htmlFor="entity-type">Type</label>
          <select
            id="entity-type"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            <option value="">All types</option>
            <option value="company">Company</option>
            <option value="organization">Organization</option>
            <option value="person">Person</option>
            <option value="country">Country</option>
            <option value="industry">Industry</option>
            <option value="unknown">Unknown</option>
          </select>
        </div>
        <div className="filter-actions">
          <button type="submit" disabled={loading}>
            {loading ? 'Loading…' : 'Search'}
          </button>
          <button
            type="button"
            className="secondary-button"
            onClick={() => {
              setSearch('');
              setTypeFilter('');
              setSelectedEntity(null);
              void loadEntities('', '');
            }}
          >
            Clear
          </button>
        </div>
      </form>

      {error && <div className="page-message page-error">{error}</div>}

      <div className="entity-explorer-layout">
        {/* Entity list */}
        <div className="entity-list">
          <div className="results-header">
            <h3>Entities</h3>
            <span>{total} total</span>
          </div>

          {loading && <div className="empty-state">Loading entities…</div>}

          {!loading && entities.length === 0 && (
            <div className="empty-state">No entities found.</div>
          )}

          {!loading && entities.map((entity) => (
            <button
              key={entity.id}
              type="button"
              className={`entity-card ${selectedEntity?.id === entity.id ? 'entity-card--selected' : ''}`}
              onClick={() => handleSelectEntity(entity)}
            >
              <div className="entity-card-header">
                <strong className="entity-name">
                  {entity.canonical_name}
                </strong>
                <EntityBadge type={entity.entity_type} />
              </div>
              <div className="entity-card-meta">
                <span>{entity.fact_count} facts</span>
                <span>{entity.document_ids.length} doc{entity.document_ids.length !== 1 ? 's' : ''}</span>
                {entity.aliases.length > 0 && (
                  <span title={entity.aliases.join(', ')}>
                    +{entity.aliases.length} alias{entity.aliases.length !== 1 ? 'es' : ''}
                  </span>
                )}
              </div>
            </button>
          ))}
        </div>

        {/* Entity detail panel */}
        <aside className="entity-detail">
          {detailLoading && (
            <div className="empty-state">Loading entity details…</div>
          )}

          {!detailLoading && !selectedEntity && (
            <div className="selection-placeholder">
              Select an entity to see all facts about it across documents.
            </div>
          )}

          {!detailLoading && selectedEntity && (
            <>
              <div className="entity-detail-header">
                <h3>{selectedEntity.canonical_name}</h3>
                <EntityBadge type={selectedEntity.entity_type} />
              </div>

              <dl className="entity-detail-meta">
                <div>
                  <dt>Facts</dt>
                  <dd>{selectedEntity.fact_count}</dd>
                </div>
                <div>
                  <dt>Documents</dt>
                  <dd>{selectedEntity.document_ids.length}</dd>
                </div>
                <div>
                  <dt>Confidence</dt>
                  <dd>{Math.round(selectedEntity.confidence * 100)}%</dd>
                </div>
              </dl>

              {selectedEntity.aliases.length > 0 && (
                <div className="entity-aliases">
                  <strong>Also known as:</strong>
                  <div className="entity-alias-list">
                    {selectedEntity.aliases.map((alias) => (
                      <span key={alias} className="entity-alias-tag">
                        {alias}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {selectedEntity.document_ids.length > 0 && (
                <div className="entity-docs">
                  <strong>Appears in:</strong>
                  <ul>
                    {selectedEntity.document_ids.map((docId) => (
                      <li key={docId}>{cleanDocId(docId)}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="entity-attributes">
                <h4>Facts by attribute</h4>
                {Object.entries(selectedEntity.attributes).map(
                  ([attribute, facts]) => (
                    <div key={attribute} className="entity-attribute-group">
                      <div className="entity-attribute-name">
                        {attribute}
                        <span className="entity-attribute-count">
                          {facts.length} value{facts.length !== 1 ? 's' : ''}
                        </span>
                      </div>
                      {facts.map((fact) => (
                        <div key={fact.id} className="entity-fact-row">
                          <span className="entity-fact-value">
                            {String(fact.value)}
                            {fact.unit ? ` ${fact.unit}` : ''}
                          </span>
                          <span className="entity-fact-confidence">
                            {Math.round(fact.confidence * 100)}%
                          </span>
                          <span className="entity-fact-doc">
                            {cleanDocId(fact.document_id)}
                          </span>
                          {fact.temporal_scope && (
                            <span className="entity-fact-period">
                              {(fact.temporal_scope as Record<string, unknown>).period_label as string ?? ''}
                            </span>
                          )}
                          {fact.needs_review && (
                            <span className="entity-fact-review">⚠️</span>
                          )}
                        </div>
                      ))}
                    </div>
                  ),
                )}
              </div>
            </>
          )}
        </aside>
      </div>
    </section>
  );
}

export default EntityExplorer;

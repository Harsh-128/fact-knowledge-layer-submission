import { useCallback, useEffect, useState } from 'react';

import { Fact, getFacts, reviewFact } from '../api/client';

type ReviewState = 'pending' | 'accepted' | 'rejected';

interface ReviewedFact {
  fact: Fact;
  state: ReviewState;
}

function ReviewQueue() {
  const [items, setItems] = useState<ReviewedFact[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState<string | null>(null); // fact_id being saved

  const loadReviewFacts = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = await getFacts({ needs_review: true, limit: 200 });
      setItems(result.map((fact) => ({ fact, state: 'pending' })));
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to load facts for review.',
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadReviewFacts();
  }, [loadReviewFacts]);

  const handleDecision = async (factId: string, accept: boolean) => {
    setSaving(factId);
    try {
      await reviewFact(factId, accept);
      setItems((prev) =>
        prev.map((item) =>
          item.fact.id === factId
            ? { ...item, state: accept ? 'accepted' : 'rejected' }
            : item,
        ),
      );
    } catch {
      setError(`Failed to save decision for fact ${factId}.`);
    } finally {
      setSaving(null);
    }
  };

  const pending = items.filter((i) => i.state === 'pending').length;
  const accepted = items.filter((i) => i.state === 'accepted').length;
  const rejected = items.filter((i) => i.state === 'rejected').length;

  return (
    <section className="review-queue">
      <div className="page-heading">
        <span className="eyebrow">Human-in-the-loop</span>
        <h2>Review Queue</h2>
        <p>
          Facts the system flagged as uncertain. Accept the ones that
          look correct, reject the ones that don't.
        </p>
      </div>

      {/* Summary */}
      <div className="review-summary">
        <div>
          <strong>{items.length}</strong>
          <span>Total flagged</span>
        </div>
        <div className="review-summary--pending">
          <strong>{pending}</strong>
          <span>Pending</span>
        </div>
        <div className="review-summary--accepted">
          <strong>{accepted}</strong>
          <span>Accepted</span>
        </div>
        <div className="review-summary--rejected">
          <strong>{rejected}</strong>
          <span>Rejected</span>
        </div>
      </div>

      {error && <div className="page-message page-error">{error}</div>}

      {loading ? (
        <div className="empty-state">Loading review queue…</div>
      ) : items.length === 0 ? (
        <div className="empty-state">
          🎉 No facts need review right now.
        </div>
      ) : (
        <div className="review-list">
          {items.map(({ fact, state }) => (
            <article
              key={fact.id}
              className={`review-card review-card--${state}`}
            >
              {/* State ribbon */}
              {state !== 'pending' && (
                <div className={`review-ribbon review-ribbon--${state}`}>
                  {state === 'accepted' ? '✅ Accepted' : '❌ Rejected'}
                </div>
              )}

              <div className="review-card-body">
                {/* Fact identity */}
                <div className="review-fact-header">
                  <span className="review-fact-attribute">
                    {fact.attribute}
                  </span>
                  <span className="review-fact-value">
                    {String(fact.value)}
                    {fact.unit ? ` ${fact.unit}` : ''}
                  </span>
                </div>

                {/* Metadata row */}
                <div className="review-fact-meta">
                  <span>Entity: {fact.entity_id}</span>
                  <span>Doc: {fact.document_id.slice(0, 24)}…</span>
                  <span>
                    Confidence: {Math.round(fact.confidence * 100)}%
                  </span>
                  {fact.temporal_scope && (
                    <span>
                      Period:{' '}
                      {(fact.temporal_scope as Record<string, unknown>).period_label as string ?? '—'}
                    </span>
                  )}
                </div>

                {/* Evidence */}
                {fact.evidence.length > 0 && (
                  <blockquote className="review-evidence">
                    <p>"{fact.evidence[0].quoted_text}"</p>
                    <footer>Page {fact.evidence[0].page_number}</footer>
                  </blockquote>
                )}
              </div>

              {/* Action buttons */}
              {state === 'pending' && (
                <div className="review-actions">
                  <button
                    type="button"
                    className="review-btn review-btn--accept"
                    disabled={saving === fact.id}
                    onClick={() => handleDecision(fact.id, true)}
                  >
                    {saving === fact.id ? '…' : '✅ Accept'}
                  </button>
                  <button
                    type="button"
                    className="review-btn review-btn--reject"
                    disabled={saving === fact.id}
                    onClick={() => handleDecision(fact.id, false)}
                  >
                    {saving === fact.id ? '…' : '❌ Reject'}
                  </button>
                </div>
              )}

              {state !== 'pending' && (
                <div className="review-actions">
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() =>
                      setItems((prev) =>
                        prev.map((item) =>
                          item.fact.id === fact.id
                            ? { ...item, state: 'pending' }
                            : item,
                        )
                      )
                    }
                  >
                    Undo
                  </button>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export default ReviewQueue;

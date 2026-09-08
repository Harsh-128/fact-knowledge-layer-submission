import type { EvidenceRef } from '../api/client';

interface EvidenceHighlighterProps {
  evidence: EvidenceRef[];
}

function EvidenceHighlighter({
  evidence,
}: EvidenceHighlighterProps) {
  if (evidence.length === 0) {
    return (
      <div className="evidence-empty">
        No source evidence is available for this fact.
      </div>
    );
  }

  return (
    <section className="evidence-section">
      <div className="evidence-section-header">
        <h3>Source Evidence</h3>
        <span>{evidence.length} reference{evidence.length !== 1 ? 's' : ''}</span>
      </div>

      <div className="evidence-list">
        {evidence.map((item, index) => (
          <article
            className="evidence-item"
            key={`${item.document_id}-${item.page_number}-${item.chunk_id ?? index}`}
          >
            <div className="evidence-meta">
              <span className="evidence-page">
                Page {item.page_number}
              </span>

              {item.chunk_id && (
                <span className="evidence-chunk">
                  Chunk {item.chunk_id}
                </span>
              )}
            </div>

            <blockquote className="evidence-quote">
              {item.quoted_text}
            </blockquote>

            {(item.char_start !== null &&
              item.char_start !== undefined &&
              item.char_end !== null &&
              item.char_end !== undefined) && (
              <div className="evidence-offsets">
                Characters {item.char_start}–{item.char_end}
              </div>
            )}

            <div className="evidence-document">
              Document: {item.document_id}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export default EvidenceHighlighter;

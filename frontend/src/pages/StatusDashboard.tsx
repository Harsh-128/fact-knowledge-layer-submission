import { useCallback, useEffect, useRef, useState } from 'react';

import {
  Document,
  DocumentStatus,
  getDocumentStatus,
  getDocuments,
} from '../api/client';

// Poll every 3 seconds for documents that are still processing.
const POLL_INTERVAL_MS = 3000;

const STATUS_LABELS: Record<string, string> = {
  uploaded: '⏳ Uploaded',
  processing: '⚙️ Processing',
  processed: '✅ Processed',
  failed: '❌ Failed',
};

const STATUS_COLORS: Record<string, string> = {
  uploaded: '#f59e0b',
  processing: '#3b82f6',
  processed: '#10b981',
  failed: '#ef4444',
};

function ProgressBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="progress-bar-track">
      <div
        className="progress-bar-fill"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function DocumentCard({
  doc,
  statusData,
}: {
  doc: Document;
  statusData: DocumentStatus | null;
}) {
  const statusKey = statusData?.status ?? doc.status;
  const label = STATUS_LABELS[statusKey] ?? statusKey;
  const color = STATUS_COLORS[statusKey] ?? '#6b7280';
  const filename = doc.filename.replace(/^document:[a-f0-9]+_/, '');

  const createdAt = new Date(doc.created_at).toLocaleString();
  const processedAt = statusData?.processed_at
    ? new Date(statusData.processed_at).toLocaleString()
    : null;

  return (
    <div className={`status-card status-card--${statusKey}`}>
      <div className="status-card-header">
        <div className="status-card-name">
          <span className="status-badge" style={{ color }}>
            {label}
          </span>
          <strong title={filename}>{filename}</strong>
        </div>
        <span className="status-card-date">{createdAt}</span>
      </div>

      {statusData && (
        <>
          <div className="status-card-counts">
            <div className="status-count">
              <span>{statusData.page_count ?? '—'}</span>
              <label>Pages</label>
            </div>
            <div className="status-count">
              <span>{statusData.chunk_count}</span>
              <label>Chunks</label>
            </div>
            <div className="status-count">
              <span>{statusData.fact_count}</span>
              <label>Facts</label>
            </div>
            <div className={`status-count ${statusData.needs_review_count > 0 ? 'status-count--warn' : ''}`}>
              <span>{statusData.needs_review_count}</span>
              <label>Need review</label>
            </div>
          </div>

          {statusKey === 'processing' && statusData.chunk_count > 0 && (
            <div className="status-progress">
              <span className="status-progress-label">
                Extracting facts… {statusData.fact_count} found so far
              </span>
              <ProgressBar
                value={statusData.fact_count}
                max={Math.max(statusData.chunk_count * 3, statusData.fact_count)}
              />
            </div>
          )}

          {statusKey === 'processed' && processedAt && (
            <div className="status-processed-at">
              Completed: {processedAt}
            </div>
          )}

          {statusKey === 'failed' && statusData.error_message && (
            <div className="status-error">
              {statusData.error_message}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function StatusDashboard() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [statusMap, setStatusMap] = useState<Record<string, DocumentStatus>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadDocuments = useCallback(async () => {
    try {
      const docs = await getDocuments({ limit: 100 });
      setDocuments(docs);
      return docs;
    } catch {
      setError('Unable to load documents.');
      return [];
    }
  }, []);

  const refreshStatuses = useCallback(async (docs: Document[]) => {
    const results = await Promise.allSettled(
      docs.map((d) => getDocumentStatus(d.id)),
    );
    const newMap: Record<string, DocumentStatus> = {};
    results.forEach((r, i) => {
      if (r.status === 'fulfilled') {
        newMap[docs[i].id] = r.value;
      }
    });
    setStatusMap(newMap);
    return newMap;
  }, []);

  // Initial load
  useEffect(() => {
    setLoading(true);
    loadDocuments()
      .then((docs) => refreshStatuses(docs))
      .finally(() => setLoading(false));
  }, [loadDocuments, refreshStatuses]);

  // Polling — only when some docs are still processing
  useEffect(() => {
    const tick = async () => {
      const docs = await loadDocuments();
      const map = await refreshStatuses(docs);
      const stillProcessing = docs.some(
        (d) => (map[d.id]?.status ?? d.status) === 'processing' ||
               (map[d.id]?.status ?? d.status) === 'uploaded',
      );
      if (!stillProcessing && pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };

    pollRef.current = setInterval(tick, POLL_INTERVAL_MS);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [loadDocuments, refreshStatuses]);

  const totalFacts = Object.values(statusMap).reduce(
    (sum, s) => sum + s.fact_count,
    0,
  );
  const totalReview = Object.values(statusMap).reduce(
    (sum, s) => sum + s.needs_review_count,
    0,
  );
  const processing = documents.filter(
    (d) => (statusMap[d.id]?.status ?? d.status) === 'processing' ||
            (statusMap[d.id]?.status ?? d.status) === 'uploaded',
  ).length;

  return (
    <section className="status-dashboard">
      <div className="page-heading">
        <span className="eyebrow">Processing pipeline</span>
        <h2>Status Dashboard</h2>
        <p>
          Live view of every document — from upload through fact
          extraction to completion.
          {processing > 0 && (
            <span className="status-live-badge"> ● Live</span>
          )}
        </p>
      </div>

      {/* Summary bar */}
      <div className="status-summary">
        <div>
          <strong>{documents.length}</strong>
          <span>Documents</span>
        </div>
        <div>
          <strong>{totalFacts}</strong>
          <span>Total facts</span>
        </div>
        <div className={totalReview > 0 ? 'status-summary--warn' : ''}>
          <strong>{totalReview}</strong>
          <span>Need review</span>
        </div>
        <div>
          <strong style={{ color: processing > 0 ? '#3b82f6' : '#10b981' }}>
            {processing > 0 ? `${processing} processing` : 'All done'}
          </strong>
          <span>Pipeline status</span>
        </div>
      </div>

      {error && <div className="page-message page-error">{error}</div>}

      {loading ? (
        <div className="empty-state">Loading documents…</div>
      ) : documents.length === 0 ? (
        <div className="empty-state">
          No documents yet. Upload a PDF to get started.
        </div>
      ) : (
        <div className="status-card-grid">
          {documents.map((doc) => (
            <DocumentCard
              key={doc.id}
              doc={doc}
              statusData={statusMap[doc.id] ?? null}
            />
          ))}
        </div>
      )}
    </section>
  );
}

export default StatusDashboard;

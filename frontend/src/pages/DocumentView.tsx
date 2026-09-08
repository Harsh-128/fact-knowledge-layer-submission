import { useEffect, useState } from 'react';

import {
  Document,
  Fact,
  getDocuments,
  getFacts,
} from '../api/client';
import FactCard from '../components/FactCard';
import EvidenceHighlighter from '../components/EvidenceHighlighter';

interface DocumentViewProps {
  documentId?: string;
  onDocumentSelect: (id: string) => void;
}

function DocumentView({
  documentId = '',
  onDocumentSelect,
}: DocumentViewProps) {
  const [facts, setFacts] = useState<Fact[]>([]);
  const [selectedFact, setSelectedFact] = useState<Fact | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [documents, setDocuments] = useState<Document[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);

  useEffect(() => {
  if (documentId) {
    return;
  }

  const loadDocuments = async () => {
    setDocumentsLoading(true);
    setError('');

    try {
      const result = await getDocuments({
        limit: 100,
        offset: 0,
      });

      setDocuments(result);
    } catch (loadError) {
      if (loadError instanceof Error && loadError.message) {
        setError(loadError.message);
      } else {
        setError('Unable to load documents.');
      }
    } finally {
      setDocumentsLoading(false);
    }
  };

  void loadDocuments();
}, [documentId]);

  useEffect(() => {
    if (!documentId) {
      setFacts([]);
      setSelectedFact(null);
      return;
    }

    const loadDocumentFacts = async () => {
      setLoading(true);
      setError('');

      try {
        const result = await getFacts({
          document_id: documentId,
          limit: 100,
          offset: 0,
        });

        setFacts(result);
        setSelectedFact(result[0] ?? null);
      } catch (loadError) {
        setFacts([]);
        setSelectedFact(null);

        if (loadError instanceof Error && loadError.message) {
          setError(loadError.message);
        } else {
          setError('Unable to load document facts.');
        }
      } finally {
        setLoading(false);
      }
    };

    void loadDocumentFacts();
  }, [documentId]);

  if (!documentId) {
  return (
    <section className="document-view">
      <div className="page-heading">
        <span className="eyebrow">Document analysis</span>

        <h2>Document View</h2>

        <p>
          Select a processed document to inspect its extracted
          facts and source evidence.
        </p>
      </div>

      {error && (
        <div className="page-message page-error">
          {error}
        </div>
      )}

      {documentsLoading ? (
        <div className="empty-state">
          Loading documents...
        </div>
      ) : documents.length === 0 ? (
        <div className="empty-state">
          No documents available.
        </div>
      ) : (
        <div className="document-selector">
          <h3>Processed Documents</h3>

          {documents.map((document) => (
            <button
              key={document.id}
              type="button"
              className="document-selector-item"
              onClick={() => onDocumentSelect(document.id)}
            >
              <strong>{document.filename}</strong>

              <span>
                {document.status} · {document.page_count ?? 0} pages
              </span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

  return (
    <section className="document-view">
      <div className="page-heading">
        <span className="eyebrow">Document analysis</span>

        <h2>Document View</h2>

        <p>
          Inspect facts extracted from this source document and
          trace each claim back to its evidence.
        </p>

        <div className="document-id">
          Document: <strong>{documentId}</strong>
        </div>
      </div>

      {error && (
        <div className="page-message page-error">
          {error}
        </div>
      )}

      {loading && (
        <div className="empty-state">
          Loading document facts...
        </div>
      )}

      {!loading && !error && facts.length === 0 && (
        <div className="empty-state">
          No facts have been extracted from this document yet.
        </div>
      )}

      {!loading && facts.length > 0 && (
        <div className="document-layout">
          <div className="document-facts">
            <div className="results-header">
              <h3>Extracted Facts</h3>
              <span>{facts.length}</span>
            </div>

            {facts.map((fact) => (
              <FactCard
                key={fact.id}
                fact={fact}
                onSelect={setSelectedFact}
              />
            ))}
          </div>

          <aside className="document-evidence">
            <h3>Evidence</h3>

            {selectedFact ? (
              <>
                <div className="selected-fact-summary">
                  <span>Selected fact</span>
                  <strong>{selectedFact.attribute}</strong>
                </div>

                <EvidenceHighlighter
                  evidence={selectedFact.evidence}
                />
              </>
            ) : (
              <p className="selection-placeholder">
                Select a fact to view its source evidence.
              </p>
            )}
          </aside>
        </div>
      )}
    </section>
  );
}

export default DocumentView;

import { useState } from 'react';

import DocumentView from './pages/DocumentView';
import FactExplorer from './pages/FactExplorer';
import RelationshipGraph from './pages/RelationshipGraph';
import UploadPage from './pages/UploadPage';
import ComparePage from './pages/ComparePage';
import StatusDashboard from './pages/StatusDashboard';
import ReviewQueue from './pages/ReviewQueue';
import EntityExplorer from './pages/EntityExplorer';

import './App.css';

type Page =
  | 'upload'
  | 'facts'
  | 'document'
  | 'relationships'
  | 'compare'
  | 'status'
  | 'review'
  | 'entities';

const navigation: { id: Page; label: string }[] = [
  { id: 'upload', label: 'Upload' },
  { id: 'status', label: '📊 Status' },
  { id: 'facts', label: 'Fact Explorer' },
  { id: 'entities', label: '🏢 Entities' },
  { id: 'review', label: '🔍 Review' },
  { id: 'document', label: 'Document View' },
  { id: 'relationships', label: 'Relationships' },
  { id: 'compare', label: 'Compare' },
];

function App() {
  const [activePage, setActivePage] =
    useState<Page>('upload');

  const [documentId, setDocumentId] = useState('');
  const [documentFilename, setDocumentFilename] = useState('');

  const handleDocumentUploaded = (id: string, filename?: string) => {
    setDocumentId(id);
    if (filename) setDocumentFilename(filename);
  };

  const handleDocumentSelect = (id: string, filename?: string) => {
    setDocumentId(id);
    if (filename) setDocumentFilename(filename);
    // Empty string means "go back to document list"
    if (id === '') {
      setDocumentFilename('');
    }
    setActivePage('document');
  };

  const renderPage = () => {
    switch (activePage) {
      case 'upload':
        return (
          <UploadPage
            onDocumentUploaded={handleDocumentUploaded}
          />
        );

      case 'facts':
        return <FactExplorer />;

      case 'document':
        return (
          <DocumentView
            documentId={documentId}
            documentFilename={documentFilename}
            onDocumentSelect={handleDocumentSelect}
          />
        );

      case 'relationships':
        return <RelationshipGraph />;

      case 'compare':
        return <ComparePage />;

      case 'status':
        return <StatusDashboard />;

      case 'review':
        return <ReviewQueue />;

      case 'entities':
        return <EntityExplorer />;

      default:
        return <UploadPage />;
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">
          <h1>Fact Knowledge Layer</h1>
          <p>
            Grounded fact extraction and cross-document reasoning
          </p>
        </div>

        <nav className="app-navigation">
          {navigation.map((item) => (
            <button
              key={item.id}
              type="button"
              className={
                activePage === item.id
                  ? 'nav-button active'
                  : 'nav-button'
              }
              onClick={() => setActivePage(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="app-main">
        {renderPage()}
      </main>
    </div>
  );
}

export default App;

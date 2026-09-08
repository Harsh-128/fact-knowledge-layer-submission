import { useState } from 'react';

import DocumentView from './pages/DocumentView';
import FactExplorer from './pages/FactExplorer';
import RelationshipGraph from './pages/RelationshipGraph';
import UploadPage from './pages/UploadPage';

import './App.css';

type Page =
  | 'upload'
  | 'facts'
  | 'document'
  | 'relationships';

const navigation: { id: Page; label: string }[] = [
  { id: 'upload', label: 'Upload' },
  { id: 'facts', label: 'Fact Explorer' },
  { id: 'document', label: 'Document View' },
  { id: 'relationships', label: 'Relationships' },
];

function App() {
  const [activePage, setActivePage] =
    useState<Page>('upload');

  const [documentId, setDocumentId] = useState('');

  const handleDocumentSelect = (id: string) => {
    setDocumentId(id);
    setActivePage('document');
  };

  const renderPage = () => {
    switch (activePage) {
      case 'upload':
        return (
          <UploadPage
            onDocumentUploaded={handleDocumentSelect}
          />
        );

      case 'facts':
        return <FactExplorer />;

      case 'document':
        return (
          <DocumentView
            documentId={documentId}
            onDocumentSelect={handleDocumentSelect}
          />
        );

      case 'relationships':
        return <RelationshipGraph />;

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

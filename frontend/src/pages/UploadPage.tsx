import {
  ChangeEvent,
  FormEvent,
  useEffect,
  useState,
} from 'react';

import {
  DocumentUploadResponse,
  getJobStatus,
  uploadDocument,
} from '../api/client';

interface UploadPageProps {
  onDocumentUploaded?: (documentId: string) => void;
}

function UploadPage({
  onDocumentUploaded,
}: UploadPageProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] =
    useState<DocumentUploadResponse | null>(null);
  const [error, setError] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [jobStatus, setJobStatus] = useState<string | null>(null);

  const handleFileChange = (
    
    event: ChangeEvent<HTMLInputElement>,
  ) => {
    const file = event.target.files?.[0] ?? null;

    setError('');
    setUploadResult(null);
    setJobStatus(null);

    if (!file) {
      setSelectedFile(null);
      return;
    }

    const isPdf =
      file.type === 'application/pdf' ||
      file.name.toLowerCase().endsWith('.pdf');

    if (!isPdf) {
      setSelectedFile(null);
      setError('Please select a PDF file.');
      return;
    }

    setSelectedFile(file);
  };
    useEffect(() => {
    if (!uploadResult?.task_id) {
      return;
    }

    let cancelled = false;

    const pollJobStatus = async () => {
      try {
        const result = await getJobStatus(
          uploadResult.task_id,
        );

        if (cancelled) {
          return;
        }

        setJobStatus(result.status);

        const status = result.status.toUpperCase();

        if (
          status === 'SUCCESS' ||
          status === 'COMPLETED'
        ) {
          const documentId =
            result.result?.document_id ?? uploadResult.document_id;

          onDocumentUploaded?.(documentId);
          return;
        }

        if (
          status === 'FAILURE' ||
          status === 'REVOKED'
        ) {
          setError(
            result.error ??
              'Document processing failed.',
          );
          return;
        }

        window.setTimeout(
          pollJobStatus,
          2000,
        );
      } catch (pollError) {
        if (cancelled) {
          return;
        }

        if (
          pollError instanceof Error &&
          pollError.message
        ) {
          setError(
            `Unable to check processing status: ${pollError.message}`,
          );
        } else {
          setError(
            'Unable to check document processing status.',
          );
        }
      }
    };

    void pollJobStatus();

    return () => {
      cancelled = true;
    };
  }, [uploadResult, onDocumentUploaded]);

  const handleSubmit = async (
    event: FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();

    if (!selectedFile) {
      setError('Please select a PDF file first.');
      return;
    }

    setError('');
    setUploadResult(null);
    setJobStatus(null);
    setIsUploading(true);

    try {
      const result = await uploadDocument(selectedFile);
      setUploadResult(result);
      setJobStatus('QUEUED');
    } catch (uploadError) {
      if (
        uploadError instanceof Error &&
        uploadError.message
      ) {
        setError(uploadError.message);
      } else {
        setError(
          'Upload failed. Make sure the FastAPI backend is running.',
        );
      }
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <section className="upload-page">
      <div className="page-heading">
        <span className="eyebrow">Document ingestion</span>
        <h2>Upload a PDF</h2>
        <p>
          Upload a source document and send it to the Fact
          Knowledge Layer for processing.
        </p>
      </div>

      <form className="upload-form" onSubmit={handleSubmit}>
        <label className="file-dropzone">
          <span className="file-dropzone-title">
            Choose a PDF document
          </span>

          <span className="file-dropzone-description">
            PDF files only
          </span>

          <input
            type="file"
            accept="application/pdf,.pdf"
            onChange={handleFileChange}
          />
        </label>

        {selectedFile && (
          <div className="selected-file">
            <strong>{selectedFile.name}</strong>
            <span>
              {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
            </span>
          </div>
        )}

        {error && (
          <div className="upload-message upload-error">
            {error}
          </div>
        )}

        {uploadResult && (
          <div className="upload-message upload-success">
            <strong>Document queued successfully.</strong>

            <div>
              Document ID: {uploadResult.document_id}
            </div>

            <div>
              Task ID: {uploadResult.task_id}
            </div>

            <div>
              Status: {uploadResult.status}
            </div>
          </div>
        )}

        <button
          className="upload-button"
          type="submit"
          disabled={!selectedFile || isUploading}
        >
          {isUploading ? 'Uploading...' : 'Upload document'}
        </button>
      </form>
    </section>
  );
}

export default UploadPage;

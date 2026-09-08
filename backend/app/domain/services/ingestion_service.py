from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.exceptions import (
    DocumentProcessingError,
    UnsupportedDocumentError,
)
from app.domain.models.chunk import Chunk
from app.domain.models.document import Document, DocumentStatus
from app.infra.pdf.chunker import PDFChunker
from app.infra.pdf.parser import ParsedDocument, PDFParser
from app.infra.storage.blob_storage import BlobStorage


@dataclass(slots=True)
class IngestionResult:
    """Result produced after successfully ingesting a document."""

    document: Document
    parsed_document: ParsedDocument
    chunks: list[Chunk]
    storage_path: str


class IngestionService:
    """
    Coordinate document storage, PDF parsing, and chunking.

    This service deliberately does not perform fact extraction. Extraction
    is a separate pipeline stage so large documents can be processed
    incrementally.
    """

    SUPPORTED_CONTENT_TYPES = {
        "application/pdf",
    }

    def __init__(
        self,
        storage: BlobStorage | None = None,
        parser: PDFParser | None = None,
        chunker: PDFChunker | None = None,
    ) -> None:
        self.storage = storage or BlobStorage()
        self.parser = parser or PDFParser()
        self.chunker = chunker or PDFChunker()

    def ingest(
        self,
        *,
        content: bytes,
        filename: str,
        content_type: str = "application/pdf",
        document_id: str | None = None,
    ) -> IngestionResult:
        """
        Store and process a PDF document.

        Raises:
            UnsupportedDocumentError:
                When the uploaded content type is not supported.
            DocumentProcessingError:
                When storage, parsing, or chunking fails.
        """

        self._validate_upload(
            content=content,
            filename=filename,
            content_type=content_type,
        )

        document = Document(
            id=document_id or f"document:{self.storage.sha256(content)}",
            filename=filename,
            content_type=content_type,
            file_size_bytes=len(content),
            sha256=self.storage.sha256(content),
        )

        storage_path = ""

        try:
            document.mark_processing()

            storage_path = self.storage.save(
                content=content,
                filename=filename,
                object_id=document.id,
            )

            parsed_document = self._parse_stored_document(
                storage_path
            )

            chunks = self.chunker.chunk_document(
                parsed_document=parsed_document,
                document=document,
            )

            document.mark_processed(
                page_count=parsed_document.page_count
            )

            return IngestionResult(
                document=document,
                parsed_document=parsed_document,
                chunks=chunks,
                storage_path=storage_path,
            )

        except Exception as exc:
            document.mark_failed(str(exc))

            if isinstance(exc, DocumentProcessingError):
                raise

            raise DocumentProcessingError(
                f"Document ingestion failed: {exc}"
            ) from exc

    def ingest_file(
        self,
        file_path: str | Path,
        *,
        content_type: str = "application/pdf",
        document_id: str | None = None,
    ) -> IngestionResult:
        """
        Ingest a PDF directly from an existing local path.

        This is useful for CLI processing and development.
        """

        path = Path(file_path)

        if not path.exists():
            raise DocumentProcessingError(
                f"Input file does not exist: {path}"
            )

        if not path.is_file():
            raise DocumentProcessingError(
                f"Input path is not a file: {path}"
            )

        try:
            content = path.read_bytes()
        except OSError as exc:
            raise DocumentProcessingError(
                f"Unable to read input file: {exc}"
            ) from exc

        return self.ingest(
            content=content,
            filename=path.name,
            content_type=content_type,
            document_id=document_id,
        )

    def _parse_stored_document(
        self,
        storage_path: str,
    ) -> ParsedDocument:
        """Parse a document after it has been safely stored."""

        return self.parser.parse(storage_path)

    @classmethod
    def _validate_upload(
        cls,
        *,
        content: bytes,
        filename: str,
        content_type: str,
    ) -> None:
        """Validate basic upload requirements."""

        if not content:
            raise DocumentProcessingError(
                "Uploaded document is empty."
            )

        if not filename.strip():
            raise DocumentProcessingError(
                "Uploaded document must have a filename."
            )

        normalized_content_type = content_type.strip().lower()

        if normalized_content_type not in cls.SUPPORTED_CONTENT_TYPES:
            raise UnsupportedDocumentError(
                f"Unsupported document type: {content_type}. "
                f"Supported types: {sorted(cls.SUPPORTED_CONTENT_TYPES)}"
            )

        if Path(filename).suffix.lower() != ".pdf":
            raise UnsupportedDocumentError(
                f"Unsupported file extension: {filename}. "
                "Only PDF files are supported."
            )

    def delete_stored_document(
        self,
        storage_path: str,
    ) -> None:
        """Delete a document from blob storage."""

        self.storage.delete(storage_path)


def get_ingestion_service(
    storage: BlobStorage | None = None,
    parser: PDFParser | None = None,
    chunker: PDFChunker | None = None,
) -> IngestionService:
    """Create an ingestion service."""

    return IngestionService(
        storage=storage,
        parser=parser,
        chunker=chunker,
    )

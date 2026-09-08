from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class DocumentStatus(StrEnum):
    """Processing state of an uploaded document."""

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class Document(BaseModel):
    """
    Domain representation of an uploaded source document.

    This model intentionally contains document-level metadata only.
    PDF pages and extracted chunks are represented separately.
    """

    id: str = Field(
        ...,
        description="Unique identifier for the document.",
    )

    filename: str = Field(
        ...,
        min_length=1,
        description="Original uploaded filename.",
    )

    content_type: str = Field(
        default="application/pdf",
        description="MIME type of the uploaded document.",
    )

    file_size_bytes: int = Field(
        default=0,
        ge=0,
        description="Size of the uploaded document in bytes.",
    )

    sha256: str | None = Field(
        default=None,
        description="SHA-256 checksum used for document identity and deduplication.",
    )

    page_count: int | None = Field(
        default=None,
        ge=1,
        description="Number of pages detected in the PDF.",
    )

    status: DocumentStatus = Field(
        default=DocumentStatus.UPLOADED,
        description="Current document processing status.",
    )

    error_message: str | None = Field(
        default=None,
        description="Processing error when status is FAILED.",
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when the document record was created.",
    )

    processed_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when document processing completed.",
    )

    def mark_processing(self) -> None:
        """Mark the document as currently being processed."""
        self.status = DocumentStatus.PROCESSING
        self.error_message = None

    def mark_processed(self, page_count: int) -> None:
        """Mark the document as successfully processed."""
        if page_count < 1:
            raise ValueError("page_count must be at least 1")

        self.status = DocumentStatus.PROCESSED
        self.page_count = page_count
        self.processed_at = datetime.utcnow()
        self.error_message = None

    def mark_failed(self, error_message: str) -> None:
        """Mark the document as failed and retain the reason."""
        self.status = DocumentStatus.FAILED
        self.error_message = error_message

    @property
    def is_processed(self) -> bool:
        """Return whether the document has completed processing."""
        return self.status == DocumentStatus.PROCESSED
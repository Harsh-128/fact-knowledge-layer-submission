from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models.document import Document, DocumentStatus
from app.infra.db.models_orm import DocumentORM


class DocumentRepository:
    """Persistence operations for documents."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, document: Document) -> Document:
        """Persist a new document."""

        existing = self.get_by_id(document.id)

        if existing is not None:
            return existing

        orm_document = DocumentORM(
            id=document.id,
            filename=document.filename,
            content_type=document.content_type,
            file_size_bytes=document.file_size_bytes,
            sha256=document.sha256,
            page_count=document.page_count,
            status=document.status.value,
            error_message=document.error_message,
            created_at=document.created_at,
            processed_at=document.processed_at,
        )

        self.db.add(orm_document)
        self.db.flush()

        return self._to_domain(orm_document)

    def get_by_id(
        self,
        document_id: str,
    ) -> Document | None:
        """Find a document by its ID."""

        orm_document = self.db.get(
            DocumentORM,
            document_id,
        )

        if orm_document is None:
            return None

        return self._to_domain(orm_document)

    def get_orm_by_id(
        self,
        document_id: str,
    ) -> DocumentORM | None:
        """Find the ORM document when database-level access is required."""

        return self.db.get(
            DocumentORM,
            document_id,
        )

    def get_by_sha256(
        self,
        sha256: str,
    ) -> Document | None:
        """Find an existing document with the same content checksum."""

        statement = (
            select(DocumentORM)
            .where(DocumentORM.sha256 == sha256)
            .limit(1)
        )

        orm_document = self.db.execute(
            statement
        ).scalar_one_or_none()

        if orm_document is None:
            return None

        return self._to_domain(orm_document)

    def update_status(
        self,
        document_id: str,
        status: DocumentStatus,
        *,
        page_count: int | None = None,
        error_message: str | None = None,
        processed_at: datetime | None = None,
    ) -> Document | None:
        """Update the processing status of a document."""

        orm_document = self.get_orm_by_id(document_id)

        if orm_document is None:
            return None

        orm_document.status = status.value

        if page_count is not None:
            orm_document.page_count = page_count

        if error_message is not None:
            orm_document.error_message = error_message

        if processed_at is not None:
            orm_document.processed_at = processed_at

        self.db.add(orm_document)
        self.db.flush()

        return self._to_domain(orm_document)

    def list_documents(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Document]:
        """Return documents ordered from newest to oldest."""

        if limit < 1:
            raise ValueError("limit must be at least 1.")

        if offset < 0:
            raise ValueError("offset cannot be negative.")

        statement = (
            select(DocumentORM)
            .order_by(DocumentORM.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        documents = self.db.execute(
            statement
        ).scalars().all()

        return [
            self._to_domain(document)
            for document in documents
        ]

    def delete(
        self,
        document_id: str,
    ) -> bool:
        """Delete a document by ID."""

        orm_document = self.get_orm_by_id(document_id)

        if orm_document is None:
            return False

        self.db.delete(orm_document)
        self.db.flush()

        return True

    @staticmethod
    def _to_domain(
        orm_document: DocumentORM,
    ) -> Document:
        """Convert a database model into the domain model."""

        return Document(
            id=orm_document.id,
            filename=orm_document.filename,
            content_type=orm_document.content_type,
            file_size_bytes=orm_document.file_size_bytes,
            sha256=orm_document.sha256,
            page_count=orm_document.page_count,
            status=DocumentStatus(orm_document.status),
            error_message=orm_document.error_message,
            created_at=orm_document.created_at,
            processed_at=orm_document.processed_at,
        )

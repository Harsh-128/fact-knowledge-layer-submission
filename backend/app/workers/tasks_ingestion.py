from __future__ import annotations

import hashlib
from pathlib import Path

from app.core.logging import get_logger
from app.core.exceptions import UnsupportedDocumentError
from app.domain.services.ingestion_service import IngestionService
from app.infra.db.repositories.chunk_repo import ChunkRepository
from app.infra.db.repositories.document_repo import DocumentRepository
from app.infra.db.session import SessionLocal
from app.workers.celery_app import celery_app
from app.workers.tasks_extraction import extract_facts_task


logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    name="documents.ingest",
    # M-3: Only retry on transient I/O and connection errors.
    # Permanent failures (corrupt PDF, wrong file type) must not be retried.
    autoretry_for=(ConnectionError, TimeoutError, OSError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def ingest_document_task(
    self,
    file_path: str,
    document_id: str | None = None,
) -> dict:
    """
    Process a PDF asynchronously and persist its document/chunks.

    Duplicate PDFs are detected using SHA-256 before creating a new
    document record.
    """

    db = SessionLocal()
    temporary_path = Path(file_path)

    try:
        logger.info(
            "Starting document ingestion: file=%s document_id=%s",
            file_path,
            document_id,
        )

        if not temporary_path.exists():
            raise FileNotFoundError(
                f"Uploaded file no longer exists: {file_path}"
            )

        document_repository = DocumentRepository(db)
        chunk_repository = ChunkRepository(db)

        # M-1: Removed dead hasattr(_calculate_sha256) branch.
        # Always use the inline hashlib implementation.
        digest = hashlib.sha256()
        with temporary_path.open("rb") as file:
            for block in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(block)
        file_sha256 = digest.hexdigest()

        # Reuse an already-ingested document instead of violating the
        # documents.sha256 unique constraint.
        existing_document = document_repository.get_by_sha256(
            file_sha256
        )

        if existing_document is not None:
            existing_chunks = chunk_repository.get_by_document(
                existing_document.id
            )

            logger.info(
                "Duplicate document detected: sha256=%s existing_document_id=%s",
                file_sha256,
                existing_document.id,
            )

            extract_facts_task.delay(existing_document.id)

            # The temporary upload is no longer needed because the document
            # already exists in the database.
            if temporary_path.exists():
                temporary_path.unlink(missing_ok=True)

            return {
                "document_id": existing_document.id,
                "filename": existing_document.filename,
                "status": "already_exists",
                "page_count": existing_document.page_count,
                "chunk_count": len(existing_chunks),
                "sha256": existing_document.sha256,
            }

        # M-7: Guard against redundant re-ingestion on Celery retry.
        # If the document was already created (commit succeeded before the
        # Celery broker call failed), skip ingestion and only re-dispatch
        # the extraction task.
        if document_id is not None:
            already_ingested = document_repository.get_by_id(document_id)
            if already_ingested is not None:
                logger.info(
                    "Document already ingested on a previous attempt, "
                    "re-dispatching extraction: document_id=%s",
                    document_id,
                )
                extract_facts_task.delay(already_ingested.id)
                if temporary_path.exists():
                    temporary_path.unlink(missing_ok=True)
                return {
                    "document_id": already_ingested.id,
                    "filename": already_ingested.filename,
                    "status": "already_exists",
                    "page_count": already_ingested.page_count,
                    "chunk_count": 0,
                    "sha256": already_ingested.sha256,
                }

        ingestion_service = IngestionService()

        result = ingestion_service.ingest_file(
            file_path,
            document_id=document_id,
        )

        persisted_document = document_repository.create(
            result.document
        )

        persisted_chunks = chunk_repository.create_many(
            result.chunks
        )

        db.commit()

        # C-4: Delete the temporary upload file after a successful ingestion.
        # The ingestion service has already saved a permanent copy to storage.
        if temporary_path.exists():
            temporary_path.unlink(missing_ok=True)

        extract_facts_task.delay(persisted_document.id)

        logger.info(
            "Document ingestion completed: document_id=%s pages=%s chunks=%s",
            persisted_document.id,
            persisted_document.page_count,
            len(persisted_chunks),
        )

        return {
            "document_id": persisted_document.id,
            "filename": persisted_document.filename,
            "status": persisted_document.status.value,
            "page_count": persisted_document.page_count,
            "chunk_count": len(persisted_chunks),
            "storage_path": result.storage_path,
            "sha256": persisted_document.sha256,
        }

    except (UnsupportedDocumentError, FileNotFoundError, ValueError) as exc:
        # M-3: Permanent failures — do not retry, just log and re-raise so
        # Celery marks the task as FAILURE immediately.
        db.rollback()
        logger.error(
            "Document ingestion permanent failure: file=%s document_id=%s error=%s",
            file_path,
            document_id,
            exc,
        )
        raise

    except Exception:
        db.rollback()

        logger.exception(
            "Document ingestion failed: file=%s document_id=%s",
            file_path,
            document_id,
        )

        raise

    finally:
        db.close()
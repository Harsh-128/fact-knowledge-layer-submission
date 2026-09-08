from __future__ import annotations

from pathlib import Path

from app.core.logging import get_logger
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
    autoretry_for=(Exception,),
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

        # Calculate the document hash before creating a new database record.
        file_sha256 = document_repository._calculate_sha256(
            temporary_path
        ) if hasattr(document_repository, "_calculate_sha256") else None

        if file_sha256 is None:
            import hashlib

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
                temporary_path.unlink()

            return {
                "document_id": existing_document.id,
                "filename": existing_document.filename,
                "status": "already_exists",
                "page_count": existing_document.page_count,
                "chunk_count": len(existing_chunks),
                "sha256": existing_document.sha256,
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
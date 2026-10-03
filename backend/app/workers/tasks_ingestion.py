from __future__ import annotations

import base64
import hashlib
import tempfile
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
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def ingest_document_task(
    self,
    file_path: str | None = None,
    document_id: str | None = None,
    original_filename: str | None = None,
    content_b64: str | None = None,
) -> dict:
    """
    Process a PDF asynchronously and persist its document/chunks.

    Supports two modes:
    - content_b64: PDF bytes encoded as base64 (cloud/multi-container mode)
    - file_path: path to a local file (local dev mode)
    """

    db = SessionLocal()

    try:
        # ── Resolve PDF bytes ─────────────────────────────────────────────
        if content_b64:
            # Cloud mode: content passed directly via Redis/Celery message.
            logger.info(
                "Starting document ingestion (base64 mode): document_id=%s filename=%s",
                document_id,
                original_filename,
            )
            content = base64.b64decode(content_b64)

            # Write to a temp file so IngestionService can parse it with PyMuPDF.
            suffix = Path(original_filename or "upload.pdf").suffix or ".pdf"
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp.write(content)
            tmp.flush()
            tmp.close()
            temporary_path = Path(tmp.name)
            cleanup_temp = True

        elif file_path:
            # Local dev mode: file already on disk.
            logger.info(
                "Starting document ingestion (file mode): file=%s document_id=%s",
                file_path,
                document_id,
            )
            temporary_path = Path(file_path)
            cleanup_temp = False

            if not temporary_path.exists():
                raise FileNotFoundError(
                    f"Uploaded file no longer exists: {file_path}"
                )

            with temporary_path.open("rb") as f:
                content = f.read()
        else:
            raise ValueError("Either file_path or content_b64 must be provided.")

        document_repository = DocumentRepository(db)
        chunk_repository = ChunkRepository(db)

        # SHA-256 deduplication
        file_sha256 = hashlib.sha256(content).hexdigest()

        existing_document = document_repository.get_by_sha256(file_sha256)

        if existing_document is not None:
            existing_chunks = chunk_repository.get_by_document(existing_document.id)
            logger.info(
                "Duplicate document detected: sha256=%s existing_document_id=%s",
                file_sha256,
                existing_document.id,
            )
            extract_facts_task.delay(existing_document.id)
            if cleanup_temp and temporary_path.exists():
                temporary_path.unlink(missing_ok=True)
            return {
                "document_id": existing_document.id,
                "filename": existing_document.filename,
                "status": "already_exists",
                "page_count": existing_document.page_count,
                "chunk_count": len(existing_chunks),
                "sha256": existing_document.sha256,
            }

        # Idempotency guard on retry
        if document_id is not None:
            already_ingested = document_repository.get_by_id(document_id)
            if already_ingested is not None:
                logger.info(
                    "Document already ingested on a previous attempt, "
                    "re-dispatching extraction: document_id=%s",
                    document_id,
                )
                extract_facts_task.delay(already_ingested.id)
                if cleanup_temp and temporary_path.exists():
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
            temporary_path,
            document_id=document_id,
            original_filename=original_filename,
        )

        persisted_document = document_repository.create(result.document)
        persisted_chunks = chunk_repository.create_many(result.chunks)
        db.commit()

        if cleanup_temp and temporary_path.exists():
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
        db.rollback()
        logger.error(
            "Document ingestion permanent failure: document_id=%s error=%s",
            document_id,
            exc,
        )
        raise

    except Exception:
        db.rollback()
        logger.exception(
            "Document ingestion failed: document_id=%s",
            document_id,
        )
        raise

    finally:
        db.close()

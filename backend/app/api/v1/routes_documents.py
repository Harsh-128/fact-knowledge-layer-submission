from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_database, require_api_key
from app.config import settings
from app.infra.db.models_orm import ChunkORM, FactORM
from app.infra.db.repositories.document_repo import DocumentRepository
from app.workers.tasks_ingestion import ingest_document_task


router = APIRouter(
    prefix="/documents",
    tags=["documents"],
    dependencies=[Depends(require_api_key)],
)

@router.get("")
def list_documents(
    limit: int = 100,
    offset: int = 0,
    db=Depends(get_database),
) -> list[dict]:
    """
    List processed documents for inspection in the frontend.
    """

    repository = DocumentRepository(db)

    documents = repository.list_documents(
        limit=limit,
        offset=offset,
    )

    return [
        {
            "id": document.id,
            # Strip any path prefix — show only the clean original filename.
            "filename": Path(document.filename).name,
            "status": document.status.value,
            "page_count": document.page_count,
            "created_at": document.created_at,
            "processed_at": document.processed_at,
        }
        for document in documents
    ]


@router.get("/{document_id}/status")
def get_document_status(
    document_id: str,
    db: Session = Depends(get_database),
) -> dict:
    """
    Return processing status and counts for a single document.
    Used by the Status Dashboard for live polling.
    """

    repository = DocumentRepository(db)
    document = repository.get_by_id(document_id)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )

    chunk_count = db.execute(
        select(func.count()).where(ChunkORM.document_id == document_id)
    ).scalar() or 0

    fact_count = db.execute(
        select(func.count()).where(FactORM.document_id == document_id)
    ).scalar() or 0

    needs_review_count = db.execute(
        select(func.count()).where(
            FactORM.document_id == document_id,
            FactORM.needs_review.is_(True),
        )
    ).scalar() or 0

    return {
        "id": document.id,
        "filename": Path(document.filename).name,
        "status": document.status.value,
        "page_count": document.page_count,
        "chunk_count": chunk_count,
        "fact_count": fact_count,
        "needs_review_count": needs_review_count,
        "created_at": document.created_at,
        "processed_at": document.processed_at,
        "error_message": document.error_message,
    }


@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    file: UploadFile = File(...),
) -> dict:
    """
    Upload a PDF and queue asynchronous document ingestion.
    """

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required.",
        )

    filename = Path(file.filename).name

    if Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF files are supported.",
        )

    if file.content_type not in (None, "", "application/pdf"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Uploaded file must be a PDF.",
        )

    content = await file.read()

    max_size = settings.max_upload_size_mb * 1024 * 1024

    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File exceeds the maximum allowed size of "
                f"{settings.max_upload_size_mb} MB."
            ),
        )

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded PDF is empty.",
        )

    # H-6: Validate PDF magic bytes to reject non-PDF files regardless of
    # the filename extension or Content-Type header.
    if not content.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File does not appear to be a valid PDF (missing %PDF header).",
        )

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    document_id = f"document:{uuid4().hex}"
    temporary_path = upload_dir / f"{document_id}_{filename}"

    try:
        temporary_path.write_bytes(content)

        task = ingest_document_task.delay(
            str(temporary_path),
            document_id=document_id,
            original_filename=filename,
        )

    except Exception as exc:
        if temporary_path.exists():
            temporary_path.unlink()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue document ingestion: {exc}",
        ) from exc

    return {
        "document_id": document_id,
        "filename": filename,
        "status": "queued",
        "task_id": task.id,
    }

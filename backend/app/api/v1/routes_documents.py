from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.v1.deps import get_database, require_api_key
from app.infra.db.repositories.document_repo import DocumentRepository

from app.api.v1.deps import require_api_key
from app.config import settings
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
            "filename": document.filename,
            "status": document.status.value,
            "page_count": document.page_count,
            "created_at": document.created_at,
            "processed_at": document.processed_at,
        }
        for document in documents
    ]
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

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    document_id = f"document:{uuid4().hex}"
    temporary_path = upload_dir / f"{document_id}_{filename}"

    try:
        temporary_path.write_bytes(content)

        task = ingest_document_task.delay(
            str(temporary_path),
            document_id=document_id,
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

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.deps import require_api_key
from app.workers.celery_app import celery_app


router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
    dependencies=[Depends(require_api_key)],
)


@router.get("/{task_id}")
def get_job_status(task_id: str) -> dict:
    """
    Return the current Celery status for a background task.
    """

    result = celery_app.AsyncResult(task_id)

    response = {
        "task_id": task_id,
        "status": result.status,
    }

    if result.successful():
        response["result"] = result.result

    elif result.failed():
        response["error"] = str(result.result)

    return response

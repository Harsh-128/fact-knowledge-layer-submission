from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_database, require_api_key
from app.infra.db.repositories.fact_repo import FactRepository


router = APIRouter(
    prefix="/facts",
    tags=["facts"],
    dependencies=[Depends(require_api_key)],
)


@router.get("")
def list_facts(
    document_id: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    attribute: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_database),
) -> dict:
    """
    List extracted facts with optional document/entity/attribute filters.
    """

    repository = FactRepository(db)

    if document_id:
        facts = repository.get_by_document(document_id)
    elif entity_id:
        facts = repository.get_by_entity(entity_id)
    elif attribute:
        facts = repository.get_by_attribute(attribute)
    else:
        facts = repository.list_all()

    total = len(facts)
    facts = facts[offset : offset + limit]

    return {
        "items": [
            fact.storage_dict()
            for fact in facts
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{fact_id}")
def get_fact(
    fact_id: str,
    db: Session = Depends(get_database),
) -> dict:
    """
    Retrieve a single fact, including its evidence references.
    """

    repository = FactRepository(db)
    fact = repository.get_by_id(fact_id)

    if fact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fact not found: {fact_id}",
        )

    return fact.storage_dict()

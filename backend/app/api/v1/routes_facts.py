from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_database, require_api_key
from app.infra.db.models_orm import FactORM
from app.infra.db.repositories.fact_repo import FactRepository


router = APIRouter(
    prefix="/facts",
    tags=["facts"],
    dependencies=[Depends(require_api_key)],
)


class ReviewDecision(BaseModel):
    """Body for accepting or rejecting a fact under review."""

    accept: bool
    note: str = ""


@router.get("")
def list_facts(
    document_id: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    attribute: str | None = Query(default=None),
    needs_review: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_database),
) -> dict:
    """
    List extracted facts with optional filters.

    Use needs_review=true to get only facts that need human review.
    """

    repository = FactRepository(db)

    # When needs_review filter is supplied use a direct DB query so we
    # can apply all filters together efficiently.
    if needs_review is not None:
        stmt = select(FactORM).where(FactORM.needs_review.is_(needs_review))
        if document_id:
            stmt = stmt.where(FactORM.document_id == document_id)
        if entity_id:
            stmt = stmt.where(FactORM.entity_id == entity_id)
        if attribute:
            stmt = stmt.where(FactORM.attribute == attribute)
        stmt = stmt.order_by(FactORM.created_at.desc())
        orm_facts = db.execute(stmt).scalars().all()
        facts = [repository._to_domain(f) for f in orm_facts]
    elif document_id:
        facts = repository.get_by_document(document_id)
    elif entity_id:
        facts = repository.get_by_entity(entity_id)
    elif attribute:
        facts = repository.get_by_attribute(attribute)
    else:
        facts = repository.list_all()

    total = len(facts)
    facts = facts[offset: offset + limit]

    return {
        "items": [fact.storage_dict() for fact in facts],
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


@router.patch("/{fact_id}/review")
def review_fact(
    fact_id: str,
    decision: ReviewDecision,
    db: Session = Depends(get_database),
) -> dict:
    """
    Accept or reject a fact flagged for human review.

    accept=true  → clears needs_review flag (fact confirmed correct)
    accept=false → marks fact as rejected (needs_review stays true)
    """

    repository = FactRepository(db)
    fact = repository.get_by_id(fact_id)

    if fact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fact not found: {fact_id}",
        )

    updated = repository.mark_for_review(
        fact_id,
        needs_review=not decision.accept,
    )

    db.commit()

    return {
        "fact_id": fact_id,
        "accepted": decision.accept,
        "needs_review": updated.needs_review if updated else None,
    }

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_database, require_api_key
from app.domain.models.relationship import RelationshipType
from app.infra.db.models_orm import FactORM, RelationshipORM
from app.infra.db.repositories.relationship_repo import RelationshipRepository


router = APIRouter(
    prefix="/relationships",
    tags=["relationships"],
    dependencies=[Depends(require_api_key)],
)


@router.get("")
def list_relationships(
    fact_id: str | None = Query(default=None),
    relationship_type: str | None = Query(default=None),
    document_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_database),
) -> dict:
    """
    List relationships with optional fact/type/document filters.

    When document_id is supplied, only relationships where at least one
    fact belongs to that document are returned.
    """

    repository = RelationshipRepository(db)

    if fact_id:
        relationships = repository.get_for_fact(fact_id)
    elif document_id:
        # Find all fact IDs belonging to this document, then return
        # relationships that involve any of those facts.
        fact_ids = [
            row[0]
            for row in db.execute(
                select(FactORM.id).where(FactORM.document_id == document_id)
            ).all()
        ]
        if not fact_ids:
            return {"items": [], "total": 0, "limit": limit, "offset": offset}

        from sqlalchemy import or_
        stmt = (
            select(RelationshipORM)
            .where(
                or_(
                    RelationshipORM.source_fact_id.in_(fact_ids),
                    RelationshipORM.target_fact_id.in_(fact_ids),
                )
            )
            .order_by(RelationshipORM.created_at.desc())
        )
        from app.domain.models.relationship import Relationship, RelationshipType as RT
        orm_rels = db.execute(stmt).scalars().all()
        relationships = [repository._to_domain(r) for r in orm_rels]
    elif relationship_type:
        relationships = repository.get_by_type(
            RelationshipType(relationship_type)
        )
    else:
        relationships = repository.list_all(limit=limit + offset)

    total = len(relationships)
    relationships = relationships[offset : offset + limit]

    return {
        "items": [
            relationship.model_dump(mode="json")
            for relationship in relationships
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{relationship_id}")
def get_relationship(
    relationship_id: str,
    db: Session = Depends(get_database),
) -> dict:
    """
    Retrieve a single relationship between two facts.
    """

    repository = RelationshipRepository(db)
    relationship = repository.get_by_id(relationship_id)

    if relationship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Relationship not found: {relationship_id}",
        )

    return relationship.model_dump(mode="json")

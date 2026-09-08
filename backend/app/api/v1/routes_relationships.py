from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_database, require_api_key
from app.domain.models.relationship import RelationshipType
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
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_database),
) -> dict:
    """
    List relationships with optional fact/type filters.
    """

    repository = RelationshipRepository(db)

    if fact_id:
        relationships = repository.get_for_fact(fact_id)
    elif relationship_type:
        relationships = repository.get_by_type(
    		RelationshipType(relationship_type)
	)
    else:
        relationships = repository.list_all(limit=limit)

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

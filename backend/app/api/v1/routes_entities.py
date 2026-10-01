from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_database, require_api_key
from app.infra.db.models_orm import EntityORM, FactORM
from app.infra.db.repositories.entity_repo import EntityRepository


router = APIRouter(
    prefix="/entities",
    tags=["entities"],
    dependencies=[Depends(require_api_key)],
)


@router.get("")
def list_entities(
    search: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_database),
) -> dict:
    """
    List canonical entities with optional search and type filter.
    Each entity includes its fact count and the documents it appears in.
    """

    stmt = select(EntityORM)

    if search:
        stmt = stmt.where(
            EntityORM.canonical_name.ilike(f"%{search}%")
        )

    if entity_type:
        stmt = stmt.where(EntityORM.entity_type == entity_type)

    stmt = stmt.order_by(EntityORM.canonical_name)

    orm_entities = db.execute(stmt).scalars().all()
    total = len(orm_entities)
    paged = orm_entities[offset: offset + limit]

    # For each entity, get fact count and distinct document IDs.
    result = []
    for entity in paged:
        rows = db.execute(
            select(FactORM.document_id)
            .where(FactORM.entity_id == entity.id)
            .distinct()
        ).scalars().all()

        fact_count = db.execute(
            select(func.count()).where(FactORM.entity_id == entity.id)
        ).scalar() or 0

        result.append({
            "id": entity.id,
            "canonical_name": entity.canonical_name,
            "entity_type": entity.entity_type,
            "aliases": entity.aliases or [],
            "confidence": entity.confidence,
            "fact_count": fact_count,
            "document_ids": list(rows),
        })

    return {
        "items": result,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{entity_id}")
def get_entity(
    entity_id: str,
    db: Session = Depends(get_database),
) -> dict:
    """
    Get a single entity with its facts grouped by attribute.
    """

    repo = EntityRepository(db)
    entity = repo.get_by_id(entity_id)

    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity not found: {entity_id}",
        )

    # Get all facts for this entity.
    orm_facts = db.execute(
        select(FactORM)
        .where(FactORM.entity_id == entity_id)
        .order_by(FactORM.attribute, FactORM.created_at)
    ).scalars().all()

    # Group by attribute.
    attributes: dict[str, list] = {}
    document_ids: set[str] = set()

    for fact in orm_facts:
        document_ids.add(fact.document_id)
        if fact.attribute not in attributes:
            attributes[fact.attribute] = []
        attributes[fact.attribute].append({
            "id": fact.id,
            "value": fact.value,
            "unit": fact.unit,
            "confidence": fact.confidence,
            "document_id": fact.document_id,
            "temporal_scope": fact.temporal_scope,
            "needs_review": fact.needs_review,
        })

    return {
        "id": entity.id,
        "canonical_name": entity.canonical_name,
        "entity_type": entity.entity_type,
        "aliases": entity.aliases or [],
        "confidence": entity.confidence,
        "fact_count": len(orm_facts),
        "document_ids": list(document_ids),
        "attributes": attributes,
    }

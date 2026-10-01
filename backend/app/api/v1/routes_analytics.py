from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_database, require_api_key
from app.infra.db.models_orm import (
    DocumentORM,
    EntityORM,
    FactORM,
    RelationshipORM,
)


router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    dependencies=[Depends(require_api_key)],
)


@router.get("/summary")
def get_analytics_summary(db: Session = Depends(get_database)) -> dict:
    """
    Return all analytics data in one call to minimise round-trips.
    """

    # ── Totals ────────────────────────────────────────────────────────
    total_documents = db.execute(
        select(func.count()).select_from(DocumentORM)
    ).scalar() or 0

    total_facts = db.execute(
        select(func.count()).select_from(FactORM)
    ).scalar() or 0

    total_entities = db.execute(
        select(func.count()).select_from(EntityORM)
    ).scalar() or 0

    total_relationships = db.execute(
        select(func.count()).select_from(RelationshipORM)
    ).scalar() or 0

    needs_review = db.execute(
        select(func.count()).where(FactORM.needs_review.is_(True))
    ).scalar() or 0

    # ── Facts per document ────────────────────────────────────────────
    rows = db.execute(
        select(
            DocumentORM.id,
            DocumentORM.filename,
            func.count(FactORM.id).label("fact_count"),
        )
        .outerjoin(FactORM, FactORM.document_id == DocumentORM.id)
        .group_by(DocumentORM.id, DocumentORM.filename)
        .order_by(func.count(FactORM.id).desc())
    ).all()

    facts_per_document = [
        {
            "document_id": row.id,
            "filename": row.filename.split("_", 1)[-1]
            if "_" in row.filename and row.filename.startswith("document:")
            else row.filename,
            "fact_count": row.fact_count,
        }
        for row in rows
    ]

    # ── Relationship type breakdown ───────────────────────────────────
    rel_rows = db.execute(
        select(
            RelationshipORM.relationship_type,
            func.count(RelationshipORM.id).label("count"),
        )
        .group_by(RelationshipORM.relationship_type)
        .order_by(func.count(RelationshipORM.id).desc())
    ).all()

    relationship_breakdown = [
        {"type": row.relationship_type, "count": row.count}
        for row in rel_rows
    ]

    # ── Confidence distribution (buckets: 0-20, 20-40, …, 80-100) ────
    confidence_buckets: list[dict] = []
    bucket_labels = ["0–20%", "20–40%", "40–60%", "60–80%", "80–100%"]
    bucket_ranges = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)]

    for label, (low, high) in zip(bucket_labels, bucket_ranges):
        count = db.execute(
            select(func.count()).where(
                FactORM.confidence >= low,
                FactORM.confidence < high,
            )
        ).scalar() or 0
        confidence_buckets.append({"label": label, "count": count})

    # ── Top 10 attributes by fact count ──────────────────────────────
    attr_rows = db.execute(
        select(
            FactORM.attribute,
            func.count(FactORM.id).label("count"),
        )
        .group_by(FactORM.attribute)
        .order_by(func.count(FactORM.id).desc())
        .limit(10)
    ).all()

    top_attributes = [
        {"attribute": row.attribute, "count": row.count}
        for row in attr_rows
    ]

    # ── Top 10 entities by fact count ─────────────────────────────────
    entity_rows = db.execute(
        select(
            EntityORM.id,
            EntityORM.canonical_name,
            EntityORM.entity_type,
            func.count(FactORM.id).label("count"),
        )
        .outerjoin(FactORM, FactORM.entity_id == EntityORM.id)
        .group_by(EntityORM.id, EntityORM.canonical_name, EntityORM.entity_type)
        .order_by(func.count(FactORM.id).desc())
        .limit(10)
    ).all()

    top_entities = [
        {
            "entity_id": row.id,
            "canonical_name": row.canonical_name,
            "entity_type": row.entity_type,
            "count": row.count,
        }
        for row in entity_rows
    ]

    # ── Entity type breakdown ─────────────────────────────────────────
    etype_rows = db.execute(
        select(
            EntityORM.entity_type,
            func.count(EntityORM.id).label("count"),
        )
        .group_by(EntityORM.entity_type)
        .order_by(func.count(EntityORM.id).desc())
    ).all()

    entity_type_breakdown = [
        {"type": row.entity_type, "count": row.count}
        for row in etype_rows
    ]

    return {
        "totals": {
            "documents": total_documents,
            "facts": total_facts,
            "entities": total_entities,
            "relationships": total_relationships,
            "needs_review": needs_review,
        },
        "facts_per_document": facts_per_document,
        "relationship_breakdown": relationship_breakdown,
        "confidence_distribution": confidence_buckets,
        "top_attributes": top_attributes,
        "top_entities": top_entities,
        "entity_type_breakdown": entity_type_breakdown,
    }

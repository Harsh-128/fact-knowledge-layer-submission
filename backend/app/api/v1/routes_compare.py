from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.api.v1.deps import get_database, require_api_key
from app.core.logging import get_logger
from app.domain.services.comparison_service import FactComparisonService
from app.infra.db.models_orm import RelationshipORM
from app.infra.db.repositories.fact_repo import FactRepository
from app.infra.db.repositories.relationship_repo import RelationshipRepository
from app.infra.llm.client import LLMClient


logger = get_logger(__name__)

router = APIRouter(
    prefix="/compare",
    tags=["compare"],
    dependencies=[Depends(require_api_key)],
)


class CompareRequest(BaseModel):
    """Request body for selective document comparison."""

    document_ids: list[str] = Field(
        ...,
        min_length=2,
        description="At least two document IDs to compare.",
    )


class CompareResponse(BaseModel):
    document_ids: list[str]
    facts_considered: int
    relationships_created: int
    relationships: list[dict]


@router.post("", response_model=CompareResponse)
def compare_selected_documents(
    request: CompareRequest,
    db: Session = Depends(get_database),
) -> CompareResponse:
    """
    Run fact comparison across a specific set of documents only.

    Facts are grouped by (entity_id, attribute). Within each group,
    only facts belonging to the supplied documents are compared.
    Also returns any pre-existing relationships between these documents.
    """

    if len(request.document_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 document IDs are required for comparison.",
        )

    fact_repo = FactRepository(db)
    relationship_repo = RelationshipRepository(db)

    # Fetch all facts from the selected documents only.
    all_facts = []
    for doc_id in request.document_ids:
        all_facts.extend(fact_repo.get_by_document(doc_id))

    if not all_facts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No facts found for the selected documents.",
        )

    # Collect all fact IDs for relationship lookup later.
    selected_fact_ids = {f.id for f in all_facts}

    # Group facts by (entity_id, attribute).
    groups: dict[tuple[str, str], list] = defaultdict(list)
    for fact in all_facts:
        groups[(fact.entity_id, fact.attribute)].append(fact)

    comparison_service = FactComparisonService(llm_client=LLMClient())

    newly_created: list = []
    all_relationship_ids: set[str] = set()
    all_relationships: list = []

    for (entity_id, attribute), facts in groups.items():
        # Only compare if facts come from at least 2 different documents.
        doc_ids_in_group = {f.document_id for f in facts}
        if len(doc_ids_in_group) < 2:
            continue

        logger.info(
            "Selective comparison: entity=%s attribute=%s facts=%s docs=%s",
            entity_id,
            attribute,
            len(facts),
            len(doc_ids_in_group),
        )

        try:
            relationships = comparison_service.compare_many(facts)
            persisted = relationship_repo.create_many(relationships)
            for r in persisted:
                if r.id not in all_relationship_ids:
                    all_relationship_ids.add(r.id)
                    all_relationships.append(r)
                    newly_created.append(r)
        except Exception as exc:
            logger.warning(
                "Comparison failed for entity=%s attribute=%s: %s",
                entity_id,
                attribute,
                exc,
            )
            continue

    db.commit()

    # Also return pre-existing relationships between these facts
    # (already created by auto-comparison on upload).
    existing_stmt = (
        select(RelationshipORM)
        .where(
            or_(
                RelationshipORM.source_fact_id.in_(selected_fact_ids),
                RelationshipORM.target_fact_id.in_(selected_fact_ids),
            )
        )
    )
    existing_orms = db.execute(existing_stmt).scalars().all()
    for orm_rel in existing_orms:
        if orm_rel.id not in all_relationship_ids:
            # Only include when BOTH facts are from the selected documents.
            if (
                orm_rel.source_fact_id in selected_fact_ids
                and orm_rel.target_fact_id in selected_fact_ids
            ):
                all_relationship_ids.add(orm_rel.id)
                all_relationships.append(relationship_repo._to_domain(orm_rel))

    logger.info(
        "Selective comparison complete: docs=%s facts=%s "
        "new_relationships=%s total_relationships=%s",
        len(request.document_ids),
        len(all_facts),
        len(newly_created),
        len(all_relationships),
    )

    return CompareResponse(
        document_ids=request.document_ids,
        facts_considered=len(all_facts),
        relationships_created=len(all_relationships),
        relationships=[
            r.model_dump(mode="json") for r in all_relationships
        ],
    )

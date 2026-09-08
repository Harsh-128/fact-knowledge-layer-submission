from __future__ import annotations

from app.core.logging import get_logger
from app.domain.services.comparison_service import FactComparisonService
from app.infra.db.repositories.fact_repo import FactRepository
from app.infra.db.repositories.relationship_repo import RelationshipRepository
from app.infra.llm.client import LLMClient
from app.infra.db.session import SessionLocal
from app.workers.celery_app import celery_app


logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    name="facts.compare",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def compare_facts_task(
    self,
    entity_id: str,
    attribute: str,
) -> dict:
    """
    Compare facts for one canonical entity and attribute.

    Only facts that belong to the same comparison subject are considered.
    The comparison service decides whether each pair corroborates,
    contradicts, reconciles, or is unrelated.
    """

    db = SessionLocal()

    try:
        logger.info(
            "Starting fact comparison: entity_id=%s attribute=%s",
            entity_id,
            attribute,
        )

        fact_repository = FactRepository(db)
        relationship_repository = RelationshipRepository(db)

        facts = fact_repository.list_for_comparison(
            entity_id=entity_id,
            attribute=attribute,
        )

        if len(facts) < 2:
            logger.info(
                "Not enough facts to compare: entity_id=%s attribute=%s count=%s",
                entity_id,
                attribute,
                len(facts),
            )

            return {
                "entity_id": entity_id,
                "attribute": attribute,
                "fact_count": len(facts),
                "relationship_count": 0,
            }

        comparison_service = FactComparisonService(
            llm_client=LLMClient()
        )

        relationships = comparison_service.compare_many(facts)

        persisted_relationships = relationship_repository.create_many(
            relationships
        )

        db.commit()

        review_count = sum(
            1
            for relationship in persisted_relationships
            if relationship.needs_review
        )

        logger.info(
            "Fact comparison completed: entity_id=%s attribute=%s facts=%s relationships=%s needs_review=%s",
            entity_id,
            attribute,
            len(facts),
            len(persisted_relationships),
            review_count,
        )

        return {
            "entity_id": entity_id,
            "attribute": attribute,
            "fact_count": len(facts),
            "relationship_count": len(persisted_relationships),
            "needs_review_count": review_count,
        }

    except Exception:
        db.rollback()

        logger.exception(
            "Fact comparison failed: entity_id=%s attribute=%s",
            entity_id,
            attribute,
        )

        raise

    finally:
        db.close()

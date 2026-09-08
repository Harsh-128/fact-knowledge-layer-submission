from __future__ import annotations

from app.core.logging import get_logger
from app.core.exceptions import FactExtractionError
from app.domain.services.entity_resolution_service import EntityResolutionService
from app.domain.services.extraction_service import FactExtractionService
from app.infra.db.repositories.chunk_repo import ChunkRepository
from app.infra.db.repositories.document_repo import DocumentRepository
from app.infra.db.repositories.entity_repo import EntityRepository
from app.infra.db.repositories.fact_repo import FactRepository
from app.infra.db.session import SessionLocal
from app.workers.celery_app import celery_app
from app.infra.db.repositories.fact_type_repo import FactTypeRepository


logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    name="facts.extract",
)
def extract_facts_task(
    self,
    document_id: str,
) -> dict:
    """
    Extract source-grounded facts from all chunks belonging to a document.

    Chunks are processed in batches. If a batch fails because the local LLM
    returns an invalid structured response, the batch is split into smaller
    batches instead of restarting the entire document.
    """

    db = SessionLocal()

    try:
        logger.info(
            "Starting fact extraction: document_id=%s",
            document_id,
        )

        chunk_repository = ChunkRepository(db)
        document_repository = DocumentRepository(db)
        entity_repository = EntityRepository(db)
        fact_repository = FactRepository(db)
        fact_type_repository = FactTypeRepository(db)

        document = document_repository.get_by_id(document_id)

        if document is None:
            raise ValueError(
                f"Document not found: {document_id}"
            )

        chunks = chunk_repository.get_by_document(document_id)

        if not chunks:
            raise ValueError(
                f"No chunks found for document: {document_id}"
            )

        existing_facts = fact_repository.get_by_document(document_id)

        if existing_facts:
            logger.info(
                "Facts already exist for document: document_id=%s facts=%s",
                document_id,
                len(existing_facts),
            )

            return {
                "document_id": document_id,
                "chunk_count": len(chunks),
                "fact_count": len(existing_facts),
                "needs_review_count": sum(
                    1 for fact in existing_facts if fact.needs_review
                ),
                "status": "already_extracted",
            }

        entity_resolution_service = EntityResolutionService(
            entity_repository=entity_repository,
        )

        extraction_service = FactExtractionService(
            entity_resolution_service=entity_resolution_service,
        )

        extracted_facts = []

        batch_size = 4

        for batch_start in range(0, len(chunks), batch_size):
            batch = chunks[
                batch_start:batch_start + batch_size
            ]

            logger.info(
                "Extracting facts batch: document_id=%s "
                "batch=%s-%s size=%s",
                document_id,
                batch_start + 1,
                min(
                    batch_start + batch_size,
                    len(chunks),
                ),
                len(batch),
            )

            try:
                facts = extraction_service.extract_from_chunk_batch(
                    chunks=batch,
                    document=document,
                )

            except FactExtractionError as exc:
                logger.warning(
                    "Batch extraction failed: document_id=%s "
                    "batch=%s-%s size=%s error=%s",
                    document_id,
                    batch_start + 1,
                    min(
                        batch_start + batch_size,
                        len(chunks),
                    ),
                    len(batch),
                    exc,
                )

                # Fall back to individual chunks so one malformed LLM
                # response does not restart the entire document.
                facts = []

                for fallback_chunk in batch:
                    logger.info(
                        "Fallback extraction: document_id=%s "
                        "page=%s chunk=%s",
                        document_id,
                        fallback_chunk.page_number,
                        fallback_chunk.id,
                    )

                    try:
                        fallback_facts = (
                            extraction_service.extract_from_chunk(
                                fallback_chunk,
                                document,
                            )
                        )

                        facts.extend(fallback_facts)

                    except FactExtractionError as fallback_exc:
                        logger.warning(
                            "Fallback extraction failed: "
                            "document_id=%s chunk=%s error=%s",
                            document_id,
                            fallback_chunk.id,
                            fallback_exc,
                        )

                        # Continue processing the remaining chunks.
                        continue

            for fact in facts:
                fact.document_id = document_id

                fact_type_name = (
                    fact.fact_type_id.removeprefix("type:").strip()
                )

                fact_type = fact_type_repository.get_or_create(
                    name=fact_type_name,
                )

                fact.fact_type_id = fact_type.id

            if facts:
                persisted_batch = fact_repository.create_many(facts)
            else:
                persisted_batch = []
                
            extracted_facts.extend(persisted_batch)

        db.commit()

        review_count = sum(
            1
            for fact in extracted_facts
            if fact.needs_review
        )

        logger.info(
            "Fact extraction completed: document_id=%s "
            "chunks=%s facts=%s needs_review=%s",
            document_id,
            len(chunks),
            len(extracted_facts),
            review_count,
        )

        return {
            "document_id": document_id,
            "chunk_count": len(chunks),
            "fact_count": len(extracted_facts),
            "needs_review_count": review_count,
        }

    except Exception:
        db.rollback()

        logger.exception(
            "Fact extraction failed: document_id=%s",
            document_id,
        )

        raise

    finally:
        db.close()
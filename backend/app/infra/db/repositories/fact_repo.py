from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models.fact import Fact
from app.domain.value_objects.temporal_scope import TemporalScope
from app.domain.value_objects.evidence_ref import EvidenceRef
from app.infra.db.models_orm import FactORM


class FactRepository:
    """Persistence operations for extracted facts."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self) -> list[Fact]:
        """Return all persisted facts."""

        statement = select(FactORM).order_by(
            FactORM.created_at
        )

        facts = self.db.execute(
            statement
        ).scalars().all()

        return [
            self._to_domain(fact)
            for fact in facts
        ]

    def create(self, fact: Fact) -> Fact:
        """Persist a single fact."""

        existing = self.get_by_id(fact.id)

        if existing is not None:
            return existing

        orm_fact = FactORM(
            id=fact.id,
            document_id=fact.document_id,
            chunk_id=fact.chunk_id,
            entity_id=fact.entity_id,
            fact_type_id=fact.fact_type_id,
            attribute=fact.attribute,
            value=fact.value,
            unit=fact.unit,
            temporal_scope=(
                fact.temporal_scope.model_dump(mode="json")
                if fact.temporal_scope
                else None
            ),
            evidence=[
                evidence.model_dump_for_storage()
                for evidence in fact.evidence
            ],
            confidence=fact.confidence,
            needs_review=fact.needs_review,
            extraction_method=fact.extraction_method,
            raw_extraction=fact.raw_extraction,
            created_at=fact.created_at,
        )

        self.db.add(orm_fact)
        self.db.flush()

        return self._to_domain(orm_fact)

    def create_many(self, facts: list[Fact]) -> list[Fact]:
        """Persist multiple facts."""

        if not facts:
            return []

        created: list[Fact] = []

        for fact in facts:
            created.append(self.create(fact))

        self.db.flush()

        return created

    def get_by_id(
        self,
        fact_id: str,
    ) -> Fact | None:
        """Find a fact by ID."""

        orm_fact = self.db.get(
            FactORM,
            fact_id,
        )

        if orm_fact is None:
            return None

        return self._to_domain(orm_fact)

    def get_by_document(
        self,
        document_id: str,
    ) -> list[Fact]:
        """Return all facts extracted from a document."""

        statement = (
            select(FactORM)
            .where(FactORM.document_id == document_id)
            .order_by(FactORM.created_at)
        )

        facts = self.db.execute(
            statement
        ).scalars().all()

        return [
            self._to_domain(fact)
            for fact in facts
        ]

    def get_by_entity(
        self,
        entity_id: str,
    ) -> list[Fact]:
        """Return all facts associated with an entity."""

        statement = (
            select(FactORM)
            .where(FactORM.entity_id == entity_id)
            .order_by(FactORM.created_at)
        )

        facts = self.db.execute(
            statement
        ).scalars().all()

        return [
            self._to_domain(fact)
            for fact in facts
        ]

    def get_by_attribute(
        self,
        attribute: str,
        *,
        entity_id: str | None = None,
    ) -> list[Fact]:
        """Find facts by attribute, optionally restricted to an entity."""

        statement = select(FactORM).where(
            FactORM.attribute == attribute
        )

        if entity_id is not None:
            statement = statement.where(
                FactORM.entity_id == entity_id
            )

        statement = statement.order_by(
            FactORM.created_at
        )

        facts = self.db.execute(
            statement
        ).scalars().all()

        return [
            self._to_domain(fact)
            for fact in facts
        ]

    def list_for_comparison(
        self,
        entity_id: str,
        attribute: str,
    ) -> list[Fact]:
        """
        Return facts that are candidates for cross-document comparison.

        This deliberately filters by canonical entity and attribute before
        the comparison service performs semantic reasoning.
        """

        return self.get_by_attribute(
            attribute,
            entity_id=entity_id,
        )

    def mark_for_review(
        self,
        fact_id: str,
        needs_review: bool = True,
    ) -> Fact | None:
        """Update the review flag for a fact."""

        orm_fact = self.db.get(
            FactORM,
            fact_id,
        )

        if orm_fact is None:
            return None

        orm_fact.needs_review = needs_review

        self.db.add(orm_fact)
        self.db.flush()

        return self._to_domain(orm_fact)

    def delete_by_document(
        self,
        document_id: str,
    ) -> int:
        """Delete all facts belonging to a document."""

        facts = (
            self.db.execute(
                select(FactORM).where(
                    FactORM.document_id == document_id
                )
            )
            .scalars()
            .all()
        )

        count = len(facts)

        for fact in facts:
            self.db.delete(fact)

        self.db.flush()

        return count

    @staticmethod
    def _to_domain(
        orm_fact: FactORM,
    ) -> Fact:
        """Convert a database fact into the domain model."""

        temporal_scope_data = orm_fact.temporal_scope or {}

        temporal_scope = TemporalScope(
            **temporal_scope_data
        )

        evidence = [
            EvidenceRef(**item)
            for item in (orm_fact.evidence or [])
        ]

        return Fact(
            id=orm_fact.id,
            document_id=orm_fact.document_id,
            chunk_id=orm_fact.chunk_id,
            entity_id=orm_fact.entity_id,
            fact_type_id=orm_fact.fact_type_id,
            attribute=orm_fact.attribute,
            value=orm_fact.value,
            unit=orm_fact.unit,
            temporal_scope=temporal_scope,
            evidence=evidence,
            confidence=orm_fact.confidence,
            needs_review=orm_fact.needs_review,
            extraction_method=orm_fact.extraction_method,
            raw_extraction=orm_fact.raw_extraction,
            created_at=orm_fact.created_at,
        )

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models.relationship import Relationship, RelationshipType
from app.infra.db.models_orm import RelationshipORM


class RelationshipRepository:
    """Persistence operations for fact relationships."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, relationship: Relationship) -> Relationship:
        """Persist a new fact relationship."""

        existing = self.get_by_id(relationship.id)

        if existing is not None:
            return existing

        orm_relationship = RelationshipORM(
            id=relationship.id,
            source_fact_id=relationship.source_fact_id,
            target_fact_id=relationship.target_fact_id,
            relationship_type=relationship.relationship_type.value,
            confidence=relationship.confidence,
            explanation=relationship.explanation,
            evidence=relationship.evidence,
            needs_review=relationship.needs_review,
            created_at=relationship.created_at,
        )

        self.db.add(orm_relationship)
        self.db.flush()

        return self._to_domain(orm_relationship)

    def create_many(
        self,
        relationships: list[Relationship],
    ) -> list[Relationship]:
        """Persist multiple relationships."""

        if not relationships:
            return []

        created: list[Relationship] = []

        for relationship in relationships:
            created.append(self.create(relationship))

        self.db.flush()

        return created

    def get_by_id(
        self,
        relationship_id: str,
    ) -> Relationship | None:
        """Find a relationship by ID."""

        orm_relationship = self.db.get(
            RelationshipORM,
            relationship_id,
        )

        if orm_relationship is None:
            return None

        return self._to_domain(orm_relationship)

    def get_between_facts(
        self,
        source_fact_id: str,
        target_fact_id: str,
    ) -> Relationship | None:
        """Find an existing relationship between two facts."""

        statement = (
            select(RelationshipORM)
            .where(
                RelationshipORM.source_fact_id == source_fact_id,
                RelationshipORM.target_fact_id == target_fact_id,
            )
            .limit(1)
        )

        orm_relationship = self.db.execute(
            statement
        ).scalar_one_or_none()

        if orm_relationship is None:
            return None

        return self._to_domain(orm_relationship)

    def get_for_fact(
        self,
        fact_id: str,
    ) -> list[Relationship]:
        """Return all relationships involving a fact."""

        statement = (
            select(RelationshipORM)
            .where(
                (RelationshipORM.source_fact_id == fact_id)
                | (RelationshipORM.target_fact_id == fact_id)
            )
            .order_by(RelationshipORM.created_at)
        )

        relationships = self.db.execute(
            statement
        ).scalars().all()

        return [
            self._to_domain(relationship)
            for relationship in relationships
        ]

    def list_all(
        self,
        *,
        limit: int = 100,
    ) -> list[Relationship]:
        """Return all persisted relationships."""

        if limit < 1:
            raise ValueError("limit must be at least 1.")

        statement = (
            select(RelationshipORM)
            .order_by(RelationshipORM.created_at.desc())
            .limit(limit)
        )

        relationships = self.db.execute(
            statement
        ).scalars().all()

        return [
            self._to_domain(relationship)
            for relationship in relationships
        ]

    def get_by_type(
        self,
        relationship_type: RelationshipType,
        *,
        limit: int = 100,
    ) -> list[Relationship]:
        """Return relationships of a specific type."""

        if limit < 1:
            raise ValueError("limit must be at least 1.")

        statement = (
            select(RelationshipORM)
            .where(
                RelationshipORM.relationship_type
                == relationship_type.value
            )
            .order_by(RelationshipORM.created_at.desc())
            .limit(limit)
        )

        relationships = self.db.execute(
            statement
        ).scalars().all()

        return [
            self._to_domain(relationship)
            for relationship in relationships
        ]

    def mark_for_review(
        self,
        relationship_id: str,
        needs_review: bool = True,
    ) -> Relationship | None:
        """Update the review flag for a relationship."""

        orm_relationship = self.db.get(
            RelationshipORM,
            relationship_id,
        )

        if orm_relationship is None:
            return None

        orm_relationship.needs_review = needs_review

        self.db.add(orm_relationship)
        self.db.flush()

        return self._to_domain(orm_relationship)

    def delete_for_fact(
        self,
        fact_id: str,
    ) -> int:
        """Delete relationships involving a specific fact."""

        statement = select(RelationshipORM).where(
            (RelationshipORM.source_fact_id == fact_id)
            | (RelationshipORM.target_fact_id == fact_id)
        )

        relationships = self.db.execute(
            statement
        ).scalars().all()

        count = len(relationships)

        for relationship in relationships:
            self.db.delete(relationship)

        self.db.flush()

        return count

    @staticmethod
    def _to_domain(
        orm_relationship: RelationshipORM,
    ) -> Relationship:
        """Convert a database relationship into the domain model."""

        return Relationship(
            id=orm_relationship.id,
            source_fact_id=orm_relationship.source_fact_id,
            target_fact_id=orm_relationship.target_fact_id,
            relationship_type=RelationshipType(
                orm_relationship.relationship_type
            ),
            confidence=orm_relationship.confidence,
            explanation=orm_relationship.explanation,
            evidence=list(orm_relationship.evidence or []),
            needs_review=orm_relationship.needs_review,
            created_at=orm_relationship.created_at,
        )

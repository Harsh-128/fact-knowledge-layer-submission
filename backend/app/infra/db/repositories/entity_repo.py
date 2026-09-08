from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models.entity import Entity
from app.infra.db.models_orm import EntityORM


class EntityRepository:
    """Persistence operations for canonical entities."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, entity: Entity) -> Entity:
        """Persist a new canonical entity."""

        existing = self.get_by_id(entity.id)

        if existing is not None:
            return existing

        orm_entity = EntityORM(
            id=entity.id,
            canonical_name=entity.canonical_name,
            entity_type=entity.entity_type,
            aliases=entity.aliases,
            description=entity.description,
            confidence=entity.confidence,
            embedding=None,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

        self.db.add(orm_entity)
        self.db.flush()

        return self._to_domain(orm_entity)

    def get_by_id(
        self,
        entity_id: str,
    ) -> Entity | None:
        """Find an entity by ID."""

        orm_entity = self.db.get(
            EntityORM,
            entity_id,
        )

        if orm_entity is None:
            return None

        return self._to_domain(orm_entity)

    def get_orm_by_id(
        self,
        entity_id: str,
    ) -> EntityORM | None:
        """Return the ORM entity when database-level access is needed."""

        return self.db.get(
            EntityORM,
            entity_id,
        )

    def get_by_canonical_name(
        self,
        canonical_name: str,
    ) -> Entity | None:
        """Find an entity by its canonical name."""

        statement = (
            select(EntityORM)
            .where(EntityORM.canonical_name == canonical_name)
            .limit(1)
        )

        orm_entity = self.db.execute(
            statement
        ).scalar_one_or_none()

        if orm_entity is None:
            return None

        return self._to_domain(orm_entity)

    def find_by_alias(
        self,
        alias: str,
    ) -> list[Entity]:
        """
        Find entities containing an alias.

        Aliases are stored as JSONB, so PostgreSQL's JSON containment
        operator is used for the lookup.
        """

        statement = select(EntityORM).where(
            EntityORM.aliases.contains([alias])
        )

        entities = self.db.execute(
            statement
        ).scalars().all()

        return [
            self._to_domain(entity)
            for entity in entities
        ]

    def list_entities(
        self,
        *,
        entity_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Entity]:
        """List canonical entities with optional type filtering."""

        if limit < 1:
            raise ValueError("limit must be at least 1.")

        if offset < 0:
            raise ValueError("offset cannot be negative.")

        statement = select(EntityORM)

        if entity_type:
            statement = statement.where(
                EntityORM.entity_type == entity_type
            )

        statement = (
            statement
            .order_by(EntityORM.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        entities = self.db.execute(
            statement
        ).scalars().all()

        return [
            self._to_domain(entity)
            for entity in entities
        ]

    def update(
        self,
        entity: Entity,
    ) -> Entity:
        """Update an existing entity."""

        orm_entity = self.get_orm_by_id(entity.id)

        if orm_entity is None:
            raise ValueError(
                f"Entity not found: {entity.id}"
            )

        orm_entity.canonical_name = entity.canonical_name
        orm_entity.entity_type = entity.entity_type
        orm_entity.aliases = entity.aliases
        orm_entity.description = entity.description
        orm_entity.confidence = entity.confidence
        orm_entity.updated_at = entity.updated_at

        self.db.add(orm_entity)
        self.db.flush()

        return self._to_domain(orm_entity)

    def add_alias(
        self,
        entity_id: str,
        alias: str,
    ) -> Entity:
        """Add an alias to an existing entity."""

        orm_entity = self.get_orm_by_id(entity_id)

        if orm_entity is None:
            raise ValueError(
                f"Entity not found: {entity_id}"
            )

        aliases = list(orm_entity.aliases or [])

        if alias.strip() and alias not in aliases:
            aliases.append(alias.strip())

        orm_entity.aliases = aliases

        self.db.add(orm_entity)
        self.db.flush()

        return self._to_domain(orm_entity)

    def delete(
        self,
        entity_id: str,
    ) -> bool:
        """Delete an entity by ID."""

        orm_entity = self.get_orm_by_id(entity_id)

        if orm_entity is None:
            return False

        self.db.delete(orm_entity)
        self.db.flush()

        return True

    @staticmethod
    def _to_domain(
        orm_entity: EntityORM,
    ) -> Entity:
        """Convert a database entity into the domain model."""

        return Entity(
            id=orm_entity.id,
            canonical_name=orm_entity.canonical_name,
            entity_type=orm_entity.entity_type,
            aliases=list(orm_entity.aliases or []),
            description=orm_entity.description,
            confidence=orm_entity.confidence,
            created_at=orm_entity.created_at,
            updated_at=orm_entity.updated_at,
        )

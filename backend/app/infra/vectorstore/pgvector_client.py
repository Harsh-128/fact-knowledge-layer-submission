from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infra.db.models_orm import EntityORM


class PGVectorClient:
    """
    PostgreSQL/pgvector helper for entity embeddings.

    Embeddings are stored directly on EntityORM.embedding.
    The database must have the pgvector extension enabled.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def store_entity_embedding(
        self,
        entity_id: str,
        embedding: Sequence[float],
    ) -> EntityORM:
        """
        Store an embedding for an existing entity.
        """

        entity = self.db.get(EntityORM, entity_id)

        if entity is None:
            raise ValueError(f"Entity not found: {entity_id}")

        vector = list(embedding)

        if len(vector) != 1536:
            raise ValueError(
                f"Expected a 1536-dimensional embedding, got {len(vector)}."
            )

        entity.embedding = vector

        self.db.add(entity)
        self.db.flush()

        return entity

    def find_similar_entities(
        self,
        embedding: Sequence[float],
        *,
        limit: int = 5,
        entity_type: str | None = None,
    ) -> list[tuple[EntityORM, float]]:
        """
        Find entities with embeddings closest to the supplied vector.

        Returns:
            A list of (entity, distance) tuples ordered by similarity.

        Smaller cosine distance means greater similarity.
        """

        vector = list(embedding)

        if len(vector) != 1536:
            raise ValueError(
                f"Expected a 1536-dimensional embedding, got {len(vector)}."
            )

        if limit < 1:
            raise ValueError("limit must be at least 1.")

        if entity_type:
            distance = EntityORM.embedding.cosine_distance(vector)

            statement = (
                select(EntityORM, distance.label("distance"))
                .where(
                    EntityORM.embedding.is_not(None),
                    EntityORM.entity_type == entity_type,
                )
                .order_by(distance)
                .limit(limit)
            )
        else:
            distance = EntityORM.embedding.cosine_distance(vector)

            statement = (
                select(EntityORM, distance.label("distance"))
                .where(EntityORM.embedding.is_not(None))
                .order_by(distance)
                .limit(limit)
            )

        results = self.db.execute(statement).all()

        return [
            (entity, float(distance))
            for entity, distance in results
        ]

    def delete_entity_embedding(
        self,
        entity_id: str,
    ) -> None:
        """Remove the embedding associated with an entity."""

        entity = self.db.get(EntityORM, entity_id)

        if entity is None:
            raise ValueError(f"Entity not found: {entity_id}")

        entity.embedding = None

        self.db.add(entity)
        self.db.flush()

    def count_embedded_entities(self) -> int:
        """Return the number of entities that currently have embeddings."""

        statement = select(EntityORM.id).where(
            EntityORM.embedding.is_not(None)
        )

        return len(self.db.execute(statement).scalars().all())

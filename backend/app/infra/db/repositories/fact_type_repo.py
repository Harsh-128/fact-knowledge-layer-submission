from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models.fact_type import FactType
from app.infra.db.models_orm import FactTypeORM


class FactTypeRepository:
    """Persistence operations for evolving fact-type schemas."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_name(self, name: str) -> FactType | None:
        """Find a fact type by case-insensitive normalized name."""

        normalized_name = " ".join(name.strip().split())

        if not normalized_name:
            return None

        statement = select(FactTypeORM).where(
            FactTypeORM.name.ilike(normalized_name)
        )

        orm_fact_type = self.db.execute(statement).scalar_one_or_none()

        if orm_fact_type is None:
            return None

        return self._to_domain(orm_fact_type)

    def get_or_create(
        self,
        name: str,
        description: str | None = None,
        value_schema: dict | None = None,
    ) -> FactType:
        """Return an existing fact type or create a new one."""

        normalized_name = " ".join(name.strip().split())

        if not normalized_name:
            raise ValueError("Fact type name cannot be empty.")

        existing = self.get_by_name(normalized_name)

        if existing is not None:
            return existing

        fact_type = FactType(
            id=f"fact-type-{__import__('uuid').uuid4().hex}",
            name=normalized_name,
            description=description,
            value_schema=value_schema or {},
        )

        orm_fact_type = FactTypeORM(
            id=fact_type.id,
            name=fact_type.name,
            description=fact_type.description,
            value_schema=fact_type.value_schema,
            version=fact_type.version,
            is_active=fact_type.is_active,
            created_at=fact_type.created_at,
            updated_at=fact_type.updated_at,
        )

        self.db.add(orm_fact_type)
        self.db.flush()

        return fact_type

    @staticmethod
    def _to_domain(orm_fact_type: FactTypeORM) -> FactType:
        return FactType(
            id=orm_fact_type.id,
            name=orm_fact_type.name,
            description=orm_fact_type.description,
            value_schema=orm_fact_type.value_schema,
            version=orm_fact_type.version,
            is_active=orm_fact_type.is_active,
            created_at=orm_fact_type.created_at,
            updated_at=orm_fact_type.updated_at,
        )

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.domain.models.fact_type import FactType


class SchemaRegistryService:
    """
    Manage the evolving fact-type schema.

    Fact types are data-driven rather than hard-coded into the application,
    allowing new kinds of facts to appear in previously unseen documents.
    """

    def __init__(self) -> None:
        self._fact_types: dict[str, FactType] = {}

    def get_or_create(
        self,
        name: str,
        description: str | None = None,
        value_schema: dict | None = None,
    ) -> FactType:
        """
        Return an existing fact type or create a new one.

        Matching is case-insensitive and whitespace-normalized.
        """

        normalized_name = self._normalize_name(name)

        if not normalized_name:
            raise ValueError("Fact type name cannot be empty.")

        existing = self.get_by_name(normalized_name)

        if existing is not None:
            return existing

        fact_type = FactType(
            id=f"fact-type-{uuid4().hex}",
            name=normalized_name,
            description=description,
            value_schema=value_schema or {},
        )

        self._fact_types[fact_type.id] = fact_type

        return fact_type

    def get_by_id(self, fact_type_id: str) -> FactType | None:
        """Return a fact type by its ID."""

        return self._fact_types.get(fact_type_id)

    def get_by_name(self, name: str) -> FactType | None:
        """
        Find a fact type by normalized name.
        """

        normalized_name = self._normalize_name(name)

        for fact_type in self._fact_types.values():
            if fact_type.matches_name(normalized_name):
                return fact_type

        return None

    def list_active(self) -> list[FactType]:
        """Return all currently active fact types."""

        return [
            fact_type
            for fact_type in self._fact_types.values()
            if fact_type.is_active
        ]

    def update_schema(
        self,
        fact_type_id: str,
        value_schema: dict,
    ) -> FactType:
        """
        Update the schema of an existing fact type.

        The FactType model increments its version automatically.
        """

        fact_type = self.get_by_id(fact_type_id)

        if fact_type is None:
            raise KeyError(
                f"Fact type not found: {fact_type_id}"
            )

        fact_type.update_schema(value_schema)

        return fact_type

    def deactivate(self, fact_type_id: str) -> FactType:
        """
        Deactivate a fact type without deleting its historical definition.
        """

        fact_type = self.get_by_id(fact_type_id)

        if fact_type is None:
            raise KeyError(
                f"Fact type not found: {fact_type_id}"
            )

        fact_type.is_active = False
        fact_type.updated_at = datetime.utcnow()

        return fact_type

    @staticmethod
    def _normalize_name(name: str) -> str:
        """
        Normalize fact-type names while keeping them human-readable.
        """

        return " ".join(name.strip().split())


def get_schema_registry_service() -> SchemaRegistryService:
    """Return a schema registry service instance."""

    return SchemaRegistryService()

from datetime import datetime

from pydantic import BaseModel, Field


class Entity(BaseModel):
    """
    Canonical representation of a real-world entity.

    Examples:
    - "Delhivery Limited"
    - "Delhivery"
    - "India"
    - "Indian economy"

    Different mentions can later be resolved to the same canonical entity.
    """

    id: str = Field(
        ...,
        description="Unique identifier for the canonical entity.",
    )

    canonical_name: str = Field(
        ...,
        min_length=1,
        description="Canonical name used internally for the entity.",
    )

    entity_type: str = Field(
        default="unknown",
        min_length=1,
        description="Entity category such as company, country, organization, or industry.",
    )

    aliases: list[str] = Field(
        default_factory=list,
        description="Alternative names or mentions referring to this entity.",
    )

    description: str | None = Field(
        default=None,
        description="Optional description of the entity.",
    )

    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence that this canonical entity representation is correct.",
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when the entity was created.",
    )

    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when the entity was last updated.",
    )

    def add_alias(self, alias: str) -> None:
        """Add an alternative entity name if it is not already present."""
        normalized = alias.strip()

        if not normalized:
            return

        if normalized.lower() == self.canonical_name.strip().lower():
            return

        if not any(existing.lower() == normalized.lower() for existing in self.aliases):
            self.aliases.append(normalized)
            self.updated_at = datetime.utcnow()

    def matches(self, name: str) -> bool:
        """
        Check whether a name matches the canonical name or one of its aliases.
        """
        normalized = name.strip().lower()

        if normalized == self.canonical_name.strip().lower():
            return True

        return any(alias.lower() == normalized for alias in self.aliases)
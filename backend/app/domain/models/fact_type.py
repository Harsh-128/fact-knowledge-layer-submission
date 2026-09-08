from datetime import datetime

from pydantic import BaseModel, Field


class FactType(BaseModel):
    """
    Describes the schema/category of a fact.

    Fact types are intentionally data-driven so the system can evolve
    when new kinds of facts appear in previously unseen documents.
    """

    id: str = Field(
        ...,
        description="Unique identifier for the fact type.",
    )

    name: str = Field(
        ...,
        min_length=1,
        description="Human-readable fact type name.",
    )

    description: str | None = Field(
        default=None,
        description="Description of what this fact type represents.",
    )

    value_schema: dict = Field(
        default_factory=dict,
        description=(
            "JSON-compatible schema describing the expected structure "
            "of the fact value."
        ),
    )

    version: int = Field(
        default=1,
        ge=1,
        description="Schema version of this fact type.",
    )

    is_active: bool = Field(
        default=True,
        description="Whether this fact type can currently be used.",
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when the fact type was created.",
    )

    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when the fact type was last updated.",
    )

    def matches_name(self, name: str) -> bool:
        """Check whether a name matches this fact type case-insensitively."""
        return self.name.strip().lower() == name.strip().lower()

    def update_schema(self, value_schema: dict) -> None:
        """
        Replace the value schema and increment its version.
        """
        if not isinstance(value_schema, dict):
            raise TypeError("value_schema must be a dictionary")

        self.value_schema = value_schema
        self.version += 1
        self.updated_at = datetime.utcnow()
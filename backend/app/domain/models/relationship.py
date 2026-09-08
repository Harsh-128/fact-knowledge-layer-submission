from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class RelationshipType(StrEnum):
    """Possible relationships between two facts."""

    CORROBORATES = "corroborates"
    CONTRADICTS = "contradicts"
    RECONCILES = "reconciles"
    UNRELATED = "unrelated"


class Relationship(BaseModel):
    """
    Represents a semantic relationship between two facts.

    Relationships are produced by the cross-document comparison
    pipeline after facts have been normalized and grouped by entity
    and attribute.
    """

    id: str = Field(
        ...,
        description="Unique identifier for the relationship.",
    )

    source_fact_id: str = Field(
        ...,
        description="Identifier of the first fact.",
    )

    target_fact_id: str = Field(
        ...,
        description="Identifier of the second fact.",
    )

    relationship_type: RelationshipType = Field(
        ...,
        description="Semantic relationship between the two facts.",
    )

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the relationship classification.",
    )

    explanation: str = Field(
        ...,
        min_length=1,
        description="Human-readable explanation for the relationship.",
    )

    evidence: list[str] = Field(
        default_factory=list,
        description="Evidence or reasoning references supporting the relationship.",
    )

    needs_review: bool = Field(
        default=False,
        description="Whether the relationship requires human review.",
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when the relationship was created.",
    )

    def involves_fact(self, fact_id: str) -> bool:
        """Return whether the relationship contains the given fact."""
        return fact_id in {
            self.source_fact_id,
            self.target_fact_id,
        }

    def is_confident(self, threshold: float = 0.8) -> bool:
        """Return whether the relationship meets the confidence threshold."""
        return self.confidence >= threshold

    def mark_for_review(self) -> None:
        """Mark the relationship for human review."""
        self.needs_review = True

    @property
    def is_positive(self) -> bool:
        """
        Return whether the relationship represents agreement
        rather than contradiction.
        """
        return self.relationship_type in {
            RelationshipType.CORROBORATES,
            RelationshipType.RECONCILES,
        }
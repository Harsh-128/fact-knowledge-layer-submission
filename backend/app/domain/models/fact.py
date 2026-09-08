from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.value_objects.evidence_ref import EvidenceRef
from app.domain.value_objects.temporal_scope import TemporalScope


class Fact(BaseModel):
    """
    A normalized, source-grounded fact extracted from a document.

    A fact describes an attribute/value belonging to an entity,
    together with temporal context, source evidence, and extraction
    confidence.
    """

    id: str = Field(
        ...,
        description="Unique identifier for the fact.",
    )

    document_id: str = Field(
        ...,
        description="Identifier of the source document.",
    )

    chunk_id: str | None = Field(
        default=None,
        description="Identifier of the source chunk.",
    )

    entity_id: str = Field(
        ...,
        description="Canonical entity to which this fact belongs.",
    )

    fact_type_id: str = Field(
        ...,
        description="Identifier of the fact type/schema.",
    )

    attribute: str = Field(
        ...,
        min_length=1,
        description="Normalized attribute represented by the fact.",
    )

    value: Any = Field(
        ...,
        description="Structured or scalar value of the fact.",
    )

    unit: str | None = Field(
        default=None,
        description="Unit associated with the value, such as INR, percent, USD, or tonnes.",
    )

    temporal_scope: TemporalScope | None = Field(
        default=None,
        description="Time period to which the fact applies.",
    )

    evidence: list[EvidenceRef] = Field(
        default_factory=list,
        description="Source evidence supporting this fact.",
    )

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall confidence in the extracted fact.",
    )

    needs_review: bool = Field(
        default=False,
        description="Whether the fact should be reviewed by a human.",
    )

    extraction_method: str = Field(
        default="llm",
        description="Method used to extract the fact.",
    )

    raw_extraction: dict[str, Any] = Field(
        default_factory=dict,
        description="Original structured extraction returned by the extraction pipeline.",
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when the fact was created.",
    )

    def add_evidence(self, evidence_ref: EvidenceRef) -> None:
        """Attach a source evidence reference to this fact."""
        self.evidence.append(evidence_ref)

    def has_evidence(self) -> bool:
        """Return True when the fact has at least one evidence reference."""
        return len(self.evidence) > 0

    def mark_for_review(self) -> None:
        """Mark this fact as requiring human review."""
        self.needs_review = True

    def is_high_confidence(self, threshold: float = 0.8) -> bool:
        """Return whether the fact confidence meets the supplied threshold."""
        return self.confidence >= threshold

    def storage_dict(self) -> dict[str, Any]:
        """
        Return a JSON-serializable representation suitable for persistence.
        """
        return self.model_dump(mode="json", exclude_none=True)
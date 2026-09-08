from pydantic import BaseModel, Field


class EvidenceRef(BaseModel):
    """
    Identifies the exact source location supporting a fact.
    """

    document_id: str = Field(
        ...,
        description="Unique identifier of the source document.",
    )

    page_number: int = Field(
        ...,
        ge=1,
        description="1-based PDF page number containing the evidence.",
    )

    chunk_id: str | None = Field(
        default=None,
        description="Identifier of the semantic chunk containing the evidence.",
    )

    quoted_text: str = Field(
        ...,
        min_length=1,
        description="Exact text extracted from the source document.",
    )

    char_start: int | None = Field(
        default=None,
        ge=0,
        description="Character offset where the evidence starts within the chunk.",
    )

    char_end: int | None = Field(
        default=None,
        ge=0,
        description="Character offset where the evidence ends within the chunk.",
    )

    def has_offsets(self) -> bool:
        """Return True when both character offsets are available."""
        return self.char_start is not None and self.char_end is not None

    def model_dump_for_storage(self) -> dict:
        """
        Return a JSON-serializable representation suitable for JSONB storage.
        """
        return self.model_dump(exclude_none=True)
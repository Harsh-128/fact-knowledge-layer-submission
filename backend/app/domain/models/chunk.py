from pydantic import BaseModel, Field


class Chunk(BaseModel):
    """
    A semantic text chunk extracted from a document.

    Chunks are the intermediate representation between PDF parsing
    and fact extraction.
    """

    id: str = Field(
        ...,
        description="Unique identifier for the chunk.",
    )

    document_id: str = Field(
        ...,
        description="Identifier of the source document.",
    )

    page_number: int = Field(
        ...,
        ge=1,
        description="1-based PDF page number containing the chunk.",
    )

    chunk_index: int = Field(
        ...,
        ge=0,
        description="Zero-based position of the chunk within the document.",
    )

    text: str = Field(
        ...,
        min_length=1,
        description="Text contained in this chunk.",
    )

    char_start: int | None = Field(
        default=None,
        ge=0,
        description="Character offset where the chunk starts on the source page.",
    )

    char_end: int | None = Field(
        default=None,
        ge=0,
        description="Character offset where the chunk ends on the source page.",
    )

    token_count: int | None = Field(
        default=None,
        ge=0,
        description="Approximate number of tokens in the chunk.",
    )

    def has_offsets(self) -> bool:
        """Return True when both character offsets are available."""
        return self.char_start is not None and self.char_end is not None

    @property
    def length(self) -> int:
        """Return the number of characters in the chunk."""
        return len(self.text)
from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractedTemporalScope(BaseModel):
    """
    Temporal context extracted from the source text.

    Dates are kept as strings at the LLM boundary because source
    documents may express periods in many different forms, such as:

    - FY2021
    - FY 2024-25
    - Q4 FY24
    - December 2024
    - year ended March 31, 2024
    """

    start_date: str | None = Field(
        default=None,
        description="Normalized start date when explicitly available, in YYYY-MM-DD format.",
    )

    end_date: str | None = Field(
        default=None,
        description="Normalized end date when explicitly available, in YYYY-MM-DD format.",
    )

    period_label: str | None = Field(
        default=None,
        description="Original period expression, such as FY2021, Q4 FY24, or December 2024.",
    )

    granularity: str | None = Field(
        default=None,
        description="Temporal granularity such as day, month, quarter, fiscal_year, or year.",
    )


class ExtractedEvidence(BaseModel):
    """
    Exact evidence supporting an extracted fact.

    Evidence is captured at the extraction boundary so the system
    can later create a domain EvidenceRef tied to a document.
    """

    page_number: int = Field(
        ...,
        ge=1,
        description="1-based PDF page number containing the evidence.",
    )

    chunk_id: str | None = Field(
        default=None,
        description="Identifier of the chunk from which the evidence was extracted.",
    )

    quoted_text: str = Field(
        ...,
        min_length=1,
        description="Exact verbatim text from the source chunk supporting the fact.",
    )

    char_start: int | None = Field(
        default=None,
        ge=0,
        description="Character offset where the quoted evidence starts in the source chunk.",
    )

    char_end: int | None = Field(
        default=None,
        ge=0,
        description="Character offset where the quoted evidence ends in the source chunk.",
    )


class ExtractedFact(BaseModel):
    """
    One structured fact extracted from a document chunk.

    The schema deliberately supports heterogeneous values because
    different documents may contain:
    - numbers,
    - percentages,
    - dates,
    - strings,
    - lists,
    - structured objects.
    """

    entity_name: str = Field(
        ...,
        min_length=1,
        description="Name or mention of the entity associated with the fact.",
    )

    entity_type: str = Field(
        default="unknown",
        min_length=1,
        description=(
            "Entity category such as company, country, organization, "
            "industry, metric, or unknown."
        ),
    )

    fact_type_name: str = Field(
        ...,
        min_length=1,
        description=(
            "Human-readable category for the fact. "
            "Use a concise generic name that can become a reusable schema."
        ),
    )

    attribute: str = Field(
        ...,
        min_length=1,
        description=(
            "Normalized attribute represented by the fact, "
            "for example revenue, GDP growth, employee count, or market share."
        ),
    )

    value: str = Field(
        ...,
        min_length=1,
        description=(
            "The extracted fact value represented as a JSON-compatible string. "
            "For numbers, return the numeric value as text; for percentages, "
            "dates, labels, lists, or structured values, preserve the source "
            "meaning in a compact JSON-compatible representation."
        ),
    )

    unit: str | None = Field(
        default=None,
        description=(
            "Unit associated with the value, such as INR, USD, percent, "
            "million, billion, tonnes, or count."
        ),
    )

    temporal_scope: ExtractedTemporalScope | None = Field(
        default=None,
        description="Time period to which the fact applies.",
    )

    evidence: list[ExtractedEvidence] = Field(
        ...,
        min_length=1,
        description="One or more exact source references supporting the fact.",
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model confidence that the extracted fact is correct.",
    )

    extraction_notes: str | None = Field(
        default=None,
        description=(
            "Short note explaining ambiguity, interpretation, "
            "or unusual source formatting."
        ),
    )


class FactExtractionResponse(BaseModel):
    """
    Complete structured response returned by the fact extraction model.
    """

    facts: list[ExtractedFact] = Field(
        default_factory=list,
        description="Facts extracted from the supplied document chunk.",
    )

    extraction_warnings: list[str] = Field(
        default_factory=list,
        description=(
            "Warnings about OCR quality, ambiguous wording, incomplete "
            "context, tables, or other extraction limitations."
        ),
    )


class EntityResolutionCandidate(BaseModel):
    """
    Candidate canonical entity considered during entity resolution.
    """

    entity_id: str = Field(
        ...,
        min_length=1,
        description="Identifier of the candidate canonical entity.",
    )

    canonical_name: str = Field(
        ...,
        min_length=1,
        description="Canonical name of the candidate entity.",
    )

    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Similarity score between the extracted mention and candidate entity.",
    )


class EntityResolutionResponse(BaseModel):
    """
    Structured result of the entity resolution stage.
    """

    selected_entity_id: str | None = Field(
        default=None,
        description="Selected canonical entity ID, or null when no reliable match exists.",
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in the selected entity resolution.",
    )

    candidates: list[EntityResolutionCandidate] = Field(
        default_factory=list,
        description="Candidate entities considered during resolution.",
    )

    needs_review: bool = Field(
        default=False,
        description="Whether human review is recommended.",
    )

    explanation: str = Field(
        ...,
        min_length=1,
        description="Short explanation of the entity resolution decision.",
    )


class FactComparisonResponse(BaseModel):
    """
    Structured result of comparing two normalized facts.
    """

    relationship_type: str = Field(
        ...,
        description=(
            "One of: corroborates, contradicts, reconciles, unrelated."
        ),
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in the relationship classification.",
    )

    explanation: str = Field(
        ...,
        min_length=1,
        description="Explanation of why the two facts have this relationship.",
    )

    context_factors: list[str] = Field(
        default_factory=list,
        description=(
            "Relevant contextual factors such as time period, scope, "
            "unit conversion, methodology, or definition differences."
        ),
    )

    needs_review: bool = Field(
        default=False,
        description="Whether human review is recommended.",
    )

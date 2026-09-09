from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from app.core.exceptions import FactExtractionError
from app.domain.models.chunk import Chunk
from app.domain.models.document import Document
from app.domain.models.fact import Fact
from app.domain.services.entity_resolution_service import EntityResolutionService
from app.domain.value_objects.evidence_ref import EvidenceRef
from app.domain.value_objects.temporal_scope import TemporalScope
from app.infra.llm.client import LLMClient
from app.infra.llm.schemas import (
    ExtractedFact,
    FactExtractionResponse,
)


PROMPT_FILE = (
    Path(__file__).resolve().parents[2]
    / "infra"
    / "llm"
    / "prompts"
    / "extract_facts.md"
)


_NUMERIC_PATTERN = re.compile(
    r"""
    (?:
        \b\d+(?:[.,]\d+)*\b
        |
        \b\d+(?:\.\d+)?\s*%
        |
        [$€£₹]\s*\d
        |
        \b\d+(?:\.\d+)?\s*
        (?:million|billion|trillion|thousand|crore|lakh|mn|bn|m|k)
        \b
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_DATE_PATTERN = re.compile(
    r"""
    \b
    (?:
        FY\s*\d{2,4}(?:[-/]\d{2,4})?
        |
        Q[1-4]\s*(?:FY)?\s*\d{2,4}
        |
        19\d{2}
        |
        20\d{2}
        |
        \d{1,2}[-/]\d{1,2}[-/]\d{2,4}
    )
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

_UNIT_PATTERN = re.compile(
    r"""
    \b
    (?:
        percent
        |percentage
        |USD
        |INR
        |EUR
        |GBP
        |million
        |billion
        |trillion
        |crore
        |lakh
        |tonnes?
        |tons?
        |kg
        |kilograms?
        |km
        |kilometers?
        |MW
        |GW
        |employees?
        |customers?
        |units?
    )
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

_FACTUAL_VERB_PATTERN = re.compile(
    r"""
    \b
    (?:
        reported
        |recorded
        |reached
        |generated
        |earned
        |grew
        |growth
        |increased
        |decreased
        |declined
        |rose
        |fell
        |remained
        |stood
        |accounted
        |represented
        |comprised
        |operated
        |serves?
        |employed
        |produced
        |sold
        |spent
        |invested
        |borrowed
        |owned
        |held
        |achieved
        |estimated
        |projected
        |forecast
        |expects?
        |included
        |contained
        |consisted
        |covered
        |affected
        |supported
        |provided
        |launched
        |acquired
        |merged
        |approved
        |adopted
        |implemented
        |accounted
    )
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

_RELATIONAL_PATTERN = re.compile(
    r"""
    \b
    (?:
        has
        |have
        |had
        |is
        |are
        |was
        |were
        |constitutes?
        |includes?
        |contains?
        |covers?
        |accounts?
        |forms?
        |represents?
    )
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

_BOILERPLATE_PATTERN = re.compile(
    r"""
    \b
    (?:
        table\s+of\s+contents
        |contents
        |acknowledg(?:e)?ments?
        |abbreviations?
        |list\s+of\s+(?:tables|figures|charts|boxes)
        |copyright
        |all\s+rights\s+reserved
        |references?
        |bibliography
        |appendix
        |index
    )
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


@lru_cache(maxsize=1)
def load_extraction_prompt() -> str:
    """
    Load and cache the fact extraction instructions.
    """

    if not PROMPT_FILE.exists():
        raise FactExtractionError(
            f"Extraction prompt file not found: {PROMPT_FILE}"
        )

    try:
        prompt = PROMPT_FILE.read_text(encoding="utf-8")
    except OSError as exc:
        raise FactExtractionError(
            f"Unable to read extraction prompt: {exc}"
        ) from exc

    if not prompt.strip():
        raise FactExtractionError(
            "Extraction prompt file is empty."
        )

    return prompt


def _is_fact_candidate(text: str) -> bool:
    """
    Conservatively determine whether a chunk is worth sending to the LLM.
    """

    normalized = " ".join(text.split())

    if not normalized:
        return False

    if len(normalized) < 40:
        return False

    if _NUMERIC_PATTERN.search(normalized):
        return True

    if _DATE_PATTERN.search(normalized):
        return True

    if _UNIT_PATTERN.search(normalized):
        return True

    if _FACTUAL_VERB_PATTERN.search(normalized):
        return True

    if _RELATIONAL_PATTERN.search(normalized):
        return True

    if _BOILERPLATE_PATTERN.search(normalized):
        return False

    return True


class FactExtractionService:
    """
    Extract source-grounded facts from document chunks.
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        entity_resolution_service: EntityResolutionService | None = None,
    ) -> None:
        self.llm_client = llm_client or LLMClient()
        self.entity_resolution_service = (
            entity_resolution_service or EntityResolutionService()
        )

    def extract_from_chunk(
        self,
        chunk: Chunk,
        document: Document,
    ) -> list[Fact]:
        """
        Extract facts from one document chunk.
        """

        if chunk.document_id != document.id:
            raise FactExtractionError(
                "Chunk document_id does not match the supplied document ID."
            )

        if not chunk.text.strip():
            return []

        if not _is_fact_candidate(chunk.text):
            print(
                f"Skipping non-candidate chunk "
                f"document={document.id} "
                f"page={chunk.page_number} "
                f"chunk={chunk.id}"
            )
            return []

        # Financial/table-like chunks are handled deterministically first.
        # This avoids expensive LLM calls for structured numeric tables.
        if self._looks_like_simple_table(chunk.text):
            table_facts = self._extract_simple_table_facts(
                chunk=chunk,
                document=document,
            )

            if table_facts:
                return table_facts

        system_prompt = load_extraction_prompt()

        user_prompt = self._build_user_prompt(
            chunk=chunk,
            document=document,
        )

        response = self.llm_client.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=FactExtractionResponse,
        )

        facts = self._convert_response_facts(
            response=response,
            chunk=chunk,
            document=document,
        )

        return facts

    def extract_from_chunks(
        self,
        chunks: list[Chunk],
        document: Document,
    ) -> list[Fact]:
        """
        Extract facts from multiple chunks.

        Chunks are processed sequentially here for backward compatibility.
        The worker can use extract_from_chunk_batch() for batched LLM calls.
        """

        facts: list[Fact] = []

        for chunk in chunks:
            facts.extend(
                self.extract_from_chunk(
                    chunk=chunk,
                    document=document,
                )
            )

        return facts

    def extract_from_chunk_batch(
        self,
        chunks: list[Chunk],
        document: Document,
    ) -> list[Fact]:
        """
        Extract facts from multiple chunks using one structured LLM request.

        Every chunk is included with its unique chunk ID. The LLM must return
        that chunk ID inside the evidence object so extracted facts can be
        mapped back to their original source chunk.
        """

        if not chunks:
            return []

        valid_chunks: list[Chunk] = []

        for chunk in chunks:
            if chunk.document_id != document.id:
                raise FactExtractionError(
                    "Chunk document_id does not match the supplied document ID."
                )

            if not chunk.text.strip():
                continue

            if not _is_fact_candidate(chunk.text):
                print(
                    f"Skipping non-candidate chunk "
                    f"document={document.id} "
                    f"page={chunk.page_number} "
                    f"chunk={chunk.id}"
                )
                continue

            valid_chunks.append(chunk)

        if not valid_chunks:
            return []

        system_prompt = load_extraction_prompt()
        user_prompt = self._build_batch_user_prompt(
            chunks=valid_chunks,
            document=document,
        )

        response = self.llm_client.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=FactExtractionResponse,
        )

        chunk_map = {
            chunk.id: chunk
            for chunk in valid_chunks
        }

        facts: list[Fact] = []

        for extracted_fact in response.facts:
            source_chunk = self._find_source_chunk(
                extracted_fact=extracted_fact,
                chunk_map=chunk_map,
            )

            if source_chunk is None:
                print(
                    f"Skipping extracted fact '{extracted_fact.attribute}': "
                    "source chunk could not be determined."
                )
                continue

            try:
                fact = self._convert_extracted_fact(
                    extracted_fact=extracted_fact,
                    chunk=source_chunk,
                    document=document,
                )
            except FactExtractionError as exc:
                print(
                    f"Skipping unsupported extracted fact "
                    f"'{extracted_fact.attribute}': {exc}"
                )
                continue

            if len(facts) >= 5 * len(valid_chunks):
                break

            if not any(
                existing.attribute == fact.attribute
                and existing.value == fact.value
                and existing.entity_id == fact.entity_id
                and existing.fact_type_id == fact.fact_type_id
                and existing.evidence == fact.evidence
                for existing in facts
            ):
                facts.append(fact)

        return facts

    @staticmethod
    def _find_source_chunk(
        *,
        extracted_fact: ExtractedFact,
        chunk_map: dict[str, Chunk],
    ) -> Chunk | None:
        """
        Determine which input chunk produced an extracted fact.

        Prefer the model-provided chunk_id. If it is missing or invalid,
        fall back to page number + quoted evidence text so that extraction
        remains grounded even when the LLM produces an unreliable chunk ID.
        """

        chunks = list(chunk_map.values())

        for evidence in extracted_fact.evidence:
            # 1. Prefer the exact chunk_id supplied by the model.
            if evidence.chunk_id:
                source_chunk = chunk_map.get(evidence.chunk_id)

                if source_chunk is not None:
                    return source_chunk

            # 2. Fall back to page number + quoted text.
            quoted_text = evidence.quoted_text.strip()

            if not quoted_text:
                continue

            page_chunks = [
                chunk
                for chunk in chunks
                if chunk.page_number == evidence.page_number
            ]

            for chunk in page_chunks:
                if quoted_text in chunk.text:
                    return chunk

            # 3. Handle minor whitespace differences in model output.
            normalized_quote = " ".join(quoted_text.split())

            if normalized_quote:
                for chunk in page_chunks:
                    normalized_chunk_text = " ".join(chunk.text.split())

                    if normalized_quote in normalized_chunk_text:
                        return chunk

        return None

    @staticmethod
    def _build_user_prompt(
        *,
        chunk: Chunk,
        document: Document,
    ) -> str:
        """
        Build the extraction prompt for a single source chunk.
        """

        return f"""
Document ID: {document.id}
Document filename: {document.filename}

Source page: {chunk.page_number}
Source chunk ID: {chunk.id}
Source chunk character range: {chunk.char_start} - {chunk.char_end}

Extract ONLY meaningful, distinct facts from the following source text.

Rules:
- Return at most 5 facts.
- Never repeat the same fact.
- Do NOT return a document title, standalone company name, or repeated heading as a fact.
- Prefer factual statements containing meaningful attributes, values, metrics, relationships, or descriptions.
- If there are no meaningful facts, return an empty facts list.

--- SOURCE TEXT START ---
{chunk.text}
--- SOURCE TEXT END ---

For every extracted fact:
- provide the entity,
- provide a reusable fact type,
- provide a normalized attribute,
- provide the value,
- provide the unit when applicable,
- provide temporal scope when available,
- provide exact quoted evidence,
- provide the page number,
- provide the source chunk ID,
- provide confidence between 0 and 1.

The quoted evidence must be copied exactly from the source text.
"""

    @staticmethod
    def _build_batch_user_prompt(
        *,
        chunks: list[Chunk],
        document: Document,
    ) -> str:
        """
        Build one extraction prompt containing multiple source chunks.
        """

        sections: list[str] = []

        for index, chunk in enumerate(chunks, start=1):
            sections.append(
                f"""
=== SOURCE CHUNK {index} ===
Document ID: {document.id}
Document filename: {document.filename}

Source page: {chunk.page_number}
Source chunk ID: {chunk.id}
Source chunk character range: {chunk.char_start} - {chunk.char_end}

--- SOURCE TEXT START ---
{chunk.text}
--- SOURCE TEXT END ---
"""
            )

        return f"""
Document ID: {document.id}
Document filename: {document.filename}

You are extracting facts from MULTIPLE independent source chunks.

Extract ONLY meaningful, distinct facts explicitly supported by the
provided source text.

Rules:
- Return at most 5 facts per source chunk.
- Never repeat the same fact.
- Do NOT return a document title, standalone company name, or repeated heading.
- Do NOT combine information from different chunks into a new fact.
- Every fact MUST belong to exactly one source chunk.
- Prefer factual statements containing meaningful attributes, values,
  metrics, relationships, or descriptions.
- If a chunk contains no meaningful facts, return no facts for that chunk.
- Do not use outside knowledge.
- Preserve numerical values, units, dates, and temporal context exactly.

For every extracted fact:
- provide the entity,
- provide a reusable fact type,
- provide a normalized attribute,
- provide the value,
- provide the unit when applicable,
- provide temporal scope when available,
- provide exact quoted evidence,
- provide the page number,
- provide the source chunk ID,
- provide confidence between 0 and 1.

IMPORTANT:
- The evidence.chunk_id MUST exactly match one of the Source chunk IDs
  provided below.
- The evidence.page_number MUST match the page containing the quote.
- The quoted evidence MUST be copied exactly from that source chunk.
- Never invent a chunk ID.
- If you cannot provide exact evidence, do not return the fact.

{''.join(sections)}
"""

    @staticmethod
    def _looks_like_simple_table(text: str) -> bool:
        """Return True when the chunk contains multiple quarter periods."""

        period_pattern = re.compile(
            r"\b(?:Q[1-4]\s*(?:FY)?\s*\d{2,4}|FY\s*\d{2,4})\b",
            re.IGNORECASE,
        )

        return len(period_pattern.findall(text)) >= 2

    def _extract_simple_table_facts(
        self,
        *,
        chunk: Chunk,
        document: Document,
    ) -> list[Fact]:
        """Extract simple multi-period numerical tables deterministically."""

        text = chunk.text

        period_pattern = re.compile(
            r"\bQ[1-4]\s*(?:FY)?\s*\d{2,4}\b",
            re.IGNORECASE,
        )
        period_matches = list(period_pattern.finditer(text))

        if len(period_matches) < 2:
            return []

        # Use the first contiguous group of period headers.
        # PDF extraction may place each period and value on its own line.
        periods = [match.group(0) for match in period_matches]
        header_end = period_matches[-1].end()

        number_pattern = re.compile(
            r"(?<![\w.])(?:\(\s*(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*\)|\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?![\w.])"
        )

        # Find an explicitly named entity before the period header.
        entity_name = None

        for line in text[:period_matches[0].start()].splitlines():
            candidate = line.strip()

            if (
                candidate
                and len(candidate) >= 3
                and not re.search(r"\d", candidate)
                and not candidate.startswith(("₹", "$", "€", "£"))
                and candidate.lower() not in {
                    "quarterly and full year financial performance",
                }
            ):
                entity_name = candidate

        if not entity_name:
            return []

        entity = self.entity_resolution_service.resolve(
            mention=entity_name,
            entity_type="company",
        )

        facts: list[Fact] = []
        seen_facts: set[tuple[str, str, str, object, str | None]] = set()

        lines = [
            line.strip()
            for line in text[header_end:].splitlines()
            if line.strip()
        ]

        # Vertical PDF table layout:
        # row label followed by one value per line for each period.
        # Handle vertical PDF tables where each value is on its own line.
        for index, line in enumerate(lines):
            attribute = self._normalize_table_attribute(line)

            if attribute:
                value_lines = []
                value_matches = []

                for offset in range(1, len(periods) + 1):
                    if index + offset >= len(lines):
                        break

                    candidate = lines[index + offset]
                    matches = list(number_pattern.finditer(candidate))

                    if len(matches) != 1:
                        break

                    value_lines.append(candidate)
                    value_matches.append(matches[0].group(0))

                if len(value_matches) == len(periods):
                    unit = self._infer_table_unit(text, attribute)

                    for period, value_line, raw_value in zip(
                        periods,
                        value_lines,
                        value_matches,
                    ):
                        try:
                            cleaned_value = raw_value.replace(",", "").strip()

                            is_negative = (
                                cleaned_value.startswith("(")
                                and cleaned_value.endswith(")")
                            )

                            cleaned_value = cleaned_value.strip("()")

                            value = float(cleaned_value)

                            if is_negative:
                                value = -value

                            if value.is_integer():
                                value = int(value)
                        except ValueError:
                            continue

                        fact_key = (
                            entity.id,
                            attribute,
                            period,
                            value,
                            unit,
                        )

                        if fact_key in seen_facts:
                            continue

                        seen_facts.add(fact_key)

                        line_start = text.find(value_line, header_end)

                        if line_start < 0:
                            continue

                        facts.append(
                            Fact(
                                id=f"fact-{uuid4().hex}",
                                document_id=document.id,
                                chunk_id=chunk.id,
                                entity_id=entity.id,
                                fact_type_id="type:financial_metric",
                                attribute=attribute,
                                value=value,
                                unit=unit,
                                temporal_scope=TemporalScope(
                                    period_label=period,
                                    granularity="quarter"
                                    if period.upper().startswith("Q")
                                    else "year",
                                ),
                                evidence=[
                                    EvidenceRef(
                                        document_id=document.id,
                                        page_number=chunk.page_number,
                                        chunk_id=chunk.id,
                                        quoted_text=value_line,
                                        char_start=line_start,
                                        char_end=line_start + len(value_line),
                                    )
                                ],
                                confidence=0.90,
                                needs_review=False,
                                extraction_method="deterministic_table",
                                raw_extraction={
                                    "row_label": line,
                                    "period": period,
                                    "source": "deterministic_vertical_table_parser",
                                },
                            )
                        )

                    if facts:
                        continue

            number_matches = list(number_pattern.finditer(line))

            # PDF/table extraction often places the row label and its
            # numerical cells on separate lines.
            if len(number_matches) == len(periods):
                row_label = line[:number_matches[0].start()].strip()
                value_line = line
            elif (
                len(number_matches) == 0
                and index + 1 < len(lines)
            ):
                next_line = lines[index + 1]
                next_number_matches = list(
                    number_pattern.finditer(next_line)
                )

                if len(next_number_matches) != len(periods):
                    continue

                row_label = line
                value_line = next_line
                number_matches = next_number_matches
            else:
                continue

            if not row_label:
                continue

            attribute = self._normalize_table_attribute(row_label)

            if not attribute:
                continue

            line_start = text.find(value_line, header_end)

            if line_start < 0:
                continue

            for period, number_match in zip(periods, number_matches):
                raw_value = number_match.group(0)

                try:
                    value = float(raw_value.replace(",", ""))
                    if value.is_integer():
                        value = int(value)
                except ValueError:
                    continue

                unit = self._infer_table_unit(text, attribute)

                fact_key = (
                    entity.id,
                    attribute,
                    period,
                    value,
                    unit,
                )

                if fact_key in seen_facts:
                    continue

                seen_facts.add(fact_key)

                facts.append(
                    Fact(
                        id=f"fact-{uuid4().hex}",
                        document_id=document.id,
                        chunk_id=chunk.id,
                        entity_id=entity.id,
                        fact_type_id="type:financial_metric",
                        attribute=attribute,
                        value=value,
                        unit=unit,
                        temporal_scope=TemporalScope(
                            period_label=period,
                            granularity="quarter",
                        ),
                        evidence=[
                            EvidenceRef(
                                document_id=document.id,
                                page_number=chunk.page_number,
                                chunk_id=chunk.id,
                                quoted_text=value_line,
                                char_start=line_start,
                                char_end=line_start + len(value_line),
                            )
                        ],
                        confidence=0.90,
                        needs_review=False,
                        extraction_method="deterministic_table",
                        raw_extraction={
                            "row_label": row_label,
                            "period": period,
                            "source": "deterministic_table_parser",
                        },
                    )
                )

                if len(facts) >= 5:
                    return facts

        return facts

    @staticmethod
    def _normalize_table_attribute(row_label: str) -> str | None:
        """Normalize a genuine table row label into a reusable attribute."""

        normalized = " ".join(row_label.split()).strip()

        if not normalized:
            return None

        # Numeric values, percentages, currency values, and standalone
        # symbols are table cells, not attribute names.
        if re.fullmatch(
            r"[₹$€£]?\s*[-(]?\s*\d[\d,]*(?:\.\d+)?%?\s*\)?",
            normalized,
        ):
            return None

        # Remove footnote markers such as (1).
        cleaned = re.sub(r"\(\d+\)", "", normalized)
        cleaned = " ".join(cleaned.split()).strip()

        if not cleaned:
            return None

        lowered = cleaned.lower()

        mappings = {
            "revenue for services": "revenue",
            "revenue from services": "revenue",
            "revenue from customers": "revenue",
            "revenue from customers (a+b)": "revenue",
            "total revenue from customers": "revenue",
            "adjusted ebitda": "adjusted_ebitda",
            "ebitda": "ebitda",
            "service ebitda": "service_ebitda",
            "service ebitda margin": "service_ebitda_margin",
            "less: corporate overheads": "corporate_overheads",
            "corp. overheads": "corporate_overheads",
            "corp. overheads (% of revenue)": "corporate_overheads_percent",
            "adjusted ebitda margin": "adjusted_ebitda_margin",
            "net profit": "net_profit",
            "profit after tax": "profit_after_tax",
        }

        if lowered in mappings:
            return mappings[lowered]

        # Do not invent attributes from arbitrary PDF text.
        return None

    @staticmethod
    def _infer_table_unit(
        text: str,
        attribute: str | None = None,
    ) -> str | None:
        """Infer the unit from the row when possible."""

        if attribute and "margin" in attribute.lower():
            return "%"

        if re.search(r"[₹]\s*(?:Cr|crore)\b", text, re.IGNORECASE):
            return "INR crore"

        if re.search(r"\bINR\s*(?:Cr|crore)\b", text, re.IGNORECASE):
            return "INR crore"

        if re.search(r"\bUSD\b", text, re.IGNORECASE):
            return "USD"

        if re.search(r"\bEUR\b", text, re.IGNORECASE):
            return "EUR"

        if re.search(r"\bGBP\b", text, re.IGNORECASE):
            return "GBP"

        return None

    def _convert_response_facts(
        self,
        *,
        response: FactExtractionResponse,
        chunk: Chunk,
        document: Document,
    ) -> list[Fact]:
        """
        Convert a single-chunk LLM response into domain facts.
        """

        facts: list[Fact] = []

        for extracted_fact in response.facts:
            try:
                fact = self._convert_extracted_fact(
                    extracted_fact=extracted_fact,
                    chunk=chunk,
                    document=document,
                )
            except FactExtractionError as exc:
                print(
                    f"Skipping unsupported extracted fact "
                    f"'{extracted_fact.attribute}': {exc}"
                )
                continue

            if len(facts) >= 5:
                break

            if not any(
                existing.attribute == fact.attribute
                and existing.value == fact.value
                and existing.entity_id == fact.entity_id
                and existing.fact_type_id == fact.fact_type_id
                and existing.evidence == fact.evidence
                for existing in facts
            ):
                facts.append(fact)

        return facts

    def _convert_extracted_fact(
        self,
        *,
        extracted_fact: ExtractedFact,
        chunk: Chunk,
        document: Document,
    ) -> Fact:
        """
        Convert the LLM boundary schema into the domain Fact model.
        """

        evidence_refs = self._build_evidence_refs(
            extracted_fact=extracted_fact,
            chunk=chunk,
            document=document,
        )

        if not evidence_refs:
            raise FactExtractionError(
                f"Extracted fact '{extracted_fact.attribute}' has no valid evidence."
            )

        temporal_scope = self._convert_temporal_scope(
            extracted_fact.temporal_scope,
        )

        entity = self.entity_resolution_service.resolve(
            mention=extracted_fact.entity_name,
            entity_type=extracted_fact.entity_type,
        )

        return Fact(
            id=f"fact-{uuid4().hex}",
            document_id=document.id,
            chunk_id=chunk.id,
            entity_id=entity.id,
            fact_type_id=self._temporary_fact_type_id(
                extracted_fact.fact_type_name,
            ),
            attribute=extracted_fact.attribute.strip(),
            value=self._normalize_extracted_value(
                extracted_fact.value,
            ),
            unit=(
                extracted_fact.unit.strip()
                if extracted_fact.unit
                else None
            ),
            temporal_scope=temporal_scope,
            evidence=evidence_refs,
            confidence=extracted_fact.confidence,
            needs_review=(
                extracted_fact.confidence < 0.8
                or bool(extracted_fact.extraction_notes)
            ),
            extraction_method="llm",
            raw_extraction=extracted_fact.model_dump(
                mode="json",
            ),
        )

    @staticmethod
    def _normalize_extracted_value(value: str):
        """
        Convert a string-based fact value into a useful Python value.
        """

        if not isinstance(value, str):
            return value

        normalized = value.strip()

        if not normalized:
            return normalized

        try:
            parsed = json.loads(normalized)
        except json.JSONDecodeError:
            parsed = None

        if parsed is not None:
            return parsed

        return normalized

    @staticmethod
    def _build_evidence_refs(
        *,
        extracted_fact: ExtractedFact,
        chunk: Chunk,
        document: Document,
    ) -> list[EvidenceRef]:
        """
        Convert LLM evidence into domain EvidenceRef objects.

        Evidence is accepted only when:
        - the page matches the source chunk,
        - the quote is non-empty,
        - the quote actually exists in the source chunk.
        """

        evidence_refs: list[EvidenceRef] = []

        for evidence in extracted_fact.evidence:
            quoted_text = evidence.quoted_text.strip()

            if not quoted_text:
                continue

            if evidence.page_number != chunk.page_number:
                continue

            # Deterministic grounding check for extracted numerical values.
            # The evidence quote must contain the same numeric information
            # as the extracted value, allowing formatting differences such
            # as "7,225" vs "7225".
            extracted_value = str(extracted_fact.value).strip()

            if _NUMERIC_PATTERN.search(extracted_value):
                extracted_numbers = re.findall(
                    r"\d+(?:[.,]\d+)*",
                    extracted_value,
                )

                quote_numbers = re.findall(
                    r"\d+(?:[.,]\d+)*",
                    quoted_text,
                )

                normalized_extracted_numbers = {
                    number.replace(",", "")
                    for number in extracted_numbers
                }
                normalized_quote_numbers = {
                    number.replace(",", "")
                    for number in quote_numbers
                }

                if not normalized_extracted_numbers.issubset(
                    normalized_quote_numbers
                ):
                    continue

            # First try an exact match.
            quote_position = chunk.text.find(quoted_text)

            if quote_position != -1:
                matched_text = quoted_text
                match_start = quote_position
                match_end = quote_position + len(quoted_text)

            else:
                # Fall back to whitespace-normalized matching.
                # This handles PDF/LLM differences such as line breaks
                # or multiple spaces while still requiring the text
                # to exist in the actual source chunk.
                normalized_quote = " ".join(quoted_text.split())

                if not normalized_quote:
                    continue

                quote_pattern = re.escape(normalized_quote).replace(
                    r"\ ",
                    r"\s+",
                )

                match = re.search(
                    quote_pattern,
                    chunk.text,
                )

                if match is None:
                    continue

                match_start = match.start()
                match_end = match.end()
                matched_text = chunk.text[match_start:match_end]

            char_start = (
                chunk.char_start + match_start
                if chunk.char_start is not None
                else match_start
            )

            char_end = (
                chunk.char_start + match_end
                if chunk.char_start is not None
                else match_end
            )

            evidence_refs.append(
                EvidenceRef(
                    document_id=document.id,
                    page_number=chunk.page_number,
                    chunk_id=chunk.id,
                    quoted_text=matched_text,
                    char_start=char_start,
                    char_end=char_end,
                )
            )

        return evidence_refs

    @staticmethod
    def _convert_temporal_scope(
        temporal_scope,
    ) -> TemporalScope | None:
        """
        Convert the LLM temporal representation into the domain model.
        """

        if temporal_scope is None:
            return None

        from datetime import date

        start_date = None
        end_date = None

        if temporal_scope.start_date:
            try:
                start_date = date.fromisoformat(
                    temporal_scope.start_date,
                )
            except ValueError:
                pass

        if temporal_scope.end_date:
            try:
                end_date = date.fromisoformat(
                    temporal_scope.end_date,
                )
            except ValueError:
                pass

        return TemporalScope(
            start_date=start_date,
            end_date=end_date,
            period_label=temporal_scope.period_label,
            granularity=temporal_scope.granularity,
        )

    @staticmethod
    def _temporary_entity_id(entity_name: str) -> str:
        """
        Create a temporary entity key.

        This method is retained for backward compatibility.
        """

        normalized = " ".join(entity_name.lower().split())

        return f"mention:{normalized}"

    @staticmethod
    def _temporary_fact_type_id(fact_type_name: str) -> str:
        """
        Create a temporary fact-type key.

        The schema registry will later map this to a persistent
        versioned fact type.
        """

        normalized = " ".join(fact_type_name.lower().split())

        return f"type:{normalized}"


def get_extraction_service(
    llm_client: LLMClient | None = None,
    entity_resolution_service: EntityResolutionService | None = None,
) -> FactExtractionService:
    """
    Return a fact extraction service.
    """

    return FactExtractionService(
        llm_client=llm_client,
        entity_resolution_service=entity_resolution_service,
    )
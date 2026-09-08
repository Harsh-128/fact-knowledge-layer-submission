from __future__ import annotations

from app.core.exceptions import FactComparisonError
from app.domain.models.fact import Fact
from app.domain.models.relationship import Relationship, RelationshipType
from app.infra.llm.client import LLMClient
from app.infra.llm.schemas import FactComparisonResponse


class FactComparisonService:
    """
    Compare two facts and determine their semantic relationship.

    The comparison service deliberately separates:
    - deterministic checks for obviously unrelated facts
    - LLM reasoning for semantic comparison

    This prevents the LLM from being asked to compare facts that clearly
    describe different entities or attributes.
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.llm_client = llm_client

    def compare(
        self,
        source_fact: Fact,
        target_fact: Fact,
    ) -> Relationship:
        """
        Compare two facts and return a relationship.

        Facts describing different entities or different attributes are
        treated as unrelated without making an unnecessary LLM call.
        """

        self._validate_facts(source_fact, target_fact)

        if source_fact.id == target_fact.id:
            raise FactComparisonError(
                "A fact cannot be compared with itself."
            )

        if not self._same_comparison_subject(source_fact, target_fact):
            return self._build_relationship(
                source_fact=source_fact,
                target_fact=target_fact,
                relationship_type=RelationshipType.UNRELATED,
                confidence=1.0,
                explanation=(
                    "The facts do not describe the same entity, fact type, "
                    "or attribute and therefore should not be compared."
                ),
                needs_review=False,
            )

        if self.llm_client is None:
            raise FactComparisonError(
                "An LLM client is required for semantic fact comparison."
            )

        response = self._compare_with_llm(
            source_fact,
            target_fact,
        )

        relationship_type = self._parse_relationship_type(
            response.relationship_type
        )

        confidence = max(
            0.0,
            min(1.0, response.confidence),
        )

        needs_review = (
            response.needs_review
            or confidence < 0.75
            or source_fact.needs_review
            or target_fact.needs_review
        )

        return self._build_relationship(
            source_fact=source_fact,
            target_fact=target_fact,
            relationship_type=relationship_type,
            confidence=confidence,
            explanation=response.explanation,
            needs_review=needs_review,
        )

    def compare_many(
        self,
        facts: list[Fact],
    ) -> list[Relationship]:
        """
        Compare facts that belong to the same comparison subject.

        Exact duplicate facts are corroborations and do not require an
        LLM call. Ambiguous pairs are delegated to the LLM.
        """

        relationships: list[Relationship] = []

        for index, source_fact in enumerate(facts):
            for target_fact in facts[index + 1 :]:
                if not self._same_comparison_subject(
                    source_fact,
                    target_fact,
                ):
                    continue

                if self._is_exact_duplicate(source_fact, target_fact):
                    relationships.append(
                        self._build_relationship(
                            source_fact=source_fact,
                            target_fact=target_fact,
                            relationship_type=RelationshipType.CORROBORATES,
                            confidence=1.0,
                            explanation=(
                                "The facts have the same entity, attribute, "
                                "value, unit, and temporal scope, so they "
                                "corroborate each other without requiring "
                                "semantic inference."
                            ),
                            needs_review=(
                                source_fact.needs_review
                                or target_fact.needs_review
                            ),
                        )
                    )
                    continue

                relationships.append(
                    self.compare(
                        source_fact,
                        target_fact,
                    )
                )

        return relationships

    @staticmethod
    def _is_exact_duplicate(
        source_fact: Fact,
        target_fact: Fact,
    ) -> bool:
        """
        Detect facts whose structured meaning is already identical.

        This avoids an unnecessary LLM call and prevents the model from
        inventing temporal or unit context for identical facts.
        """

        source_scope = (
            source_fact.temporal_scope.model_dump()
            if source_fact.temporal_scope
            else None
        )
        target_scope = (
            target_fact.temporal_scope.model_dump()
            if target_fact.temporal_scope
            else None
        )

        return (
            source_fact.entity_id == target_fact.entity_id
            and source_fact.attribute.strip().lower()
            == target_fact.attribute.strip().lower()
            and source_fact.fact_type_id == target_fact.fact_type_id
            and source_fact.value == target_fact.value
            and source_fact.unit == target_fact.unit
            and source_scope == target_scope
        )

    def _compare_with_llm(
        self,
        source_fact: Fact,
        target_fact: Fact,
    ) -> FactComparisonResponse:
        """Ask the LLM to semantically compare two compatible facts."""

        system_prompt = self._load_comparison_prompt()

        user_prompt = self._build_comparison_prompt(
            source_fact,
            target_fact,
        )

        try:
            return self.llm_client.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=FactComparisonResponse,
            )
        except Exception as exc:
            raise FactComparisonError(
                f"Fact comparison failed: {exc}"
            ) from exc

    @staticmethod
    def _build_comparison_prompt(
        source_fact: Fact,
        target_fact: Fact,
    ) -> str:
        """Build a source-grounded comparison request."""

        return f"""
Compare the following two facts.

SOURCE FACT
-----------
Fact ID: {source_fact.id}
Entity ID: {source_fact.entity_id}
Fact type ID: {source_fact.fact_type_id}
Attribute: {source_fact.attribute}
Value: {source_fact.value}
Unit: {source_fact.unit}
Temporal scope: {
    source_fact.temporal_scope.model_dump()
    if source_fact.temporal_scope
    else None
}
Evidence: {[e.model_dump_for_storage() for e in source_fact.evidence]}
Confidence: {source_fact.confidence}

TARGET FACT
-----------
Fact ID: {target_fact.id}
Entity ID: {target_fact.entity_id}
Fact type ID: {target_fact.fact_type_id}
Attribute: {target_fact.attribute}
Value: {target_fact.value}
Unit: {target_fact.unit}
Temporal scope: {
    target_fact.temporal_scope.model_dump()
    if target_fact.temporal_scope
    else None
}
Evidence: {[e.model_dump_for_storage() for e in target_fact.evidence]}
Confidence: {target_fact.confidence}

Determine whether the facts:

- corroborate each other,
- genuinely contradict each other,
- can be reconciled because of context such as time, scope, or units,
- or are unrelated.

Pay particular attention to temporal scope and measurement units.
Do not call two facts contradictory merely because their numerical
values differ.

Return only the structured comparison response.
"""

    @staticmethod
    def _load_comparison_prompt() -> str:
        """
        Load the comparison prompt.

        Kept as a separate method so prompt loading can later be replaced
        with a prompt registry or versioned prompt store.
        """

        from pathlib import Path

        prompt_file = (
            Path(__file__).resolve().parents[2]
            / "infra"
            / "llm"
            / "prompts"
            / "compare_facts.md"
        )

        if not prompt_file.exists():
            raise FactComparisonError(
                f"Comparison prompt not found: {prompt_file}"
            )

        try:
            prompt = prompt_file.read_text(
                encoding="utf-8"
            )
        except OSError as exc:
            raise FactComparisonError(
                f"Unable to read comparison prompt: {exc}"
            ) from exc

        if not prompt.strip():
            raise FactComparisonError(
                "Comparison prompt file is empty."
            )

        return prompt

    @staticmethod
    def _same_comparison_subject(
        source_fact: Fact,
        target_fact: Fact,
    ) -> bool:
        """
        Determine whether two facts are candidates for comparison.

        Entity and attribute/fact-type identity are required before
        semantic comparison.
        """

        if source_fact.entity_id != target_fact.entity_id:
            return False

        source_attribute = source_fact.attribute.strip().lower()
        target_attribute = target_fact.attribute.strip().lower()

        if source_attribute != target_attribute:
            return False

        if (
            source_fact.fact_type_id
            and target_fact.fact_type_id
            and source_fact.fact_type_id != target_fact.fact_type_id
        ):
            return False

        return True

    @staticmethod
    def _parse_relationship_type(
        relationship_type: str,
    ) -> RelationshipType:
        """Convert the LLM's relationship string to the domain enum."""

        normalized = relationship_type.strip().lower()

        aliases = {
            "corroborate": RelationshipType.CORROBORATES,
            "corroborates": RelationshipType.CORROBORATES,
            "support": RelationshipType.CORROBORATES,
            "supports": RelationshipType.CORROBORATES,
            "contradict": RelationshipType.CONTRADICTS,
            "contradicts": RelationshipType.CONTRADICTS,
            "conflict": RelationshipType.CONTRADICTS,
            "conflicts": RelationshipType.CONTRADICTS,
            "reconcile": RelationshipType.RECONCILES,
            "reconciles": RelationshipType.RECONCILES,
            "reconciled": RelationshipType.RECONCILES,
            "unrelated": RelationshipType.UNRELATED,
            "none": RelationshipType.UNRELATED,
        }

        parsed = aliases.get(normalized)

        if parsed is None:
            raise FactComparisonError(
                f"Unsupported relationship type returned by LLM: "
                f"{relationship_type!r}"
            )

        return parsed

    @staticmethod
    def _build_relationship(
        *,
        source_fact: Fact,
        target_fact: Fact,
        relationship_type: RelationshipType,
        confidence: float,
        explanation: str,
        needs_review: bool,
    ) -> Relationship:
        """Construct a domain relationship object."""

        return Relationship(
            id=f"relationship:{source_fact.id}:{target_fact.id}",
            source_fact_id=source_fact.id,
            target_fact_id=target_fact.id,
            relationship_type=relationship_type,
            confidence=confidence,
            explanation=explanation,
            evidence=[],
            needs_review=needs_review,
        )

    @staticmethod
    def _validate_facts(
        source_fact: Fact,
        target_fact: Fact,
    ) -> None:
        """Validate the minimum data required for comparison."""

        if not source_fact.id:
            raise FactComparisonError(
                "Source fact must have an ID."
            )

        if not target_fact.id:
            raise FactComparisonError(
                "Target fact must have an ID."
            )

        if not source_fact.attribute.strip():
            raise FactComparisonError(
                "Source fact must have an attribute."
            )

        if not target_fact.attribute.strip():
            raise FactComparisonError(
                "Target fact must have an attribute."
            )

    def is_comparable(
        self,
        source_fact: Fact,
        target_fact: Fact,
    ) -> bool:
        """Return whether two facts are candidates for comparison."""

        return self._same_comparison_subject(
            source_fact,
            target_fact,
        )


def get_comparison_service(
    llm_client: LLMClient | None = None,
) -> FactComparisonService:
    """Create a fact comparison service."""

    return FactComparisonService(
        llm_client=llm_client,
    )

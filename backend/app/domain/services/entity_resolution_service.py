from __future__ import annotations

import re
from uuid import uuid4

from app.domain.models.entity import Entity
from app.infra.db.repositories.entity_repo import EntityRepository
from app.infra.llm.client import LLMClient
from app.infra.llm.schemas import (
    EntityResolutionCandidate,
    EntityResolutionResponse,
)


class EntityResolutionService:
    """
    Resolve document entity mentions to canonical entities.

    Resolution happens in stages:

    1. Exact canonical-name match.
    2. Exact alias match.
    3. Normalized-name match.
    4. LLM-assisted resolution when deterministic matching is
       insufficient.
    5. Create a new entity when no reliable match exists.

    When an EntityRepository is supplied, canonical entities are
    persisted in PostgreSQL so that entity resolution works across
    chunks and documents. Without a repository, the service keeps
    the original in-memory behavior, which is useful for isolated
    tests.
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        entity_repository: EntityRepository | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.entity_repository = entity_repository
        self._entities: dict[str, Entity] = {}

    def register_entity(
        self,
        canonical_name: str,
        entity_type: str = "unknown",
        aliases: list[str] | None = None,
        description: str | None = None,
    ) -> Entity:
        """
        Register a canonical entity.

        If an equivalent entity already exists, return the existing one.

        When a repository is configured, the entity is persisted in
        PostgreSQL.
        """

        normalized_name = self._normalize_name(canonical_name)

        if not normalized_name:
            raise ValueError("canonical_name cannot be empty.")

        existing = self.find_exact(normalized_name)

        if existing is not None:
            for alias in aliases or []:
                self.add_alias(existing.id, alias)

            return existing

        entity = Entity(
            id=f"entity-{uuid4().hex}",
            canonical_name=canonical_name.strip(),
            entity_type=entity_type.strip() or "unknown",
            aliases=[],
            description=description,
        )

        for alias in aliases or []:
            entity.add_alias(alias)

        if self.entity_repository is not None:
            persisted_entity = self.entity_repository.create(entity)
            self._entities[persisted_entity.id] = persisted_entity
            return persisted_entity

        self._entities[entity.id] = entity

        return entity

    def resolve(
        self,
        mention: str,
        entity_type: str = "unknown",
    ) -> Entity:
        """
        Resolve an entity mention to a canonical entity.

        Deterministic matching is preferred because it is cheaper,
        faster, and easier to audit than an LLM call.
        """

        normalized_mention = self._normalize_name(mention)

        if not normalized_mention:
            raise ValueError("Entity mention cannot be empty.")

        exact_match = self.find_exact(normalized_mention)

        if exact_match is not None:
            return exact_match

        # Check the persistent database using the original mention.
        # This avoids scanning the complete entity table for exact matches.
        if self.entity_repository is not None:
            database_exact_match = (
                self.entity_repository.get_by_canonical_name(
                    mention.strip(),
                )
            )

            if database_exact_match is not None:
                self._entities[database_exact_match.id] = database_exact_match
                return database_exact_match

        alias_match = self._find_alias(normalized_mention)

        if alias_match is not None:
            return alias_match

        normalized_match = self._find_normalized_match(
            normalized_mention,
            entity_type,
        )

        if normalized_match is not None:
            self.add_alias(
                normalized_match.id,
                mention,
            )
            return normalized_match

        # Without an LLM, safely create a new entity rather than
        # incorrectly merging two different real-world entities.
        return self.register_entity(
            canonical_name=mention,
            entity_type=entity_type,
        )

    def resolve_with_llm(
        self,
        mention: str,
        entity_type: str,
        candidates: list[Entity],
        context: str = "",
    ) -> EntityResolutionResponse:
        """
        Ask the LLM to choose among candidate canonical entities.

        This method is intentionally separate from deterministic
        resolution so callers can decide when an LLM tie-break is
        worth the additional cost.
        """

        if self.llm_client is None:
            raise ValueError(
                "An LLM client is required for LLM-assisted resolution."
            )

        candidate_data = [
            {
                "entity_id": entity.id,
                "canonical_name": entity.canonical_name,
                "entity_type": entity.entity_type,
                "aliases": entity.aliases,
            }
            for entity in candidates
        ]

        system_prompt = """
You are an entity resolution system.

Determine whether an extracted entity mention refers to one of the
candidate canonical entities.

Rules:
1. Prefer an exact or clearly equivalent entity.
2. Do not merge entities merely because their names are similar.
3. Consider entity type and supplied context.
4. If no candidate is reliable, return null.
5. Be conservative when evidence is insufficient.
"""

        user_prompt = f"""
Entity mention:
{mention}

Entity type:
{entity_type}

Context:
{context}

Candidate canonical entities:
{candidate_data}

Return the best candidate only when the evidence supports the match.
"""

        return self.llm_client.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=EntityResolutionResponse,
        )

    def find_exact(self, normalized_name: str) -> Entity | None:
        """
        Find an entity by normalized canonical name.

        The in-memory cache is checked first. When a repository is
        configured, PostgreSQL is then queried so entities created by
        previous chunks or documents can also be resolved.
        """

        for entity in self._entities.values():
            if self._normalize_name(entity.canonical_name) == normalized_name:
                return entity

        if self.entity_repository is not None:
            # The repository stores the original canonical name, so
            # first try an exact database lookup. If normalization was
            # required, the normalized-match stage below can handle it.
            for entity in self.entity_repository.list_entities(limit=1000):
                if self._normalize_name(entity.canonical_name) == normalized_name:
                    self._entities[entity.id] = entity
                    return entity

        return None

    def get_by_id(self, entity_id: str) -> Entity | None:
        """Return an entity by its ID."""

        entity = self._entities.get(entity_id)

        if entity is not None:
            return entity

        if self.entity_repository is not None:
            entity = self.entity_repository.get_by_id(entity_id)

            if entity is not None:
                self._entities[entity.id] = entity

            return entity

        return None

    def list_entities(self) -> list[Entity]:
        """
        Return all registered canonical entities.

        When a repository is configured, return the persisted entities.
        """

        if self.entity_repository is not None:
            entities = self.entity_repository.list_entities(
                limit=1000,
            )

            for entity in entities:
                self._entities[entity.id] = entity

            return entities

        return list(self._entities.values())

    def add_alias(
        self,
        entity_id: str,
        alias: str,
    ) -> Entity:
        """Add an alias to an existing canonical entity."""

        entity = self.get_by_id(entity_id)

        if entity is None:
            raise KeyError(
                f"Entity not found: {entity_id}"
            )

        if not alias.strip():
            return entity

        if self.entity_repository is not None:
            updated_entity = self.entity_repository.add_alias(
                entity_id,
                alias,
            )

            self._entities[updated_entity.id] = updated_entity

            return updated_entity

        entity.add_alias(alias)

        return entity

    def _find_alias(self, normalized_mention: str) -> Entity | None:
        """Find an entity whose aliases match the mention."""

        for entity in self._entities.values():
            for alias in entity.aliases:
                if self._normalize_name(alias) == normalized_mention:
                    return entity

        if self.entity_repository is not None:
            # First use PostgreSQL's JSONB containment lookup for an
            # exact alias. The normalized in-memory check above handles
            # entities already loaded into this service.
            for entity in self.entity_repository.find_by_alias(
                normalized_mention,
            ):
                self._entities[entity.id] = entity
                return entity

            # Stored aliases may preserve punctuation/capitalization.
            # Fall back to the broader scan only when the exact JSONB
            # lookup did not find one.
            for entity in self.entity_repository.list_entities(limit=1000):
                for alias in entity.aliases:
                    if self._normalize_name(alias) == normalized_mention:
                        self._entities[entity.id] = entity
                        return entity

        return None

    def _find_normalized_match(
        self,
        normalized_mention: str,
        entity_type: str,
    ) -> Entity | None:
        """
        Find safe normalized variants.

        Examples:
        - "Delhivery Limited" -> "delhivery"
        - "DELHIVERY LTD." -> "delhivery"
        """

        mention_core = self._strip_legal_suffix(normalized_mention)

        entities = self.list_entities()

        for entity in entities:
            if (
                entity_type != "unknown"
                and entity.entity_type != "unknown"
                and entity.entity_type != entity_type
            ):
                continue

            canonical_core = self._strip_legal_suffix(
                self._normalize_name(entity.canonical_name)
            )

            if mention_core == canonical_core:
                return entity

        return None

    @staticmethod
    def _normalize_name(name: str) -> str:
        """
        Normalize an entity mention for comparison.
        """

        normalized = name.strip().lower()

        normalized = normalized.replace("&", " and ")

        normalized = re.sub(
            r"[^a-z0-9\s]",
            " ",
            normalized,
        )

        normalized = re.sub(
            r"\s+",
            " ",
            normalized,
        )

        return normalized.strip()

    @staticmethod
    def _strip_legal_suffix(name: str) -> str:
        """
        Remove common legal suffixes for safe company-name matching.
        """

        suffix_pattern = re.compile(
            r"\b("
            r"limited|"
            r"ltd|"
            r"llp|"
            r"incorporated|"
            r"inc|"
            r"corporation|"
            r"corp|"
            r"company|"
            r"co"
            r")\b$"
        )

        return suffix_pattern.sub(
            "",
            name,
        ).strip()

from __future__ import annotations

import json
import time
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError
from app.infra.llm.schemas import ExtractedFact

from app.config import settings
from app.core.exceptions import FactExtractionError

from json_repair import repair_json


T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """
    Provider-agnostic wrapper around the application's LLM providers.

    Supported providers:
    - Ollama
    - Gemini
    - OpenAI

    The rest of the application only depends on this abstraction.
    """

    def __init__(
        self,
        provider: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.provider = (
            provider if provider is not None else settings.llm_provider
        ).lower()

        self.api_key = api_key

        if self.provider == "ollama":
            self.model = model or settings.ollama_model
        elif self.provider == "gemini":
            self.model = model or settings.gemini_model
            self.api_key = (
                api_key
                if api_key is not None
                else settings.gemini_api_key
            )
        elif self.provider == "openai":
            self.model = model or settings.openai_model
            self.api_key = (
                api_key
                if api_key is not None
                else settings.openai_api_key
            )
        else:
            raise FactExtractionError(
                f"Unsupported LLM provider: {self.provider}"
            )

        self._gemini_client = None
        self._openai_client = None

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        """
        Generate a structured response validated against a Pydantic model.
        """

        if self.provider == "ollama":
            return self._generate_ollama(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=response_model,
            )

        if self.provider == "gemini":
            return self._generate_gemini(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=response_model,
            )

        if self.provider == "openai":
            return self._generate_openai(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=response_model,
            )

        raise FactExtractionError(
            f"Unsupported LLM provider: {self.provider}"
        )

    # ------------------------------------------------------------------
    # Ollama
    # ------------------------------------------------------------------

    def _generate_ollama(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        """
        Generate a structured response using Ollama's local API.
        """

        url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"

        schema = response_model.model_json_schema()

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            "stream": False,
            "format": schema,
            "options": {
                "temperature": 0,
                "num_ctx": 4096,
                "num_predict": 512,
            },
        }

        max_attempts = 3
        retry_delays = [2, 5]

        for attempt in range(max_attempts):
            try:
                response = httpx.post(
                    url,
                    json=payload,
                    timeout=300.0,
                )

                response.raise_for_status()

                data = response.json()

                content = data["message"]["content"]

                try:
                    parsed_json = json.loads(content)
                except json.JSONDecodeError:
                    repaired_content = repair_json(content)
                    parsed_json = json.loads(repaired_content)

                try:
                    return response_model.model_validate(parsed_json)

                except ValidationError as exc:
                    # Only extraction responses get tolerant item-level validation.
                    # Entity resolution and comparison remain strict.
                    if response_model.__name__ != "FactExtractionResponse":
                        raise

                    raw_facts = parsed_json.get("facts", [])

                    if not isinstance(raw_facts, list):
                        raise

                    valid_facts = []

                    for index, raw_fact in enumerate(raw_facts):
                        try:
                            valid_facts.append(
                                ExtractedFact.model_validate(raw_fact)
                            )
                        except ValidationError as fact_error:
                            print(
                                f"Skipping malformed extracted fact "
                                f"index={index}: {fact_error}"
                            )

                    if not valid_facts:
                        raise exc

                    return response_model(facts=valid_facts)

            except httpx.HTTPError as exc:
                if attempt == max_attempts - 1:
                    raise FactExtractionError(
                        f"Ollama request failed: {exc}"
                    ) from exc

            except (ValueError, KeyError, TypeError) as exc:
                raise FactExtractionError(
                    f"Ollama returned an invalid structured response: {exc}"
                ) from exc

            except Exception as exc:
                raise FactExtractionError(
                    f"Ollama response validation failed: {exc}"
                ) from exc

            delay = retry_delays[attempt]

            print(
                f"Ollama temporary failure "
                f"(attempt {attempt + 1}/{max_attempts}). "
                f"Retrying in {delay}s..."
            )

            time.sleep(delay)

        raise FactExtractionError(
            "Ollama request failed after all retry attempts."
        )

    # ------------------------------------------------------------------
    # Gemini
    # ------------------------------------------------------------------

    def _generate_gemini(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        """
        Generate a structured response using Gemini.

        This preserves the existing Gemini integration as an optional
        provider.
        """

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise FactExtractionError(
                "Google GenAI package is not installed."
            ) from exc

        if not self.api_key:
            raise FactExtractionError(
                "Gemini API key is not configured. "
                "Set GEMINI_API_KEY in the environment or .env file."
            )

        if self._gemini_client is None:
            self._gemini_client = genai.Client(
                api_key=self.api_key
            )

        max_attempts = 4
        retry_delays = [2, 5, 10]

        for attempt in range(max_attempts):
            try:
                response = self._gemini_client.models.generate_content(
                    model=self.model,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        response_mime_type="application/json",
                        response_schema=response_model,
                    ),
                )

                parsed = getattr(response, "parsed", None)

                if parsed is None:
                    raise FactExtractionError(
                        "Gemini returned no valid structured response."
                    )

                if isinstance(parsed, response_model):
                    return parsed

                try:
                    return response_model.model_validate(parsed)
                except Exception as exc:
                    raise FactExtractionError(
                        f"Gemini returned an invalid structured response: {exc}"
                    ) from exc

            except FactExtractionError:
                raise

            except Exception as exc:
                error_text = str(exc).upper()

                transient_error = (
                    "503" in error_text
                    or "UNAVAILABLE" in error_text
                    or "429" in error_text
                    or "RESOURCE_EXHAUSTED" in error_text
                )

                if not transient_error or attempt == max_attempts - 1:
                    raise FactExtractionError(
                        f"Gemini request failed: {exc}"
                    ) from exc

                delay = retry_delays[attempt]

                print(
                    f"Gemini temporary failure "
                    f"(attempt {attempt + 1}/{max_attempts}). "
                    f"Retrying in {delay}s..."
                )

                time.sleep(delay)

        raise FactExtractionError(
            "Gemini request failed after all retry attempts."
        )

    # ------------------------------------------------------------------
    # OpenAI
    # ------------------------------------------------------------------

    def _generate_openai(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        """
        Generate a structured response using an OpenAI-compatible API.

        Works with OpenRouter and other OpenAI-compatible providers.
        """

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise FactExtractionError(
                "OpenAI package is not installed."
            ) from exc

        if not self.api_key:
            raise FactExtractionError(
                "OpenAI API key is not configured. "
                "Set OPENAI_API_KEY in the environment or .env file."
            )

        if self._openai_client is None:
            self._openai_client = OpenAI(
                api_key=self.api_key,
                base_url=settings.openai_base_url,
            )

        schema = response_model.model_json_schema()

        try:
            response = self._openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": response_model.__name__,
                        "strict": True,
                        "schema": schema,
                    },
                },
                temperature=0,
            )

        except Exception as exc:
            raise FactExtractionError(
                f"OpenAI request failed: {exc}"
            ) from exc

        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise FactExtractionError(
                f"OpenAI returned an invalid response structure: {exc}"
            ) from exc

        if not content:
            raise FactExtractionError(
                "OpenAI returned empty structured content."
            )

        try:
            parsed_json = json.loads(content)
        except json.JSONDecodeError:
            try:
                repaired_content = repair_json(content)
                parsed_json = json.loads(repaired_content)
            except Exception as exc:
                raise FactExtractionError(
                    f"OpenAI returned invalid JSON: {exc}"
                ) from exc

        try:
            return response_model.model_validate(parsed_json)

        except ValidationError as exc:
            # Extraction responses get tolerant item-level validation.
            if response_model.__name__ != "FactExtractionResponse":
                raise FactExtractionError(
                    f"OpenAI returned an invalid structured response: {exc}"
                ) from exc

            raw_facts = parsed_json.get("facts", [])

            if not isinstance(raw_facts, list):
                raise FactExtractionError(
                    f"OpenAI returned invalid facts structure: {exc}"
                ) from exc

            valid_facts = []

            for index, raw_fact in enumerate(raw_facts):
                try:
                    valid_facts.append(
                        ExtractedFact.model_validate(raw_fact)
                    )
                except ValidationError as fact_error:
                    print(
                        f"Skipping malformed extracted fact "
                        f"index={index}: {fact_error}"
                    )

            if not valid_facts:
                raise FactExtractionError(
                    f"OpenAI returned no valid facts: {exc}"
                ) from exc

            return response_model(facts=valid_facts)

    @staticmethod
    def _extract_openai_parsed_response(
        response: object,
    ) -> BaseModel | None:
        """
        Extract the parsed Pydantic object from an OpenAI response.
        """

        output = getattr(response, "output", None)

        if not output:
            return None

        for output_item in output:
            if getattr(output_item, "type", None) != "message":
                continue

            for content_item in getattr(
                output_item,
                "content",
                None,
            ) or []:

                if getattr(
                    content_item,
                    "type",
                    None,
                ) != "output_text":
                    continue

                parsed = getattr(
                    content_item,
                    "parsed",
                    None,
                )

                if isinstance(parsed, BaseModel):
                    return parsed

        return None


def get_llm_client() -> LLMClient:
    """
    Return a configured LLM client.
    """

    return LLMClient()
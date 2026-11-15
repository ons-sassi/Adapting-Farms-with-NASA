"""Generate grounded explanations from immutable, precomputed backend results."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Literal

from groq import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.explanation import (
    ExplanationContent,
    ExplanationMetadata,
    ExplanationRequest,
    ExplanationResponse,
)
from app.services.llm.groq_client import GroqNotConfiguredError, create_groq_client
from app.services.llm.prompts import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)
ExplanationCategory = Literal["general", "rotation", "scoring", "risks"]


class ExplanationServiceError(RuntimeError):
    status_code = 502
    public_detail = "Impossible de générer l'explication."


class ExplanationNotConfiguredError(ExplanationServiceError):
    status_code = 503
    public_detail = "Le service d'explication Groq n'est pas configuré."


class ExplanationInputTooLargeError(ExplanationServiceError):
    status_code = 413
    public_detail = "Les résultats fournis dépassent la taille maximale autorisée."


class ExplanationInputError(ExplanationServiceError):
    status_code = 422
    public_detail = "Les résultats fournis ne peuvent pas être sérialisés en JSON."


class ExplanationTimeoutError(ExplanationServiceError):
    status_code = 504
    public_detail = "Le délai d'attente du service Groq est dépassé."


class ExplanationRateLimitError(ExplanationServiceError):
    status_code = 503
    public_detail = "Le service Groq est temporairement limité. Réessayez plus tard."


class InvalidExplanationResponseError(ExplanationServiceError):
    public_detail = "Le service Groq a retourné une réponse invalide."


class ExplanationProviderError(ExplanationServiceError):
    public_detail = "Le fournisseur Groq est temporairement indisponible."


def _json_pointer_value(document: Any, pointer: str) -> Any:
    if not pointer.startswith("/"):
        raise KeyError(pointer)
    value = document
    for raw_segment in pointer[1:].split("/"):
        segment = raw_segment.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict):
            value = value[segment]
        elif isinstance(value, list):
            value = value[int(segment)]
        else:
            raise KeyError(pointer)
    if value is None or value == "" or value == [] or value == {}:
        raise KeyError(pointer)
    return value


def _validate_explanation(content: ExplanationContent, results: dict[str, Any]) -> None:
    narrative_fields = (
        content.summary,
        content.agronomic_analysis,
        content.economic_analysis,
        content.water_analysis,
    )
    list_fields = (
        content.climate_risks,
        content.advantages,
        content.disadvantages,
        content.limitations,
    )
    if any(not value.strip() for value in narrative_fields):
        raise InvalidExplanationResponseError
    if any(any(not item.strip() for item in values) for values in list_fields):
        raise InvalidExplanationResponseError
    for recommendation in content.recommendations:
        if not recommendation.text.strip():
            raise InvalidExplanationResponseError
        if not recommendation.evidence:
            raise InvalidExplanationResponseError
        for pointer in recommendation.evidence:
            try:
                _json_pointer_value(results, pointer)
            except (KeyError, IndexError, TypeError, ValueError):
                raise InvalidExplanationResponseError from None


def _usage_counts(usage: Any) -> dict[str, int] | None:
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        usage = usage.model_dump()
    elif not isinstance(usage, dict):
        return None
    counts = {}
    for source, target in (
        ("prompt_tokens", "prompt_tokens"),
        ("completion_tokens", "completion_tokens"),
        ("total_tokens", "total_tokens"),
    ):
        value = usage.get(source)
        if isinstance(value, int) and not isinstance(value, bool):
            counts[target] = value
    return counts or None


async def explain_results(
    request: ExplanationRequest,
    category: ExplanationCategory = "general",
) -> ExplanationResponse:
    try:
        serialized = json.dumps(
            request.results,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError, RecursionError):
        raise ExplanationInputError from None

    if len(serialized) > settings.groq_max_input_chars:
        raise ExplanationInputTooLargeError

    source_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    try:
        client = create_groq_client()
    except GroqNotConfiguredError:
        raise ExplanationNotConfiguredError from None

    try:
        async with client:
            completion = await client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": build_user_prompt(
                            serialized, request.language, request.detail, category
                        ),
                    },
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "agricultural_explanation",
                        "strict": True,
                        "schema": ExplanationContent.model_json_schema(),
                    },
                },
                max_completion_tokens=settings.groq_max_completion_tokens,
            )
    except APITimeoutError:
        logger.warning("Groq explanation timed out.")
        raise ExplanationTimeoutError from None
    except RateLimitError:
        logger.warning("Groq explanation rate limit reached.")
        raise ExplanationRateLimitError from None
    except APIStatusError as exc:
        logger.warning("Groq explanation request failed with HTTP status %s.", exc.status_code)
        raise ExplanationProviderError from None
    except APIConnectionError:
        logger.warning("Groq explanation connection failed.")
        raise ExplanationProviderError from None

    try:
        choices = completion.choices
        message = choices[0].message
        response_text = message.content
        if not isinstance(response_text, str) or not response_text.strip():
            raise InvalidExplanationResponseError
        content = ExplanationContent.model_validate_json(response_text)
        _validate_explanation(content, request.results)
        response_model = getattr(completion, "model", None)
        model_name = response_model if isinstance(response_model, str) and response_model else settings.groq_model
        return ExplanationResponse(
            explanation=content,
            metadata=ExplanationMetadata(
                model=model_name,
                generated_at=datetime.now(timezone.utc).isoformat(),
                language=request.language,
                category=category,
                source_results_sha256=source_hash,
                usage=_usage_counts(getattr(completion, "usage", None)),
            ),
        )
    except InvalidExplanationResponseError:
        raise
    except (IndexError, AttributeError, TypeError, ValueError, ValidationError):
        logger.warning("Groq returned a malformed explanation.")
        raise InvalidExplanationResponseError from None

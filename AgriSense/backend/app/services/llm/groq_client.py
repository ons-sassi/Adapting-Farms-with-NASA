"""Creation of the official asynchronous Groq SDK client."""

from groq import AsyncGroq

from app.core.config import settings


class GroqNotConfiguredError(RuntimeError):
    pass


def create_groq_client() -> AsyncGroq:
    if not settings.groq_api_key:
        raise GroqNotConfiguredError
    return AsyncGroq(
        api_key=settings.groq_api_key,
        timeout=settings.groq_timeout_seconds,
        max_retries=0,
    )

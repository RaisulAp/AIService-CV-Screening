from app.config import settings
from app.llm.base import LLMProvider


def get_provider() -> LLMProvider:
    if settings.llm_provider == "openai":
        from app.llm.openai_provider import OpenAIProvider
        return OpenAIProvider()
    raise NotImplementedError(
        f"LLM_PROVIDER={settings.llm_provider!r} belum diimplementasikan "
        "(lihat ADJUSTMENT_PLAN.md §5 — Ollama direncanakan, belum dibangun)."
    )

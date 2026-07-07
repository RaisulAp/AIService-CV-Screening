import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model_extract: str = os.getenv("OPENAI_MODEL_EXTRACT", "gpt-4o-mini")
    # gpt-4o-mini default (bukan gpt-4o) — tugas reasoning di sini terstruktur/
    # pendek (1 kalimat per field), mini cukup dan jauh lebih murah per token.
    openai_model_reason: str = os.getenv("OPENAI_MODEL_REASON", "gpt-4o-mini")
    openai_embed_model: str = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

    # Batas panjang INPUT yang dikirim ke LLM (hemat token prompt walau
    # JD/CV aslinya panjang) dan batas panjang teks untuk embedding.
    max_jd_chars: int = int(os.getenv("MAX_JD_CHARS", "6000"))
    max_cv_chars: int = int(os.getenv("MAX_CV_CHARS", "6000"))
    max_embed_chars: int = int(os.getenv("MAX_EMBED_CHARS", "4000"))

    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model_extract: str = os.getenv("OLLAMA_MODEL_EXTRACT", "qwen2.5:7b")
    ollama_model_reason: str = os.getenv("OLLAMA_MODEL_REASON", "qwen2.5:7b")
    ollama_embed_model: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

    port: int = int(os.getenv("AI_PORT", "8000"))


settings = Settings()

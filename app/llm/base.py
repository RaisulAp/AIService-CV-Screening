from typing import Protocol


class LLMProvider(Protocol):
    """Seam di antara logic bisnis (jd_analyzer/cv_parser/matcher/rewriter) dan
    provider LLM konkret. Ganti provider = ganti implementasi ini saja
    (ADJUSTMENT_PLAN.md §5), logic bisnis tidak berubah."""

    def chat_json(self, system: str, user: str, *, model: str, temperature: float = 0.2, max_tokens: int = 600) -> dict:
        """Panggil LLM dalam mode JSON, kembalikan dict hasil parse.
        max_tokens membatasi OUTPUT saja (hemat biaya) — input tidak dipotong di sini,
        pemanggil bertanggung jawab memotong input panjang sebelum sampai ke sini."""
        ...

    def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        """Kembalikan embedding vector untuk tiap teks (urutan dipertahankan)."""
        ...

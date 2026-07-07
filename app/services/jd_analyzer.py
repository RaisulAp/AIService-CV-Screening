# FASE C: /analyze/jd nyata via LLM (BLUEPRINT.md §9 — JSON mode, suhu rendah,
# larang mengarang perusahaan yang tak disebutkan).

from app.config import settings
from app.llm import get_provider
from app.schemas import JDResult

_SYSTEM_PROMPT = """Ekstrak requirement lowongan kerja dari teks mentah. Balas HANYA JSON, field persis:
title (jabatan, "" jika tak jelas), company ("" jika tak disebut — JANGAN MENGARANG),
skills (array hard skill/tools eksplisit), keywords (array frasa/metodologi/sertifikasi penting selain skill),
experience (1 kalimat Indonesia, syarat pengalaman), education (1 kalimat Indonesia, syarat pendidikan).
Jangan mengarang info yang tak ada di teks. Ringkas, jangan bertele-tele."""


def analyze_jd(text: str) -> JDResult:
    provider = get_provider()
    data = provider.chat_json(
        system=_SYSTEM_PROMPT,
        user=f"Lowongan:\n\n{text[:settings.max_jd_chars]}",
        model=settings.openai_model_extract,
        temperature=0.2,
        max_tokens=500,
    )
    return JDResult(
        title=data.get("title") or "",
        company=data.get("company") or "",
        skills=data.get("skills") or [],
        keywords=data.get("keywords") or [],
        experience=data.get("experience") or "",
        education=data.get("education") or "",
    )

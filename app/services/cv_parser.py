# FASE B: raw_text + structure_report NYATA (PyMuPDF, services/pdf.py — Momen A).
# FASE C: sections NYATA via LLM. Bullet id (b1, b2, ...) ditetapkan di SINI,
# berdasar urutan kemunculan — bukan oleh LLM — supaya stabil lintas panggilan
# (weak_bullets/rewrite/rescore semua mereferensikan id ini).

from app.config import settings
from app.llm import get_provider
from app.schemas import CVResult, CVSections, ExperienceBullet
from app.services import pdf

_SECTIONS_PROMPT = """Ekstrak info terstruktur dari teks CV (hasil ekstraksi PDF, urutan mungkin berantakan).
Balas HANYA JSON, field persis:
profile (ringkasan profil singkat, "" jika tak ada),
experience (array objek {"text":"..."} — satu bullet pengalaman/organisasi/proyek per item, tulis ulang ringkas TANPA mengubah makna),
skills (array skill/tools yang eksplisit disebut),
education (array string riwayat pendidikan, mis. "S1 Informatika - Universitas X").
JANGAN menambah skill/pengalaman yang tak ada di teks asli. Jangan mengarang. Ringkas."""


class CVUnreadableError(Exception):
    """Dipetakan ke HTTP 422 -> BE memetakan ke fail_reason CV_UNREADABLE."""


def _extract_sections(raw_text: str) -> CVSections:
    provider = get_provider()
    data = provider.chat_json(
        system=_SECTIONS_PROMPT,
        user=f"Teks CV:\n\n{raw_text[:settings.max_cv_chars]}",
        model=settings.openai_model_extract,
        temperature=0.2,
        max_tokens=900,
    )
    experience = [
        ExperienceBullet(id=f"b{i + 1}", text=text)
        for i, item in enumerate(data.get("experience") or [])
        if (text := (item.get("text") or "").strip())
    ]
    return CVSections(
        profile=data.get("profile") or "",
        experience=experience,
        skills=data.get("skills") or [],
        education=data.get("education") or [],
    )


def parse_cv(file_name: str, data: bytes) -> CVResult:
    if not data:
        raise CVUnreadableError(f"File '{file_name}' kosong atau tidak bisa dibaca.")

    try:
        raw_text, structure_report = pdf.extract(data)
    except pdf.PDFUnreadableError as e:
        raise CVUnreadableError(str(e))

    sections = _extract_sections(raw_text)
    return CVResult(
        raw_text=raw_text,
        sections=sections,
        structure_report=structure_report,
    )

# FASE C: /match nyata. Angka (keyword/semantic/skill_coverage/ats_readability)
# DETERMINISTIK — LLM hanya menulis alasan + skill_gap/experience_gap/pilih
# weak_bullets. Ini menjaga janji "skor jujur, tidak di-inflate" (BLUEPRINT §9).

import json
import math

from app.config import settings
from app.llm import get_provider
from app.schemas import CVResult, JDResult, MatchResult, ScoreBreakdown, ScoreComponent, WeakBullet

_WEIGHTS = {"keyword": 0.30, "semantic": 0.30, "skill_coverage": 0.20, "ats_readability": 0.20}

_REASON_PROMPT = """Jelaskan hasil ATS matching CV vs lowongan, Bahasa Indonesia, SINGKAT.
Skor 4 komponen (0-100) SUDAH dihitung — JANGAN ubah angkanya, hanya jelaskan tiap komponen dalam 1 kalimat pendek berdasarkan data yang diberikan.
Tentukan juga: skill_gap (array skill penting yang belum dimiliki, maks 5), experience_gap (1 kalimat kekurangan pengalaman),
weak_bullet_ids (array id bullet — dari daftar yang diberikan — paling lemah/tak berdampak, maks 5, urut terlemah dulu).
Balas HANYA JSON, field: keyword_reason, semantic_reason, skill_coverage_reason, ats_readability_reason, skill_gap, experience_gap, weak_bullet_ids."""


def _norm(s: str) -> str:
    return s.strip().lower()


def _keyword_score(jd: JDResult, cv: CVResult) -> tuple[int, list[str], list[str]]:
    terms = list(dict.fromkeys(jd.skills + jd.keywords))  # dedupe, preserve order/casing
    if not terms:
        return 100, [], []
    cv_skills = {_norm(s) for s in cv.sections.skills}
    cv_text = _norm(cv.raw_text)
    matched, missing = [], []
    for term in terms:
        norm = _norm(term)
        (matched if (norm in cv_skills or norm in cv_text) else missing).append(term)
    return round(100 * len(matched) / len(terms)), matched, missing


def _skill_coverage_score(jd: JDResult, cv: CVResult) -> int:
    required = {_norm(s) for s in jd.skills}
    if not required:
        return 100
    cv_skills = {_norm(s) for s in cv.sections.skills}
    cv_text = _norm(cv.raw_text)
    covered = sum(1 for s in required if s in cv_skills or s in cv_text)
    return round(100 * covered / len(required))


def _ats_readability_score(cv: CVResult) -> int:
    score = 100
    for issue in cv.structure_report.issues:
        score -= 25 if issue.severity == "fatal" else 8
    return max(0, min(100, score))


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _semantic_score(provider, jd: JDResult, cv: CVResult) -> int:
    jd_text = f"{jd.title}. Skills: {', '.join(jd.skills)}. Keywords: {', '.join(jd.keywords)}. Pengalaman: {jd.experience}. Pendidikan: {jd.education}"
    cv_text = cv.raw_text[:settings.max_embed_chars]
    vectors = provider.embed([jd_text, cv_text], model=settings.openai_embed_model)
    sim = _cosine(vectors[0], vectors[1])
    return round(max(0.0, min(1.0, sim)) * 100)


def match(jd: JDResult, cv: CVResult) -> MatchResult:
    provider = get_provider()

    keyword_score, matched, missing = _keyword_score(jd, cv)
    skill_cov_score = _skill_coverage_score(jd, cv)
    ats_score = _ats_readability_score(cv)
    semantic_score = _semantic_score(provider, jd, cv)

    final_score = round(
        _WEIGHTS["keyword"] * keyword_score
        + _WEIGHTS["semantic"] * semantic_score
        + _WEIGHTS["skill_coverage"] * skill_cov_score
        + _WEIGHTS["ats_readability"] * ats_score
    )

    # Cap list sizes defensively — jaga token tetap kecil walau CV/JD hasil
    # parse punya banyak item; jumlah wajar (<20 bullet, <30 skill) tak terpotong.
    context = {
        "lowongan": {"title": jd.title, "skills": jd.skills[:30], "keywords": jd.keywords[:20],
                     "experience": jd.experience, "education": jd.education},
        "cv": {"skills": cv.sections.skills[:30], "education": cv.sections.education[:10],
               "experience": [{"id": b.id, "text": b.text} for b in cv.sections.experience[:20]]},
        "skor": {"keyword": keyword_score, "semantic": semantic_score, "skill_coverage": skill_cov_score, "ats_readability": ats_score},
        "matched_keywords": matched,
        "missing_keywords": missing,
        "format_issues": [{"severity": i.severity, "type": i.type} for i in cv.structure_report.issues],
    }
    reasoning = provider.chat_json(
        system=_REASON_PROMPT,
        user=json.dumps(context, ensure_ascii=False),
        model=settings.openai_model_reason,
        temperature=0.3,
        max_tokens=500,
    )

    bullets_by_id = {b.id: b.text for b in cv.sections.experience}
    weak_ids = [i for i in (reasoning.get("weak_bullet_ids") or []) if i in bullets_by_id][:5]
    if not weak_ids:
        weak_ids = [b.id for b in cv.sections.experience[:3]]
    weak_bullets = [WeakBullet(id=i, text=bullets_by_id[i]) for i in weak_ids]

    breakdown = ScoreBreakdown(
        keyword=ScoreComponent(score=keyword_score, reason=reasoning.get("keyword_reason") or ""),
        semantic=ScoreComponent(score=semantic_score, reason=reasoning.get("semantic_reason") or ""),
        skill_coverage=ScoreComponent(score=skill_cov_score, reason=reasoning.get("skill_coverage_reason") or ""),
        ats_readability=ScoreComponent(score=ats_score, reason=reasoning.get("ats_readability_reason") or ""),
    )
    return MatchResult(
        score=final_score,
        breakdown=breakdown,
        matched=matched,
        missing=missing,
        skill_gap=reasoning.get("skill_gap") or [],
        experience_gap=reasoning.get("experience_gap") or "",
        weak_bullets=weak_bullets,
    )

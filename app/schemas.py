# Skema Pydantic yang MENCERMINKAN kontrak BE persis (jangan menyimpang):
#   BE/internal/aiclient/types.go  (bentuk wire JSON)
#   BE/internal/aiclient/mock.go   (kontrak de-facto yang sudah diuji FE)
# AI Service menyesuaikan diri ke kontrak ini, bukan sebaliknya.

from typing import Literal
from pydantic import BaseModel, Field


# ---- /analyze/jd -----------------------------------------------------------

class AnalyzeJDRequest(BaseModel):
    text: str


class JDResult(BaseModel):
    title: str
    company: str
    skills: list[str]
    keywords: list[str]
    experience: str
    education: str


# ---- /parse/cv --------------------------------------------------------------

class ExperienceBullet(BaseModel):
    id: str
    text: str


class CVSections(BaseModel):
    profile: str = ""
    experience: list[ExperienceBullet] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)


class FormatIssue(BaseModel):
    severity: Literal["fatal", "warning"]
    type: str
    detail: str


class StructureReport(BaseModel):
    issues: list[FormatIssue] = Field(default_factory=list)


class CVResult(BaseModel):
    raw_text: str
    sections: CVSections
    structure_report: StructureReport


# ---- /match ------------------------------------------------------------------

class MatchRequest(BaseModel):
    jd_json: JDResult
    cv_json: CVResult


class ScoreComponent(BaseModel):
    score: int
    reason: str


class ScoreBreakdown(BaseModel):
    keyword: ScoreComponent
    semantic: ScoreComponent
    skill_coverage: ScoreComponent
    ats_readability: ScoreComponent


class WeakBullet(BaseModel):
    id: str
    text: str


class MatchResult(BaseModel):
    score: int
    breakdown: ScoreBreakdown
    matched: list[str]
    missing: list[str]
    skill_gap: list[str]
    experience_gap: str
    weak_bullets: list[WeakBullet]


# ---- /rewrite ------------------------------------------------------------------

class RewriteRequest(BaseModel):
    bullet: str
    jd_context: str


class RewriteResult(BaseModel):
    suggestion: str
    reasoning: str

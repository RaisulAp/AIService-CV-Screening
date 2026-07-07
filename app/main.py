# AI Service — FastAPI kandidat-facing (BE/internal/aiclient/*.go adalah kontrak).
# Endpoint ini dipanggil oleh Web Backend (Go), bukan langsung oleh Frontend.

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas import (
    AnalyzeJDRequest,
    CVResult,
    JDResult,
    MatchRequest,
    MatchResult,
    RewriteRequest,
    RewriteResult,
)
from app.services import cv_parser, jd_analyzer, matcher, rewriter

app = FastAPI(title="CV Screening AI Service")


# BE (aiclient/http.go) maps ANY 422 response to CV_UNREADABLE, regardless of
# endpoint. FastAPI's default request-validation error is also a 422, which
# would otherwise leak that meaning onto /analyze/jd, /match and /rewrite too.
# Remap those to 400 so 422 stays reserved for the explicit CVUnreadableError
# raised in /parse/cv (see BACKEND.md §7, ADJUSTMENT_PLAN.md §1.5).
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400, content={"detail": exc.errors()})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze/jd", response_model=JDResult)
def analyze_jd(req: AnalyzeJDRequest):
    return jd_analyzer.analyze_jd(req.text)


@app.post("/parse/cv", response_model=CVResult)
async def parse_cv(file: UploadFile):
    data = await file.read()
    try:
        return cv_parser.parse_cv(file.filename or "cv", data)
    except cv_parser.CVUnreadableError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/match", response_model=MatchResult)
def match(req: MatchRequest):
    return matcher.match(req.jd_json, req.cv_json)


@app.post("/rewrite", response_model=RewriteResult)
def rewrite(req: RewriteRequest):
    return rewriter.rewrite(req.bullet, req.jd_context)

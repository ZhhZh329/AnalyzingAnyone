from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .errors import GatewayError, build_failure_response, generate_prefixed_id
from .routes.analysis_tiers import router as analysis_tiers_router
from .routes.projects import router as projects_router


app = FastAPI(title="AnalyzingAnyone Gateway MVP", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(analysis_tiers_router)
app.include_router(projects_router)


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/ui", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/ui/")


@app.exception_handler(GatewayError)
async def handle_gateway_error(_: Request, exc: GatewayError) -> JSONResponse:
    request_id = generate_prefixed_id("req")
    trace_id = exc.trace_id or generate_prefixed_id("trace")
    response = build_failure_response(
        request_id=request_id,
        trace_id=trace_id,
        code=exc.code,
        message=exc.message,
        details=exc.details,
        retryable=exc.retryable,
        stage_key=exc.stage_key,
    )
    return JSONResponse(status_code=exc.status_code, content=response.model_dump(mode="json"))


@app.exception_handler(Exception)
async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    request_id = generate_prefixed_id("req")
    trace_id = generate_prefixed_id("trace")
    response = build_failure_response(
        request_id=request_id,
        trace_id=trace_id,
        code="INTERNAL_SERVER_ERROR",
        message="unexpected gateway error",
        details={"exception": str(exc)},
        retryable=False,
    )
    return JSONResponse(status_code=500, content=response.model_dump(mode="json"))

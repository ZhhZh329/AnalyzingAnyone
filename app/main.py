from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .errors import GatewayError, build_failure_response, generate_prefixed_id
from .routes.projects import router as projects_router


app = FastAPI(title="AnalyzingAnyone Gateway MVP", version="0.1.0")
app.include_router(projects_router)


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

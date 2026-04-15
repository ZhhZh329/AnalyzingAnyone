from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .schemas import ApiResponse, ErrorDetail, ValidationInfo


def now_local() -> datetime:
    return datetime.now(timezone.utc).astimezone()


def generate_prefixed_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


class GatewayError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: dict | None = None,
        retryable: bool = False,
        stage_key: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.retryable = retryable
        self.stage_key = stage_key
        self.trace_id = trace_id


def build_success_response(
    *,
    request_id: str,
    trace_id: str,
    data,
    status: str = "success",
    message: str | None = None,
    persisted: bool = True,
) -> ApiResponse:
    return ApiResponse(
        success=True,
        request_id=request_id,
        trace_id=trace_id,
        status=status,
        message=message,
        data=data,
        validation=ValidationInfo(persisted=persisted),
        timestamp=now_local(),
    )


def build_failure_response(
    *,
    request_id: str,
    trace_id: str,
    code: str,
    message: str,
    status: str = "failed",
    details: dict | None = None,
    retryable: bool = False,
    stage_key: str | None = None,
) -> ApiResponse:
    return ApiResponse(
        success=False,
        request_id=request_id,
        trace_id=trace_id,
        status=status,
        error=ErrorDetail(
            code=code,
            message=message,
            details=details or {},
            retryable=retryable,
            stage_key=stage_key,
        ),
        timestamp=now_local(),
    )

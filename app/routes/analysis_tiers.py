from __future__ import annotations

from fastapi import APIRouter

from ..errors import build_success_response, generate_prefixed_id
from ..schemas import ApiResponse
from ..service import GatewayService


router = APIRouter(tags=["analysis-tiers"])
service = GatewayService()


@router.get("/analysis-tiers", response_model=ApiResponse)
def get_analysis_tiers() -> ApiResponse:
    request_id = generate_prefixed_id("req")
    trace_id = generate_prefixed_id("trace")
    return build_success_response(
        request_id=request_id,
        trace_id=trace_id,
        data=service.get_analysis_tiers(),
        status="success",
        message="analysis tiers",
    )

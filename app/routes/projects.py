from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from ..errors import build_success_response, generate_prefixed_id
from ..schemas import ApiResponse, CreateProjectRequest, CreateRunRequest
from ..service import GatewayService


router = APIRouter(prefix="/projects", tags=["projects"])
service = GatewayService()


@router.post("", response_model=ApiResponse)
def create_project(payload: CreateProjectRequest) -> ApiResponse:
    request_id = generate_prefixed_id("req")
    data = service.create_project(payload)
    trace_id = f"trace_{data['project_id']}"
    return build_success_response(
        request_id=request_id,
        trace_id=trace_id,
        data=data,
        status="created",
        message="project created",
    )


@router.post("/{project_id}/ingestion-packages", response_model=ApiResponse)
async def upload_ingestion_package(
    project_id: str,
    subject_id: str = Form(...),
    package_file: UploadFile = File(...),
    package_name: str | None = Form(None),
    package_type: str = Form("zip"),
    user_notes: str | None = Form(None),
    default_source_hint: str | None = Form(None),
) -> ApiResponse:
    request_id = generate_prefixed_id("req")
    payload = await package_file.read()
    trace_id, data = service.ingest_package(
        project_id,
        subject_id=subject_id,
        filename=package_name or package_file.filename or "ingestion.zip",
        package_type=package_type,
        payload=payload,
        user_notes=user_notes,
        default_source_hint=default_source_hint,
    )
    return build_success_response(
        request_id=request_id,
        trace_id=trace_id,
        data=data,
        status="completed",
        message="ingestion package uploaded",
    )


@router.post("/{project_id}/runs", response_model=ApiResponse)
def create_run(project_id: str, payload: CreateRunRequest) -> ApiResponse:
    request_id = generate_prefixed_id("req")
    data = service.create_run(project_id, payload)
    return build_success_response(
        request_id=request_id,
        trace_id=data["trace_id"],
        data=data,
        status="queued",
        message="run created",
    )


@router.get("/{project_id}/runs/{run_id}", response_model=ApiResponse)
def get_run(project_id: str, run_id: str) -> ApiResponse:
    request_id = generate_prefixed_id("req")
    detail = service.get_run(project_id, run_id)
    return build_success_response(
        request_id=request_id,
        trace_id=detail.run.trace_id,
        data=detail.model_dump(mode="json"),
        status=detail.run.status.value,
    )


@router.get("/{project_id}/runs/{run_id}/evidence-assembly", response_model=ApiResponse)
def get_evidence_assembly(project_id: str, run_id: str) -> ApiResponse:
    request_id = generate_prefixed_id("req")
    detail = service.get_run(project_id, run_id)
    assembly = service.get_evidence_assembly(project_id, run_id)
    return build_success_response(
        request_id=request_id,
        trace_id=detail.run.trace_id,
        data=assembly,
        status=detail.run.status.value,
    )


@router.get("/{project_id}/runs/{run_id}/report", response_model=ApiResponse)
def get_report(project_id: str, run_id: str) -> ApiResponse:
    request_id = generate_prefixed_id("req")
    detail = service.get_run(project_id, run_id)
    report = service.get_report(project_id, run_id)
    return build_success_response(
        request_id=request_id,
        trace_id=detail.run.trace_id,
        data=report.model_dump(mode="json"),
        status=detail.run.status.value,
    )

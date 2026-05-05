from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


SCHEMA_VERSION = "v0.1"
API_VERSION = "v0.1"
DEFAULT_STAGE_KEYS = [
    "input_normalize",
    "assemble",
    "discipline",
    "critique",
    "synthesize",
    "report",
]


class GatewayModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    PARTIAL_FAILED = "partial_failed"
    FAILED = "failed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class StageStatusEnum(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL_FAILED = "partial_failed"


class AnalysisTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    LITE = "lite"
    STANDARD = "standard"
    FULL = "full"


class Subject(GatewayModel):
    id: str
    display_name: str
    aliases: list[str] = Field(default_factory=list)


class CreateProjectSubject(GatewayModel):
    display_name: str
    aliases: list[str] = Field(default_factory=list)


class CreateProjectRequest(GatewayModel):
    name: str
    description: str = ""
    subject: CreateProjectSubject


class Project(GatewayModel):
    id: str
    name: str
    description: str = ""
    subject: Subject
    status: str
    created_at: datetime


class IngestionPackage(GatewayModel):
    id: str
    project_id: str
    subject_id: str
    filename: str
    package_type: str
    byte_size: int
    sha256: str
    status: str
    created_at: datetime
    user_notes: str | None = None
    default_source_hint: str | None = None
    raw_file_count: int = 0
    supported_file_count: int = 0
    unsupported_file_count: int = 0
    parsed_success_count: int = 0
    parsed_failed_count: int = 0
    empty_text_count: int = 0
    source_count: int = 0
    source_types: list[str] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)


class RunConfig(GatewayModel):
    schema_version: str = SCHEMA_VERSION
    model_profile: str = "default"
    analysis_tier: AnalysisTier = AnalysisTier.MEDIUM
    color_weight_config_version: str | None = None
    scoring_rubric_version: str | None = None


class CreateRunRequest(GatewayModel):
    subject_id: str
    package_id: str | None = None
    run_config: RunConfig = Field(default_factory=RunConfig)


class StageStatus(GatewayModel):
    stage_key: str
    status: StageStatusEnum
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    error_message: str | None = None
    output_ref: str | None = None


class Run(GatewayModel):
    id: str
    project_id: str
    subject_id: str
    trace_id: str
    status: RunStatus
    current_stage: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    output_ref: str | None = None


class ArtifactRefs(GatewayModel):
    output_dir: str | None = None
    run_manifest_ref: str | None = None
    assembly_ref: str | None = None
    critic_output_ref: str | None = None
    synthesis_ref: str | None = None
    report_ref: str | None = None
    feedback_ref: str | None = None
    stdout_ref: str | None = None
    stderr_ref: str | None = None


class AuxiliaryInfo(GatewayModel):
    request_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    input_snapshot_ref: str | None = None
    status_ref: str | None = None
    manifest_ref: str | None = None
    request_events_ref: str | None = None
    latest_feedback_ref: str | None = None
    latest_stdout_ref: str | None = None
    latest_stderr_ref: str | None = None


class RunDetail(GatewayModel):
    run: Run
    stages: list[StageStatus] = Field(default_factory=list)
    error: "ErrorDetail | None" = None
    artifacts: ArtifactRefs | None = None
    auxiliary: AuxiliaryInfo | None = None


class EventView(GatewayModel):
    id: str
    date: str
    what: str
    source_ids: list[str]
    context: str | None = None


class EvidenceCardView(GatewayModel):
    id: str
    source_id: str
    source_type: str
    date: str
    kind: str
    summary: str
    verbatim_quote: str = ""
    first_hand_level: str
    reliability_note: str = ""
    editorial_risk: str = ""
    timeline_refs: list[str] = Field(default_factory=list)


class EvidenceAssemblyView(GatewayModel):
    subject: str
    timeline: list[EventView] = Field(default_factory=list)
    evidence_cards: list[EvidenceCardView] = Field(default_factory=list)


class FinalReport(GatewayModel):
    subject: str
    format: str
    content: str
    generated_at: datetime
    version: str = "v0.1"


class ValidationInfo(GatewayModel):
    acknowledged: bool = True
    schema_version: str = SCHEMA_VERSION
    api_version: str = API_VERSION
    persisted: bool = True


class ErrorDetail(GatewayModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    retryable: bool = False
    stage_key: str | None = None


class ApiResponse(GatewayModel):
    success: bool
    request_id: str
    trace_id: str
    status: str
    message: str | None = None
    data: Any | None = None
    validation: ValidationInfo | None = None
    error: ErrorDetail | None = None
    timestamp: datetime

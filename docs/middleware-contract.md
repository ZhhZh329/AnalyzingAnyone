# Middleware Contract

This document fixes the current middleware-facing contract for frontend, workflow,
and data-layer integration. It is aligned with the project requirement docs:

- `工作总线`
- `统一对象与接口契约文档`
- `中间层接口统一模块需求文档`
- `后端 Agent 工作流交互模块需求文档`
- `后端数据流控制模块需求文档`

## Current API Surface

The current middleware exposes six stable endpoints:

- `POST /projects`
- `POST /projects/{project_id}/ingestion-packages`
- `POST /projects/{project_id}/runs`
- `GET /projects/{project_id}/runs/{run_id}`
- `GET /projects/{project_id}/runs/{run_id}/evidence-assembly`
- `GET /projects/{project_id}/runs/{run_id}/report`

All responses use the same envelope:

- `success`
- `request_id`
- `trace_id`
- `status`
- `message`
- `data`
- `validation`
- `error`
- `timestamp`

## Required Run-Level Fields

The middleware expects a stable run object with at least:

- `run_id`
- `project_id`
- `subject_id`
- `trace_id`
- `status`
- `current_stage`
- `started_at`
- `finished_at`
- `output_ref`

## Required Stage-Level Fields

The middleware expects a stable stage status object with at least:

- `stage_key`
- `status`
- `started_at`
- `finished_at`
- `error_message`
- `output_ref`

Current stage keys used by the middleware:

- `input_normalize`
- `assemble`
- `discipline`
- `critique`
- `synthesize`
- `report`

## Required Error Fields

The middleware expects a stable error object with at least:

- `code`
- `message`
- `details`
- `retryable`
- `stage_key`
- `trace_id`

## Required Artifact References

The middleware currently reads these run outputs:

- `assembly.json`
- `critic_output.json`
- `synthesis.json`
- `report.md`
- `run_feedback.json`

## Required Auxiliary Metadata

The middleware also depends on auxiliary request/runtime metadata:

- `request_id`
- `trace_id`
- `created_at`
- `updated_at`
- `input_snapshot_ref`
- `status_ref`
- `request_events_ref`
- `latest_feedback_ref`
- `latest_stdout_ref`
- `latest_stderr_ref`

## Current Responsibility Split

- Workflow / agent side:
  produces run/stage/error/core-output runtime data.
- Data layer side:
  persists and organizes workflow outputs, status, logs, and auxiliary metadata.
- Middleware side:
  reads stable run/status/error/artifact data and exposes frontend-facing APIs.

## Notes

- The frontend should not construct workflow-internal state by itself.
- The middleware only depends on three backend capabilities:
  - start task
  - query status
  - read outputs
- Storage internals may change later, but these contract fields should remain
  stable for middleware consumption.

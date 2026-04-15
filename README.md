# AnalyzingAnyone Gateway MVP

This repository now contains two layers:

- The existing file-driven analysis workflow:
  - `loader.py`
  - `main.py`
  - `runtime.py`
- A new Gateway MVP API layer:
  - `app/main.py`
  - `app/routes/projects.py`
  - `app/schemas.py`
  - `app/service.py`

The Gateway does not rewrite the workflow. It wraps the current pipeline into stable APIs for:

- project creation
- ingestion package upload
- run creation
- run status lookup
- evidence assembly lookup
- final report lookup

## Requirements

- Python 3.11+
- `uv` recommended

## Install

Use `uv`:

```bash
uv sync
```

Or use `pip`:

```bash
python -m pip install -e .
```

The Gateway needs:

- `fastapi`
- `openpyxl`
- `pypdf`
- `python-docx`
- `uvicorn`
- `python-multipart`

Those dependencies are already declared in [pyproject.toml](/Users/jiangyiming/大三下学习/Agentic%20Meta%20Cognition/AnalyzingAnyone/pyproject.toml).

## Start The Gateway

```bash
uv run uvicorn app.main:app --reload
```

Default URL:

```text
http://127.0.0.1:8000
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

## Workflow Trigger Strategy

The Gateway currently starts the workflow through a subprocess.

Default behavior:

```bash
uv run python main.py --input-file <run_input.json> --feedback-out <run_feedback.json>
```

You can override the workflow command with:

```bash
export GATEWAY_WORKFLOW_COMMAND="python /abs/path/to/your_entry.py"
```

The Gateway now writes:

- `runs/{run_id}/meta/run_input.json`
- `runs/{run_id}/meta/run_feedback.json`

The workflow consumes `run_input.json`, and the Gateway reads `run_feedback.json`
to discover the real `output/<subject_slug>/` artifact directory.

## Gateway Runtime Data

Gateway runtime state is stored under:

```text
gateway_store/
```

Main structure:

```text
gateway_store/
  projects/{project_id}/
  runs/{run_id}/
```

Each run contains:

```text
runs/{run_id}/
  input/
  meta/
  status.json
```

`meta/` now typically contains:

```text
run_input.json
run_feedback.json
run.json
stdout.log
stderr.log
```

## Current API Surface

### 1. Create project

`POST /projects`

Example body:

```json
{
  "name": "Analyzing Elon Musk",
  "description": "Public-material profiling run",
  "subject": {
    "display_name": "Elon Musk",
    "aliases": ["Elon Reeve Musk"]
  }
}
```

### 2. Upload ingestion package

`POST /projects/{project_id}/ingestion-packages`

This endpoint expects `multipart/form-data` with:

- `subject_id`
- `package_file`
- `package_name`
- `package_type`
- `user_notes`
- `default_source_hint`

### 3. Create run

`POST /projects/{project_id}/runs`

Example body:

```json
{
  "subject_id": "subj_xxx",
  "package_id": "pkg_xxx",
  "run_config": {
    "schema_version": "v0.1",
    "model_profile": "default"
  }
}
```

### 4. Get run

`GET /projects/{project_id}/runs/{run_id}`

### 5. Get evidence assembly

`GET /projects/{project_id}/runs/{run_id}/evidence-assembly`

### 6. Get final report

`GET /projects/{project_id}/runs/{run_id}/report`

## Ingestion Package Support

The Gateway now accepts a mixed-document zip and generates a workflow-compatible
input bundle on its own.

Supported file types in this MVP:

- `pdf`
- `docx`
- `md`
- `txt`
- `xlsx`
- `csv`

The uploaded zip can use arbitrary nested folders. The Gateway will:

1. unpack the archive safely
2. discover supported files
3. extract text and basic structure
4. materialize standard sources
5. generate `input_bundle/manifest.json + sources/*` for [loader.py](/Users/jiangyiming/大三下学习/Agentic%20Meta%20Cognition/AnalyzingAnyone/loader.py)

Example mixed package:

```text
bundle.zip
  profile/
    bio.docx
    notes.md
  tables/
    timeline.csv
    metrics.xlsx
  archive/
    interview.pdf
```

Gateway package artifacts include:

- `package.json`
- `raw_files.json`
- `parsed_files.json`
- `sources.json`
- `warnings.json`
- `input_bundle/`

`input_bundle/manifest.json` is generated automatically and remains compatible
with the existing workflow.

## Output Resolution

The workflow itself still writes stable artifacts under:

```text
output/<subject_slug>/
```

The Gateway does not guess this path anymore. It reads the actual `output_dir`
from `run_feedback.json`, stores that as the run's `output_ref`, and then uses
that path for:

- `assembly.json`
- `critic_output.json`
- `synthesis.json`
- `report.md`

## Quick Local Test

1. Start the Gateway:

```bash
uv run uvicorn app.main:app --reload
```

2. Create a project in `/docs`.

3. Upload a mixed-document zip.

4. Create a run.

5. Poll:

```text
GET /projects/{project_id}/runs/{run_id}
```

6. Read:

- `GET /projects/{project_id}/runs/{run_id}/evidence-assembly`
- `GET /projects/{project_id}/runs/{run_id}/report`

## Known Limits

- No `color_profile` endpoint yet
- No debug endpoint yet
- No source CRUD yet
- No OCR
- No `.doc` support
- Scanned or image-only PDFs may produce empty text warnings
- This week, running status is still maintained by the Gateway side rather than continuously streamed by workflow-native stage callbacks

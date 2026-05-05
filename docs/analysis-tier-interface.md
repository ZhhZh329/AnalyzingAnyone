# Analysis Tier Interface

This document is the frontend/backend contract owned by the middleware.

## Frontend Contract

### Read Available Tiers

`GET /analysis-tiers`

Response envelope is the standard `ApiResponse`. The tier metadata is in
`data`:

```json
{
  "default_tier": "lite",
  "tiers": [
    {
      "key": "lite",
      "label": "快速档",
      "description": "适合演示和常规使用，运行少量核心 lenses，优先保证快速稳定出报告。",
      "estimated_lens_count": 35,
      "estimated_duration_minutes": "10-25"
    },
    {
      "key": "standard",
      "label": "标准档",
      "description": "覆盖主要学科和核心 lenses，质量更高，耗时中等。",
      "estimated_lens_count": 80,
      "estimated_duration_minutes": "30-60"
    },
    {
      "key": "full",
      "label": "全量档",
      "description": "运行全部 lenses，适合深度研究，耗时长，后处理需要压缩或分批汇总。",
      "estimated_lens_count": 211,
      "estimated_duration_minutes": "90+"
    }
  ]
}
```

The frontend should render tier choices from this endpoint instead of hardcoding
labels, descriptions, or estimates.

### Create Run

`POST /projects/{project_id}/runs`

The frontend sends the selected tier under `run_config.analysis_tier`:

```json
{
  "subject_id": "subj_xxx",
  "package_id": "pkg_xxx",
  "run_config": {
    "schema_version": "v0.1",
    "model_profile": "default",
    "analysis_tier": "lite"
  }
}
```

Allowed values:

- `lite`
- `standard`
- `full`

If the frontend omits `analysis_tier`, the middleware defaults to `lite`.

## Backend Workflow Contract

The middleware writes the selected tier into:

`gateway_store/runs/{run_id}/meta/run_input.json`

Shape:

```json
{
  "subject_dir": "/abs/path/to/input",
  "run_id": "run_xxx",
  "trace_id": "trace_run_xxx",
  "run_config": {
    "schema_version": "v0.1",
    "model_profile": "default",
    "analysis_tier": "lite",
    "color_weight_config_version": null,
    "scoring_rubric_version": null
  }
}
```

The backend workflow should read:

```text
run_input.json.run_config.analysis_tier
```

and use that value to select its lens/skill schedule.

Recommended semantic mapping:

- `lite`: default product/demo mode, few core lenses, fastest stable report.
- `standard`: broader core coverage across main disciplines.
- `full`: run all lenses, research mode; downstream summarization must avoid
  sending complete full-lens JSON into one model context.

The middleware does not define the exact skill list for each tier. The backend
owns the tier-to-skill schedule, but it must keep the public tier keys stable.

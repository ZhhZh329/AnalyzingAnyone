# AnalyzingAnyone

AnalyzingAnyone is a multi-agent, multi-lens pipeline for building structured public-figure profiles from source material.

The project takes a corpus of publicly available texts about a person, converts that corpus into a timeline and evidence cards, runs multiple theory-specific lenses in parallel, critiques weak claims, synthesizes cross-lens patterns, and generates a final report.

The core idea is simple:

- start from evidence, not vibes
- run multiple independent lenses, not one monolithic summary
- preserve convergence and tension across frameworks
- keep outputs traceable back to source-backed evidence cards

## What This Project Does

Given a subject directory such as `data/elon_musk/`, the pipeline:

1. Loads a `manifest.json` plus all source files
2. Builds:
   - a chronological `timeline`
   - a set of structured `evidence_cards`
3. Runs all discipline lenses in parallel
4. Audits the lens outputs for weak grounding
5. Synthesizes cross-lens findings
6. Writes a human-readable Markdown report

This is not intended to be:

- a clinical diagnosis system
- legal, medical, or financial advice
- a truth machine for private inner states

It is better understood as an evidence-constrained, multi-framework analysis system for public materials.

## Current Pipeline

The main entrypoint is [`main.py`](./main.py).

High-level stages:

1. `evidence_assembler`
2. `discipline` lenses
3. `critic`
4. `synthesizer`
5. `reporter`

Supporting runtime and schemas live in:

- [`runtime.py`](./runtime.py)
- [`loader.py`](./loader.py)
- [`schemas.py`](./schemas.py)

## Repository Layout

```text
.
├── agents/
│   ├── evidence_assembler/
│   ├── critic/
│   ├── synthesizer/
│   ├── reporter/
│   └── discipline/
│       ├── philosophy/
│       ├── psychology/
│       ├── neuroscience/
│       ├── sociology/
│       ├── cs_eng/
│       └── medicine/
├── data/
│   └── <subject>/
│       ├── manifest.json
│       └── sources/
├── output/
│   └── <subject>/
├── skills/
│   └── source_context/
├── main.py
├── runtime.py
├── loader.py
├── schemas.py
├── config.yaml
└── llm.yaml
```

## Subject Data Format

Each subject lives under `data/<subject>/`.

Example:

```text
data/elon_musk/
├── manifest.json
└── sources/
    ├── 001_childhood_bullying.txt
    ├── 002_blastar_game.txt
    └── ...
```

`manifest.json` looks like this:

```json
{
  "subject": "Elon Musk",
  "description": "Tesla/SpaceX/X/xAI CEO...",
  "sources": [
    {
      "id": "src_001",
      "type": "biography",
      "date": "1977",
      "file": "sources/001_childhood_bullying.txt",
      "context": "Childhood in Pretoria, bullying, family dynamics"
    }
  ]
}
```

Each source entry should include:

- `id`
- `type`
- `date`
- `file`
- optional metadata such as `context`

## Running The Pipeline

Install dependencies:

```bash
uv sync
```

Configure your model in `llm.yaml`.

Then run:

```bash
uv run python main.py data/elon_musk
```

If successful, outputs are written under:

```text
output/elon_musk/
├── assembly.json
├── critic_output.json
├── synthesis.json
├── report.md
└── lenses/
```

## Model Configuration

The pipeline reads:

- [`config.yaml`](./config.yaml) for shared constructs
- `llm.yaml` for provider, model, API keys, and API base overrides

`llm.yaml` is intentionally ignored by git because it contains secrets.

Typical fields:

```yaml
default:
  provider: openai
  model: "gpt-5"
  max_concurrency: 5

keys:
  openai: "..."

api_bases:
  openai: "https://your-openai-compatible-endpoint/v1"
```

## Output Types

### `assembly.json`

Contains:

- `timeline`
- `evidence_cards`

This is the evidence layer that all later stages should rely on.

### `lenses/*.json`

One output per lens. Each lens is expected to:

- analyze the same evidence set
- stay inside its own theory boundary
- map findings onto shared constructs
- optionally propose `emergent_constructs`

### `critic_output.json`

Flags:

- weakly grounded claims
- overreach
- source misuse
- construct confidence bands

### `synthesis.json`

Cross-lens synthesis of:

- convergences
- complementary views
- tensions
- scenario implications

### `report.md`

A readable final profile written from structured outputs.

## Design Principles

The project is built on a few core rules:

### 1. Evidence First

Claims should be grounded in `evidence_cards`, not just plausible interpretation.

### 2. Lens Independence

Each lens should ask its own first question. If two lenses say the same thing with different vocabulary, one of them is probably redundant.

### 3. Shared Constructs, Different Languages

Different disciplines can interpret the same construct differently. Shared constructs are a comparison layer, not a demand for uniform theory.

### 4. Preserve Tension

Do not flatten contradictions. Tension between frameworks is often the most informative result.

### 5. Explicit Boundaries

High-stakes domains such as medicine should discuss patterns, risks, and observable behavior, not invent diagnoses or hidden records.

For a more detailed internal guide, see:

- [`agents/AGENT_GUIDE.md`](./agents/AGENT_GUIDE.md)

## Adding A New Discipline

To add a new discipline:

1. Create `agents/discipline/<name>/`
2. Add:
   - `agent.yaml`
   - `prompt.md`
   - `skills/`
3. Write 4-8 non-overlapping skills
4. Make sure each skill:
   - has a real theoretical center
   - has a clear first question
   - can map to shared constructs
   - defines boundaries and overreach risks
5. Test it on an existing subject

The recently added `medicine/` discipline can be used as a concrete example.

## Utility Scripts

Current helper scripts include:

- [`scripts/fetch_paul_graham_essays.py`](./scripts/fetch_paul_graham_essays.py)
- [`scripts/fetch_sam_altman_blog.py`](./scripts/fetch_sam_altman_blog.py)
- [`scripts/fetch_obama_weekly_addresses.py`](./scripts/fetch_obama_weekly_addresses.py)
- [`scripts/fetch_steve_jobs_book.py`](./scripts/fetch_steve_jobs_book.py)
- [`scripts/run_medicine_example.py`](./scripts/run_medicine_example.py)
- [`scripts/test_openai_compat_api.py`](./scripts/test_openai_compat_api.py)

## Notes

- `output/` may contain generated artifacts that are useful to inspect and compare.
- `llm.yaml` is local-only and should not be committed.
- This project works best when source quality is high and source types are mixed.

## Status

The repository currently contains:

- multiple discipline packs
- a medicine discipline and example outputs
- a reusable OpenAI-compatible API test script
- an internal agent guide for writing future skills

If you want to understand the system quickly, start with:

1. [`main.py`](./main.py)
2. [`runtime.py`](./runtime.py)
3. [`config.yaml`](./config.yaml)
4. [`agents/AGENT_GUIDE.md`](./agents/AGENT_GUIDE.md)

"""
main.py — Orchestrator for the V2.1 multi-disciplinary human profiling pipeline.

Stages:
  1. evidence_assembler  — timeline + evidence cards
  2. sub-lens skills     — all discipline × skill combinations in parallel
  3. critic              — fact-check + construct confidence banding
  4. synthesizer         — cross-lens synthesis with construct matrix
  5. reporter            — final Markdown report

Usage:
    uv run python main.py data/elon_musk
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

import loader
from runtime import (
    build_construct_matrix,
    discover_agents,
    discover_skills,
    run_agent,
)


STAGE_KEYS = [
    "input_normalize",
    "assemble",
    "discipline",
    "critique",
    "synthesize",
    "report",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _duration_ms(started_at: str, finished_at: str) -> int | None:
    try:
        start = _parse_datetime(started_at)
        end = _parse_datetime(finished_at)
    except ValueError:
        return None
    return max(int((end - start).total_seconds() * 1000), 0)


def _status_path() -> Path | None:
    raw = os.environ.get("ANALYZINGANYONE_STATUS_PATH")
    return Path(raw) if raw else None


def _default_stages() -> list[dict]:
    return [
        {
            "stage_key": stage_key,
            "status": "pending",
            "started_at": None,
            "finished_at": None,
            "duration_ms": None,
            "error_message": None,
            "output_ref": None,
        }
        for stage_key in STAGE_KEYS
    ]


def _ensure_status_doc(status_path: Path | None) -> dict | None:
    if status_path is None:
        return None
    if status_path.exists():
        return json.loads(status_path.read_text(encoding="utf-8"))
    now = _now_iso()
    doc = {
        "run_id": os.environ.get("ANALYZINGANYONE_RUN_ID"),
        "trace_id": os.environ.get("ANALYZINGANYONE_TRACE_ID", ""),
        "status": "queued",
        "current_stage": None,
        "started_at": now,
        "finished_at": None,
        "updated_at": now,
        "stages": _default_stages(),
        "error": None,
    }
    _write_status_doc(status_path, doc)
    return doc


def _write_status_doc(status_path: Path | None, doc: dict | None) -> None:
    if status_path is None or doc is None:
        return
    status_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = status_path.with_suffix(status_path.suffix + ".tmp")
    temp_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(status_path)


def _update_stage(
    stage_key: str,
    *,
    stage_status: str | None = None,
    run_status: str | None = None,
    output_ref: str | None = None,
    error_message: str | None = None,
    error: dict | None = None,
) -> None:
    status_path = _status_path()
    doc = _ensure_status_doc(status_path)
    if doc is None:
        return
    now = _now_iso()
    stage = next((item for item in doc["stages"] if item["stage_key"] == stage_key), None)
    if stage is None:
        stage = {
            "stage_key": stage_key,
            "status": "pending",
            "started_at": None,
            "finished_at": None,
            "duration_ms": None,
            "error_message": None,
            "output_ref": None,
        }
        doc["stages"].append(stage)
    if stage_status == "running":
        stage["started_at"] = stage["started_at"] or now
        doc["current_stage"] = stage_key
        doc["status"] = run_status or "running"
    elif stage_status is not None:
        stage["status"] = stage_status
        stage["finished_at"] = now
        if stage.get("started_at"):
            stage["duration_ms"] = _duration_ms(stage["started_at"], now)
        if error_message:
            stage["error_message"] = error_message
    if stage_status is not None:
        stage["status"] = stage_status
    if output_ref is not None:
        stage["output_ref"] = output_ref
    if run_status is not None:
        doc["status"] = run_status
    if error is not None:
        doc["error"] = error
        doc["finished_at"] = now
    if run_status in {"completed", "partial_failed", "failed"}:
        doc["finished_at"] = doc.get("finished_at") or now
    doc["updated_at"] = now
    _write_status_doc(status_path, doc)


def _mark_run_failure(stage_key: str, exc: Exception) -> None:
    error = {
        "code": "WORKFLOW_STAGE_FAILED",
        "message": str(exc),
        "details": {"exception_type": type(exc).__name__},
        "retryable": False,
        "stage_key": stage_key,
    }
    _update_stage(
        stage_key,
        stage_status="failed",
        run_status="failed",
        error_message=str(exc),
        error=error,
    )


async def run(subject_dir: str) -> None:
    current_stage = "input_normalize"
    had_partial_failures = False
    try:
        # ── Load config ───────────────────────────────────────────
        config = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))

        # Load llm.yaml and merge into config (keys, api_bases, default provider/model)
        llm_path = Path("llm.yaml")
        if llm_path.exists():
            llm = yaml.safe_load(llm_path.read_text(encoding="utf-8")) or {}
            config["keys"]            = llm.get("keys", {})
            config["api_bases"]       = llm.get("api_bases", {})
            config.setdefault("provider",         llm.get("default", {}).get("provider", "anthropic"))
            config.setdefault("model",            llm.get("default", {}).get("model", ""))
            config.setdefault("max_concurrency",  llm.get("default", {}).get("max_concurrency", 5))

        provider = config.get("provider", "anthropic")
        model    = config.get("model", "")
        print(f"Provider: {provider}")
        print(f"Model:    {model}")

        # ── Discover agents ───────────────────────────────────────
        agents = discover_agents(Path("agents"))
        print(f"Discovered agents: { {k: [p.name for p in v] for k, v in agents.items()} }")

        # ── Load data ─────────────────────────────────────────────
        _update_stage("input_normalize", stage_status="running", run_status="running")
        data = loader.load(Path(subject_dir))
        subject = data["subject"]
        print(f"\nSubject: {subject}")
        print(f"Sources loaded: {len(data['sources'])}")
        _update_stage("input_normalize", stage_status="success", output_ref=str(Path(subject_dir)))

        # Prepare output directory
        output_override = os.environ.get("ANALYZINGANYONE_OUTPUT_DIR")
        if output_override:
            out_dir = Path(output_override)
        else:
            out_dir = Path("output") / subject.lower().replace(" ", "_")
        out_dir.mkdir(parents=True, exist_ok=True)
        lenses_dir = out_dir / "lenses"
        lenses_dir.mkdir(exist_ok=True)

        # ── Stage 1: Evidence assembly ────────────────────────────
        current_stage = "assemble"
        _update_stage("assemble", stage_status="running", run_status="running")
        print("\n[Stage 1] Assembling evidence...")
        assembly = await run_agent(
            agents["assemble"][0],
            "assemble",
            {"subject": subject, "sources": data["sources"]},
            config,
        )
        timeline_count = len(assembly.get("timeline", []))
        card_count = len(assembly.get("evidence_cards", []))
        print(f"  → {timeline_count} timeline events, {card_count} evidence cards")
        assembly_path = out_dir / "assembly.json"
        assembly_path.write_text(
            json.dumps(assembly, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        _update_stage("assemble", stage_status="success", output_ref=str(assembly_path))

        # ── Stage 2: Sub-lens annotations (all skills in parallel) ─
        current_stage = "discipline"
        _update_stage("discipline", stage_status="running", run_status="running")
        print("\n[Stage 2] Running sub-lens annotations in parallel...")
        discipline_agents = agents.get("discipline", [])
        source_types = {s["type"] for s in data["sources"]}

        # Discover all skills across all disciplines
        annotation_specs = []
        task_meta = []  # (discipline_name, lens_key) for final summary

        for agent_dir in discipline_agents:
            agent_cfg = yaml.safe_load(
                (agent_dir / "agent.yaml").read_text(encoding="utf-8")
            )
            disc_name = agent_cfg.get("name", agent_dir.name)
            disc_display = agent_cfg.get("display_name", disc_name)
            skills_dir = agent_dir / "skills"
            skills = discover_skills(skills_dir)

            if not skills:
                print(f"  WARNING: No skills found for {disc_name}, skipping")
                continue

            print(f"  {disc_name}: {len(skills)} skill(s) → {[s['key'] for s in skills]}")

            for skill in skills:
                annotation_specs.append(
                    (
                        agent_dir,
                        disc_name,
                        disc_display,
                        skill,
                    )
                )
                task_meta.append((disc_name, skill["key"]))

        max_concurrency = config.get("max_concurrency", 5)
        if provider == "minimax" and max_concurrency > 5:
            print(
                f"  [runtime] minimax configured for {max_concurrency} concurrent calls; "
                "clamping to 5 for stability"
            )
            max_concurrency = 5
        print(f"  Total: {len(annotation_specs)} LLM calls (max {max_concurrency} concurrent)")
        sem = asyncio.Semaphore(max_concurrency)

        async def run_lens(agent_dir: Path, disc_name: str, disc_display: str, skill: dict):
            async with sem:
                try:
                    result = await run_agent(
                        agent_dir,
                        "discipline",
                        {
                            "subject": subject,
                            "assembly": assembly,
                            "config": config,
                            "source_types": source_types,
                            "current_lens": skill,
                            "discipline_name": disc_name,
                            "discipline_display": disc_display,
                        },
                        config,
                    )
                    return disc_name, skill["key"], result, None
                except Exception as exc:
                    return disc_name, skill["key"], None, exc

        valid_annotations = []
        tasks = [
            asyncio.create_task(run_lens(agent_dir, disc_name, disc_display, skill))
            for agent_dir, disc_name, disc_display, skill in annotation_specs
        ]

        completed = 0
        total = len(tasks)
        for finished in asyncio.as_completed(tasks):
            disc, lens_key, result, error = await finished
            completed += 1

            if error is not None:
                print(f"  [{completed}/{total}] ✗ {disc}/{lens_key} FAILED: {error}")
                continue

            if isinstance(result, dict):
                result.setdefault("discipline", disc)
                result.setdefault("lens", lens_key)
            valid_annotations.append(result)
            construct_count = len(result.get("constructs", []))
            emergent_count = len(result.get("emergent_constructs", []))
            print(
                f"  [{completed}/{total}] ✓ {disc}/{lens_key}: "
                f"{construct_count} constructs, {emergent_count} emergent"
            )
            (lenses_dir / f"{disc}_{lens_key}.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        print(f"  → {len(valid_annotations)}/{len(annotation_specs)} successful")
        if len(valid_annotations) < len(annotation_specs):
            had_partial_failures = True
            _update_stage(
                "discipline",
                stage_status="partial_failed",
                output_ref=str(lenses_dir),
                error_message="one or more lens runs failed",
            )
        else:
            _update_stage("discipline", stage_status="success", output_ref=str(lenses_dir))

        construct_matrix = build_construct_matrix(valid_annotations, config)

        # ── Stage 3: Critic ───────────────────────────────────────
        current_stage = "critique"
        _update_stage("critique", stage_status="running", run_status="running")
        print("\n[Stage 3] Running critic...")
        critic_output = await run_agent(
            agents["critique"][0],
            "critique",
            {"subject": subject, "assembly": assembly, "analyses": valid_annotations},
            config,
        )
        flagged_count = len(critic_output.get("flagged_claims", []))
        confidence_count = len(critic_output.get("construct_confidence", []))
        print(f"  → {flagged_count} flagged claims, {confidence_count} construct confidence entries")
        critic_path = out_dir / "critic_output.json"
        critic_path.write_text(
            json.dumps(critic_output, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        _update_stage("critique", stage_status="success", output_ref=str(critic_path))

        # ── Stage 4: Synthesis ────────────────────────────────────
        current_stage = "synthesize"
        _update_stage("synthesize", stage_status="running", run_status="running")
        print("\n[Stage 4] Synthesizing...")
        synthesis = await run_agent(
            agents["synthesize"][0],
            "synthesize",
            {
                "subject": subject,
                "analyses": valid_annotations,
                "critic_output": critic_output,
                "construct_matrix": construct_matrix,
            },
            config,
        )
        findings_count = len(synthesis.get("summary_findings", []))
        tensions_count = len(synthesis.get("tensions", []))
        scenarios_count = len(synthesis.get("scenario_implications", []))
        print(f"  → {findings_count} findings, {tensions_count} tensions, {scenarios_count} scenario implications")
        synthesis_path = out_dir / "synthesis.json"
        synthesis_path.write_text(
            json.dumps(synthesis, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        _update_stage("synthesize", stage_status="success", output_ref=str(synthesis_path))

        # ── Stage 5: Report generation ────────────────────────────
        current_stage = "report"
        _update_stage("report", stage_status="running", run_status="running")
        print("\n[Stage 5] Generating report...")
        report = await run_agent(
            agents["report"][0],
            "report",
            {
                "subject": subject,
                "synthesis": synthesis,
                "analyses": valid_annotations,
                "critic_output": critic_output,
            },
            config,
        )
        report_path = out_dir / "report.md"
        report_path.write_text(report, encoding="utf-8")
        print(f"  → Report written ({len(report)} chars)")
        _update_stage("report", stage_status="success", output_ref=str(report_path))
        _update_stage(
            "report",
            run_status="partial_failed" if had_partial_failures else "completed",
        )

        # ── Done ──────────────────────────────────────────────────
        print(f"\n完成！所有产物已保存至 {out_dir}/")
        print(f"   assembly.json            ({timeline_count} events, {card_count} cards)")
        print(f"   lenses/                  ({len(valid_annotations)} lens annotations)")
        for disc, lens_key in task_meta:
            marker = "✓" if any(
                a.get("discipline") == disc and a.get("lens") == lens_key
                for a in valid_annotations
            ) else "✗"
            print(f"     {marker} {disc}_{lens_key}.json")
        print(f"   critic_output.json       ({flagged_count} flags)")
        print(f"   synthesis.json           ({findings_count} findings)")
        print(f"   report.md")
    except Exception as exc:
        _mark_run_failure(current_stage, exc)
        raise


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run python main.py <subject_dir>")
        print("Example: uv run python main.py data/elon_musk")
        sys.exit(1)
    asyncio.run(run(sys.argv[1]))

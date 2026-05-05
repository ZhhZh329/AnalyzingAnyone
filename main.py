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
    uv run python main.py --input-file run_input.json --feedback-out run_feedback.json
"""

import argparse
import asyncio
import json
import os
import re
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

TIER_SKILL_LIMITS = {
    "low": {
        "cs_engineering": 7,
        "economics": 6,
        "math": 6,
        "medicine": 5,
        "neuroscience": 6,
        "philosophy": 7,
        "psychology": 7,
        "sociology": 6,
    },
    "medium": {
        "cs_engineering": 16,
        "economics": 13,
        "math": 15,
        "medicine": 5,
        "neuroscience": 12,
        "philosophy": 15,
        "psychology": 15,
        "sociology": 9,
    },
    "high": {
        "cs_engineering": 34,
        "economics": 13,
        "math": 15,
        "medicine": 5,
        "neuroscience": 12,
        "philosophy": 29,
        "psychology": 33,
        "sociology": 9,
    },
}

DISCIPLINE_ALIASES = {
    "cs_eng": "cs_engineering",
}


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


def _resolve_output_dir(subject: str) -> Path:
    output_override = os.environ.get("ANALYZINGANYONE_OUTPUT_DIR")
    if output_override:
        return Path(output_override)
    return Path("output") / _subject_output_slug(subject)


def _subject_output_slug(subject: str) -> str:
    normalized = re.sub(r"[^\w]+", "_", subject.strip().lower(), flags=re.UNICODE)
    return normalized.strip("_") or "subject"


def _write_feedback(feedback_out: Path | None, payload: dict) -> None:
    if feedback_out is None:
        return
    feedback_out.parent.mkdir(parents=True, exist_ok=True)
    feedback_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _canonical_analysis_tier(value: str | None) -> str:
    raw = (value or "medium").strip().lower()
    mapping = {
        "low": "low",
        "medium": "medium",
        "high": "high",
        "lite": "low",
        "standard": "medium",
        "full": "high",
    }
    return mapping.get(raw, "medium")


def _discipline_limit_for_tier(discipline_name: str, analysis_tier: str) -> int | None:
    canonical_disc = DISCIPLINE_ALIASES.get(discipline_name, discipline_name)
    tier_limits = TIER_SKILL_LIMITS.get(analysis_tier, TIER_SKILL_LIMITS["medium"])
    return tier_limits.get(canonical_disc)


def _load_subject_dir(input_file: Path | None, subject_dir: str | None) -> str:
    if input_file is not None:
        payload = json.loads(input_file.read_text(encoding="utf-8"))
        resolved = payload.get("subject_dir")
        if not resolved:
            raise ValueError("input file is missing subject_dir")
        if payload.get("run_id") and not os.environ.get("ANALYZINGANYONE_RUN_ID"):
            os.environ["ANALYZINGANYONE_RUN_ID"] = str(payload["run_id"])
        if payload.get("trace_id") and not os.environ.get("ANALYZINGANYONE_TRACE_ID"):
            os.environ["ANALYZINGANYONE_TRACE_ID"] = str(payload["trace_id"])
        tier_from_payload = payload.get("analysis_tier")
        if not tier_from_payload and isinstance(payload.get("run_config"), dict):
            tier_from_payload = payload["run_config"].get("analysis_tier")
        os.environ["ANALYZINGANYONE_ANALYSIS_TIER"] = _canonical_analysis_tier(tier_from_payload)
        return str(resolved)
    if subject_dir:
        os.environ["ANALYZINGANYONE_ANALYSIS_TIER"] = _canonical_analysis_tier(
            os.environ.get("ANALYZINGANYONE_ANALYSIS_TIER")
        )
        return subject_dir
    raise ValueError("either <subject_dir> or --input-file must be provided")


def _resume_enabled() -> bool:
    return os.environ.get("ANALYZINGANYONE_RESUME", "").lower() in {"1", "true", "yes", "on"}


async def run(subject_dir: str, *, feedback_out: Path | None = None, check_only: bool = False) -> None:
    current_stage = "input_normalize"
    had_partial_failures = False
    subject = ""
    out_dir: Path | None = None
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
        out_dir = _resolve_output_dir(subject)
        out_dir.mkdir(parents=True, exist_ok=True)
        lenses_dir = out_dir / "lenses"
        lenses_dir.mkdir(exist_ok=True)
        resume_enabled = _resume_enabled()
        analysis_tier = _canonical_analysis_tier(os.environ.get("ANALYZINGANYONE_ANALYSIS_TIER"))
        print(f"Analysis tier: {analysis_tier}")
        if resume_enabled:
            print(f"Resume mode: enabled; existing artifacts in {out_dir}/ will be reused")

        if check_only:
            _write_feedback(
                feedback_out,
                {
                    "status": "checked",
                    "subject": subject,
                    "output_dir": str(out_dir),
                },
            )
            print(f"\nCheck-only 通过：输入目录可读取，输出目录将写入 {out_dir}/")
            return

        # ── Stage 1: Evidence assembly ────────────────────────────
        current_stage = "assemble"
        _update_stage("assemble", stage_status="running", run_status="running")
        assembly_path = out_dir / "assembly.json"
        assembly = None
        if resume_enabled and assembly_path.exists():
            try:
                cached_assembly = json.loads(assembly_path.read_text(encoding="utf-8"))
                if isinstance(cached_assembly, dict):
                    assembly = cached_assembly
                    print(f"\n[Stage 1] Reusing existing evidence assembly: {assembly_path}")
            except (OSError, json.JSONDecodeError) as exc:
                print(f"\n[Stage 1] Existing assembly is unreadable, regenerating: {exc}")
        if assembly is None:
            print("\n[Stage 1] Assembling evidence...")
            assembly = await run_agent(
                agents["assemble"][0],
                "assemble",
                {"subject": subject, "sources": data["sources"]},
                config,
            )
        if not isinstance(assembly, dict):
            assembly = {"timeline": [], "evidence_cards": []}
        if not isinstance(assembly.get("timeline"), list):
            assembly["timeline"] = []
        if not isinstance(assembly.get("evidence_cards"), list):
            assembly["evidence_cards"] = []
        timeline_count = len(assembly.get("timeline", []))
        card_count = len(assembly.get("evidence_cards", []))
        print(f"  -> {timeline_count} timeline events, {card_count} evidence cards")
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

            limit = _discipline_limit_for_tier(disc_name, analysis_tier)
            selected_skills = skills[:limit] if limit is not None else skills
            print(
                f"  {disc_name}: selected {len(selected_skills)} / total {len(skills)} "
                f"skill(s) (tier={analysis_tier})"
            )

            for skill in selected_skills:
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
        valid_annotations = []
        pending_specs = []
        for agent_dir, disc_name, disc_display, skill in annotation_specs:
            lens_key = skill["key"]
            lens_path = lenses_dir / f"{disc_name}_{lens_key}.json"
            if resume_enabled and lens_path.exists():
                try:
                    cached_result = json.loads(lens_path.read_text(encoding="utf-8"))
                    if isinstance(cached_result, dict):
                        cached_result.setdefault("discipline", disc_name)
                        cached_result.setdefault("lens", lens_key)
                        if not isinstance(cached_result.get("constructs"), list):
                            cached_result["constructs"] = []
                        else:
                            cached_result["constructs"] = [
                                c for c in cached_result["constructs"] if isinstance(c, dict)
                            ]
                        if not isinstance(cached_result.get("emergent_constructs"), list):
                            cached_result["emergent_constructs"] = []
                        else:
                            cached_result["emergent_constructs"] = [
                                e for e in cached_result["emergent_constructs"] if isinstance(e, dict)
                            ]
                        valid_annotations.append(cached_result)
                        continue
                    print(f"  [resume] Ignoring cached {disc_name}/{lens_key}: expected JSON object")
                except (OSError, json.JSONDecodeError) as exc:
                    print(f"  [resume] Ignoring cached {disc_name}/{lens_key}: {exc}")
            pending_specs.append((agent_dir, disc_name, disc_display, skill))

        if resume_enabled:
            print(f"  Resume: {len(valid_annotations)}/{len(annotation_specs)} lens output(s) reused")
        print(f"  Total: {len(pending_specs)} pending LLM calls (max {max_concurrency} concurrent)")
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

        tasks = [
            asyncio.create_task(run_lens(agent_dir, disc_name, disc_display, skill))
            for agent_dir, disc_name, disc_display, skill in pending_specs
        ]

        completed = len(valid_annotations)
        total = len(annotation_specs)
        for finished in asyncio.as_completed(tasks):
            disc, lens_key, result, error = await finished
            completed += 1

            if error is not None:
                print(f"  [{completed}/{total}] [fail] {disc}/{lens_key} FAILED: {error}")
                continue

            if not isinstance(result, dict):
                print(
                    f"  [{completed}/{total}] [fail] {disc}/{lens_key} FAILED: "
                    f"expected JSON object, got {type(result).__name__}"
                )
                continue

            result.setdefault("discipline", disc)
            result.setdefault("lens", lens_key)
            if not isinstance(result.get("constructs"), list):
                result["constructs"] = []
            else:
                result["constructs"] = [c for c in result["constructs"] if isinstance(c, dict)]
            if not isinstance(result.get("emergent_constructs"), list):
                result["emergent_constructs"] = []
            else:
                result["emergent_constructs"] = [
                    e for e in result["emergent_constructs"] if isinstance(e, dict)
                ]
            valid_annotations.append(result)
            construct_count = len(result["constructs"])
            emergent_count = len(result["emergent_constructs"])
            print(
                f"  [{completed}/{total}] [ok] {disc}/{lens_key}: "
                f"{construct_count} constructs, {emergent_count} emergent"
            )
            (lenses_dir / f"{disc}_{lens_key}.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        print(f"  -> {len(valid_annotations)}/{len(annotation_specs)} successful")
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
        # Normalize critic output shape. Some model responses can degrade to a list payload.
        if isinstance(critic_output, list):
            critic_output = {
                "flagged_claims": [x for x in critic_output if isinstance(x, dict)],
                "construct_confidence": [],
            }
        elif not isinstance(critic_output, dict):
            critic_output = {"flagged_claims": [], "construct_confidence": []}

        if not isinstance(critic_output.get("flagged_claims"), list):
            critic_output["flagged_claims"] = []
        else:
            critic_output["flagged_claims"] = [
                x for x in critic_output["flagged_claims"] if isinstance(x, dict)
            ]

        if not isinstance(critic_output.get("construct_confidence"), list):
            critic_output["construct_confidence"] = []
        else:
            critic_output["construct_confidence"] = [
                x for x in critic_output["construct_confidence"] if isinstance(x, dict)
            ]

        flagged_count = len(critic_output["flagged_claims"])
        confidence_count = len(critic_output["construct_confidence"])
        print(f"  -> {flagged_count} flagged claims, {confidence_count} construct confidence entries")
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
        # Normalize synthesis payload shape. Some model responses can degrade to a list.
        if isinstance(synthesis, list):
            synthesis = {
                "summary_findings": [x for x in synthesis if isinstance(x, dict)],
                "tensions": [],
                "scenario_implications": [],
            }
        elif not isinstance(synthesis, dict):
            synthesis = {"summary_findings": [], "tensions": [], "scenario_implications": []}

        if not isinstance(synthesis.get("summary_findings"), list):
            synthesis["summary_findings"] = []
        else:
            synthesis["summary_findings"] = [
                x for x in synthesis["summary_findings"] if isinstance(x, dict)
            ]

        if not isinstance(synthesis.get("tensions"), list):
            synthesis["tensions"] = []
        else:
            synthesis["tensions"] = [x for x in synthesis["tensions"] if isinstance(x, dict)]

        if not isinstance(synthesis.get("scenario_implications"), list):
            synthesis["scenario_implications"] = []
        else:
            synthesis["scenario_implications"] = [
                x for x in synthesis["scenario_implications"] if isinstance(x, dict)
            ]

        findings_count = len(synthesis["summary_findings"])
        tensions_count = len(synthesis["tensions"])
        scenarios_count = len(synthesis["scenario_implications"])
        print(f"  -> {findings_count} findings, {tensions_count} tensions, {scenarios_count} scenario implications")
        synthesis_path = out_dir / "synthesis.json"
        synthesis_path.write_text(
            json.dumps(synthesis, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        _update_stage("synthesize", stage_status="success", output_ref=str(synthesis_path))

        # ── Stage 5: Report generation ────────────────────────────
        current_stage = "report"
        _update_stage("report", stage_status="running", run_status="running")
        print("\n[Stage 5] Generating report...")
        report_time_utc = datetime.now(timezone.utc).isoformat()
        report_time_local = datetime.now().astimezone().isoformat()
        report = await run_agent(
            agents["report"][0],
            "report",
            {
                "subject": subject,
                "synthesis": synthesis,
                "analyses": valid_annotations,
                "critic_output": critic_output,
                "current_time_utc": report_time_utc,
                "current_time_local": report_time_local,
                "time_policy": "Use only provided timestamps. Do not infer current date/time beyond these fields.",
            },
            config,
        )
        if not isinstance(report, str):
            report = str(report)
        # Enforce runtime timestamp in report header without regex (encoding-safe).
        fixed_cn = f"报告生成时间：{report_time_local}（UTC: {report_time_utc}）"
        fixed_en = f"Report generated at: {report_time_local} (UTC: {report_time_utc})"
        report_lines = report.splitlines()
        replaced = False
        for idx, line in enumerate(report_lines):
            if line.startswith("报告生成时间："):
                report_lines[idx] = fixed_cn
                replaced = True
                break
            if line.startswith("Report generated at:"):
                report_lines[idx] = fixed_en
                replaced = True
                break
        if replaced:
            report = "\n".join(report_lines)
        else:
            report = f"{fixed_cn}\n\n{report}"
        report_path = out_dir / "report.md"
        report_path.write_text(report, encoding="utf-8")
        print(f"  -> Report written ({len(report)} chars)")
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
            marker = "[ok]" if any(
                a.get("discipline") == disc and a.get("lens") == lens_key
                for a in valid_annotations
            ) else "[fail]"
            print(f"     {marker} {disc}_{lens_key}.json")
        print(f"   critic_output.json       ({flagged_count} flags)")
        print(f"   synthesis.json           ({findings_count} findings)")
        print(f"   report.md")
        _write_feedback(
            feedback_out,
            {
                "status": "ok",
                "subject": subject,
                "output_dir": str(out_dir),
                "timeline_count": timeline_count,
                "evidence_card_count": card_count,
                "lens_output_count": len(valid_annotations),
                "flagged_claim_count": flagged_count,
                "summary_finding_count": findings_count,
                "report_path": str(report_path),
            },
        )
    except Exception as exc:
        if feedback_out is not None:
            _write_feedback(
                feedback_out,
                {
                    "status": "failed",
                    "subject": subject,
                    "output_dir": str(out_dir) if out_dir is not None else None,
                    "message": str(exc),
                    "stage_key": current_stage,
                },
            )
        _mark_run_failure(current_stage, exc)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the AnalyzingAnyone workflow.")
    parser.add_argument("subject_dir", nargs="?", help="input directory containing manifest.json and sources/")
    parser.add_argument("--input-file", dest="input_file", help="json file containing subject_dir and runtime metadata")
    parser.add_argument("--feedback-out", dest="feedback_out", help="where to write workflow feedback json")
    parser.add_argument("--check-only", dest="check_only", action="store_true", help="validate inputs without running the full workflow")
    args = parser.parse_args()

    try:
        resolved_subject_dir = _load_subject_dir(
            Path(args.input_file) if args.input_file else None,
            args.subject_dir,
        )
    except Exception as exc:
        print(f"Input resolution failed: {exc}", file=sys.stderr)
        sys.exit(1)

    asyncio.run(
        run(
            resolved_subject_dir,
            feedback_out=Path(args.feedback_out) if args.feedback_out else None,
            check_only=args.check_only,
        )
    )

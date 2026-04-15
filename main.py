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

import argparse
import asyncio
import json
import sys
from pathlib import Path

import yaml

import loader
from runtime import (
    build_construct_matrix,
    discover_agents,
    discover_skills,
    run_agent,
)


ASSEMBLY_CHUNK_CHAR_BUDGET = 4000
ASSEMBLY_TIMELINE_LIMIT = 40
ASSEMBLY_EVIDENCE_LIMIT = 60
CRITIC_EVIDENCE_LIMIT = 30
CRITIC_ANALYSES_LIMIT = 10
SYNTH_ANALYSES_LIMIT = 10
SYNTH_CONSTRUCT_MATRIX_CHAR_LIMIT = 12000
SYNTH_CRITIC_FLAGS_LIMIT = 30
REPORT_ANALYSES_LIMIT = 8
REPORT_CRITIC_FLAGS_LIMIT = 20


def _read_subject_dir_from_input_file(input_file: Path) -> str:
    """
    Accept either:
    - plain text file containing a subject_dir path
    - JSON file containing {"subject_dir": "..."} or {"input": "..."}
    """
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    raw = input_file.read_text(encoding="utf-8").strip()
    if not raw:
        raise ValueError(f"Input file is empty: {input_file}")

    if input_file.suffix.lower() == ".json":
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in input file: {input_file}") from exc
        subject_dir = (payload.get("subject_dir") or payload.get("input") or "").strip()
        if not subject_dir:
            raise ValueError(
                f"JSON input file must contain 'subject_dir' or 'input': {input_file}"
            )
        return subject_dir

    return raw


def _build_feedback_payload(
    status: str,
    subject: str,
    output_dir: Path,
    timeline_count: int = 0,
    evidence_count: int = 0,
    lens_count: int = 0,
    flagged_count: int = 0,
    findings_count: int = 0,
    report_path: Path | None = None,
    message: str = "",
) -> dict:
    payload = {
        "status": status,
        "subject": subject,
        "output_dir": str(output_dir),
        "timeline_count": timeline_count,
        "evidence_card_count": evidence_count,
        "lens_output_count": lens_count,
        "flagged_claim_count": flagged_count,
        "summary_finding_count": findings_count,
        "message": message,
    }
    if report_path is not None:
        payload["report_path"] = str(report_path)
    return payload


def _trim_text(value: str, max_chars: int = 300) -> str:
    text = (value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def _prepare_critic_inputs(assembly: dict, analyses: list[dict]) -> tuple[dict, list[dict]]:
    """
    MiniMax currently errors on oversized context for critic.
    Keep the critic stage stable by sending a compact, representative subset.
    """
    evidence_cards = assembly.get("evidence_cards", [])
    timeline = assembly.get("timeline", [])

    selected_cards = evidence_cards[:CRITIC_EVIDENCE_LIMIT]
    selected_event_ids = {
        ref
        for card in selected_cards
        for ref in card.get("timeline_refs", [])
    }
    selected_timeline = [evt for evt in timeline if evt.get("id") in selected_event_ids]

    compact_assembly = {
        "subject": assembly.get("subject", ""),
        "timeline": selected_timeline,
        "evidence_cards": selected_cards,
    }

    compact_analyses: list[dict] = []
    for ann in analyses[:CRITIC_ANALYSES_LIMIT]:
        ann_copy = dict(ann)
        constructs = []
        for c in ann_copy.get("constructs", []):
            c_copy = dict(c)
            c_copy["assessment"] = _trim_text(c_copy.get("assessment", ""), 260)
            c_copy["finding"] = _trim_text(c_copy.get("finding", ""), 260)
            constructs.append(c_copy)
        ann_copy["constructs"] = constructs
        emergent = []
        for e in ann_copy.get("emergent_constructs", []):
            e_copy = dict(e)
            e_copy["finding"] = _trim_text(e_copy.get("finding", ""), 260)
            emergent.append(e_copy)
        ann_copy["emergent_constructs"] = emergent
        compact_analyses.append(ann_copy)

    return compact_assembly, compact_analyses


def _prepare_synthesis_inputs(
    analyses: list[dict],
    critic_output: dict,
    construct_matrix: str,
) -> tuple[list[dict], dict, str]:
    """
    Keep synthesis payload within provider context limits.
    """
    compact_analyses: list[dict] = []
    for ann in analyses[:SYNTH_ANALYSES_LIMIT]:
        ann_copy = dict(ann)
        constructs = []
        for c in ann_copy.get("constructs", []):
            c_copy = dict(c)
            c_copy["assessment"] = _trim_text(c_copy.get("assessment", ""), 240)
            c_copy["finding"] = _trim_text(c_copy.get("finding", ""), 240)
            constructs.append(c_copy)
        ann_copy["constructs"] = constructs
        emergent = []
        for e in ann_copy.get("emergent_constructs", []):
            e_copy = dict(e)
            e_copy["finding"] = _trim_text(e_copy.get("finding", ""), 240)
            emergent.append(e_copy)
        ann_copy["emergent_constructs"] = emergent
        compact_analyses.append(ann_copy)

    compact_critic = dict(critic_output)
    compact_critic["flagged_claims"] = (critic_output.get("flagged_claims", []) or [])[
        :SYNTH_CRITIC_FLAGS_LIMIT
    ]

    compact_matrix = _trim_text(
        construct_matrix or "",
        SYNTH_CONSTRUCT_MATRIX_CHAR_LIMIT,
    )

    return compact_analyses, compact_critic, compact_matrix


def _prepare_report_inputs(
    analyses: list[dict],
    critic_output: dict,
    synthesis: dict,
) -> tuple[list[dict], dict, dict]:
    """
    Keep report payload compact to avoid provider context-window errors.
    """
    compact_analyses: list[dict] = []
    for ann in analyses[:REPORT_ANALYSES_LIMIT]:
        ann_copy = dict(ann)
        constructs = []
        for c in ann_copy.get("constructs", []):
            c_copy = dict(c)
            c_copy["assessment"] = _trim_text(c_copy.get("assessment", ""), 220)
            c_copy["finding"] = _trim_text(c_copy.get("finding", ""), 220)
            constructs.append(c_copy)
        ann_copy["constructs"] = constructs
        emergent = []
        for e in ann_copy.get("emergent_constructs", []):
            e_copy = dict(e)
            e_copy["finding"] = _trim_text(e_copy.get("finding", ""), 220)
            emergent.append(e_copy)
        ann_copy["emergent_constructs"] = emergent
        compact_analyses.append(ann_copy)

    compact_critic = dict(critic_output)
    compact_critic["flagged_claims"] = (critic_output.get("flagged_claims", []) or [])[
        :REPORT_CRITIC_FLAGS_LIMIT
    ]

    compact_synthesis = dict(synthesis)
    compact_synthesis["summary_findings"] = (synthesis.get("summary_findings", []) or [])[:20]
    compact_synthesis["complementary_views"] = (synthesis.get("complementary_views", []) or [])[:12]
    compact_synthesis["tensions"] = (synthesis.get("tensions", []) or [])[:12]
    compact_synthesis["scenario_implications"] = (synthesis.get("scenario_implications", []) or [])[:12]

    return compact_analyses, compact_critic, compact_synthesis


def _coerce_to_dict_output(value: object, stage_name: str) -> dict:
    """
    Normalize agent outputs that sometimes come back as a list.
    """
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                print(
                    f"  [{stage_name}] WARNING: got list output, using first dict item",
                    flush=True,
                )
                return item
        print(
            f"  [{stage_name}] WARNING: got list output with no dict item, using empty object",
            flush=True,
        )
        return {}
    print(
        f"  [{stage_name}] WARNING: unexpected output type={type(value).__name__}, using empty object",
        flush=True,
    )
    return {}


def chunk_sources_by_size(sources: list[dict], max_chars: int = ASSEMBLY_CHUNK_CHAR_BUDGET) -> list[list[dict]]:
    """
    Split sources into stable-size chunks so evidence assembly doesn't rely on one
    giant prompt. The heuristic budget counts source content plus a small header
    allowance for ids/type/date/context metadata.
    """
    chunks: list[list[dict]] = []
    current: list[dict] = []
    current_chars = 0

    for source in sources:
        source_chars = (
            len(source.get("content", ""))
            + len(source.get("context", ""))
            + len(source.get("id", ""))
            + len(source.get("type", ""))
            + len(source.get("date", ""))
            + 80
        )
        if current and current_chars + source_chars > max_chars:
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(source)
        current_chars += source_chars

    if current:
        chunks.append(current)

    return chunks or [sources]


def distribute_limit(total: int, buckets: int) -> list[int]:
    """Distribute a global item limit across N chunks as evenly as possible."""
    if buckets <= 0:
        return []
    base = total // buckets
    remainder = total % buckets
    return [base + (1 if idx < remainder else 0) for idx in range(buckets)]


def parse_date_key(date_value: str) -> tuple[int, int, int, str]:
    """
    Best-effort sort key for YYYY / YYYY-MM / YYYY-MM-DD strings.
    Unknown pieces sort early within the same year.
    """
    raw = (date_value or "").strip()
    parts = raw.split("-") if raw else []
    numbers: list[int] = []
    for idx in range(3):
        if idx < len(parts) and parts[idx].isdigit():
            numbers.append(int(parts[idx]))
        else:
            numbers.append(0)
    return numbers[0], numbers[1], numbers[2], raw


def normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def merge_assemblies(subject: str, assemblies: list[dict]) -> dict:
    """
    Merge chunked evidence-assembly outputs into one globally indexed assembly.
    Event/card ids are re-assigned so downstream stages see a consistent corpus.
    """
    indexed_events: list[tuple[tuple[int, int, int, str], int, dict]] = []
    for chunk_idx, assembly in enumerate(assemblies):
        for event in assembly.get("timeline", []):
            indexed_events.append((parse_date_key(event.get("date", "")), chunk_idx, event))
    indexed_events.sort(key=lambda item: (item[0], item[1], item[2].get("id", "")))

    deduped_events: list[tuple[tuple[int, int, int, str], int, dict]] = []
    event_seen: dict[tuple[str, str, str], int] = {}
    for sort_key, chunk_idx, event in indexed_events:
        dedupe_key = (
            event.get("date", ""),
            normalize_text(event.get("what", "")),
            normalize_text(event.get("context", "")),
        )
        existing_idx = event_seen.get(dedupe_key)
        if existing_idx is None:
            merged_event = dict(event)
            merged_event["source_ids"] = list(dict.fromkeys(event.get("source_ids", [])))
            deduped_events.append((sort_key, chunk_idx, merged_event))
            event_seen[dedupe_key] = len(deduped_events) - 1
        else:
            existing_event = deduped_events[existing_idx][2]
            combined_sources = existing_event.get("source_ids", []) + event.get("source_ids", [])
            existing_event["source_ids"] = list(dict.fromkeys(combined_sources))

    event_id_map: dict[tuple[int, str], str] = {}
    merged_events: list[dict] = []
    for position, (_, chunk_idx, event) in enumerate(deduped_events, start=1):
        old_id = event.get("id", f"evt_local_{chunk_idx}_{position}")
        new_id = f"evt_{position:03d}"
        event_id_map[(chunk_idx, old_id)] = new_id
        merged_event = dict(event)
        merged_event["id"] = new_id
        merged_events.append(merged_event)

    indexed_cards: list[tuple[tuple[int, int, int, str], int, dict]] = []
    for chunk_idx, assembly in enumerate(assemblies):
        for card in assembly.get("evidence_cards", []):
            merged_card = dict(card)
            merged_card["timeline_refs"] = [
                event_id_map[(chunk_idx, ref)]
                for ref in card.get("timeline_refs", [])
                if (chunk_idx, ref) in event_id_map
            ]
            indexed_cards.append((parse_date_key(card.get("date", "")), chunk_idx, merged_card))
    indexed_cards.sort(key=lambda item: (item[0], item[1], item[2].get("source_id", ""), item[2].get("summary", "")))

    deduped_cards: list[dict] = []
    card_seen: dict[tuple[str, str, str, str, str], int] = {}
    for _, _, card in indexed_cards:
        dedupe_key = (
            card.get("source_id", ""),
            card.get("kind", ""),
            card.get("date", ""),
            normalize_text(card.get("summary", "")),
            normalize_text(card.get("verbatim_quote", "")),
        )
        existing_idx = card_seen.get(dedupe_key)
        if existing_idx is None:
            merged_card = dict(card)
            merged_card["timeline_refs"] = list(dict.fromkeys(card.get("timeline_refs", [])))
            deduped_cards.append(merged_card)
            card_seen[dedupe_key] = len(deduped_cards) - 1
        else:
            existing_card = deduped_cards[existing_idx]
            combined_refs = existing_card.get("timeline_refs", []) + card.get("timeline_refs", [])
            existing_card["timeline_refs"] = list(dict.fromkeys(combined_refs))

    merged_cards: list[dict] = []
    for position, card in enumerate(deduped_cards, start=1):
        merged_card = dict(card)
        merged_card["id"] = f"ev_{position:03d}"
        merged_cards.append(merged_card)

    return {
        "subject": subject,
        "timeline": merged_events,
        "evidence_cards": merged_cards,
    }


async def assemble_evidence(agent_dir: Path, subject: str, sources: list[dict], config: dict) -> dict:
    """
    Run evidence assembly on a manageable chunk size and merge the results.
    This avoids single oversized requests that can hang on some providers.
    """
    chunks = chunk_sources_by_size(sources)
    if len(chunks) == 1:
        return await run_agent(
            agent_dir,
            "assemble",
            {
                "subject": subject,
                "sources": sources,
                "timeline_limit": ASSEMBLY_TIMELINE_LIMIT,
                "evidence_limit": ASSEMBLY_EVIDENCE_LIMIT,
            },
            config,
        )

    timeline_limits = distribute_limit(ASSEMBLY_TIMELINE_LIMIT, len(chunks))
    evidence_limits = distribute_limit(ASSEMBLY_EVIDENCE_LIMIT, len(chunks))
    partial_assemblies: list[dict] = []

    for idx, chunk in enumerate(chunks):
        timeline_limit = timeline_limits[idx]
        evidence_limit = evidence_limits[idx]
        approx_chars = sum(len(source.get("content", "")) for source in chunk)
        print(
            f"  [assemble] chunk {idx + 1}/{len(chunks)}: "
            f"{len(chunk)} sources, ~{approx_chars} chars, "
            f"limit {timeline_limit} events / {evidence_limit} cards",
            flush=True,
        )
        partial = await run_agent(
            agent_dir,
            "assemble",
            {
                "subject": subject,
                "sources": chunk,
                "timeline_limit": timeline_limit,
                "evidence_limit": evidence_limit,
            },
            config,
        )
        print(
            f"  [assemble] chunk {idx + 1}/{len(chunks)} complete: "
            f"{len(partial.get('timeline', []))} events, "
            f"{len(partial.get('evidence_cards', []))} cards",
            flush=True,
        )
        partial_assemblies.append(partial)

    return merge_assemblies(subject, partial_assemblies)


async def run(subject_dir: str) -> dict:
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
    print(f"Provider: {provider}", flush=True)
    print(f"Model:    {model}", flush=True)

    # ── Discover agents ───────────────────────────────────────
    agents = discover_agents(Path("agents"))
    print(f"Discovered agents: { {k: [p.name for p in v] for k, v in agents.items()} }", flush=True)

    # ── Load data ─────────────────────────────────────────────
    subject_path = Path(subject_dir)
    data = loader.load(subject_path)
    subject = data["subject"]
    print(f"\nSubject: {subject}", flush=True)
    print(f"Sources loaded: {len(data['sources'])}", flush=True)

    # Prepare output directory
    out_dir = Path("output") / subject.lower().replace(" ", "_")
    out_dir.mkdir(parents=True, exist_ok=True)
    lenses_dir = out_dir / "lenses"
    lenses_dir.mkdir(exist_ok=True)

    # ── Stage 1: Evidence assembly ────────────────────────────
    print("\n[Stage 1] Assembling evidence...", flush=True)
    assembly = await assemble_evidence(
        agents["assemble"][0],
        subject,
        data["sources"],
        config,
    )
    timeline_count = len(assembly.get("timeline", []))
    card_count = len(assembly.get("evidence_cards", []))
    print(f"  [assemble] {timeline_count} timeline events, {card_count} evidence cards", flush=True)
    (out_dir / "assembly.json").write_text(
        json.dumps(assembly, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── Stage 2: Sub-lens annotations (all skills in parallel) ─
    print("\n[Stage 2] Running sub-lens annotations in parallel...", flush=True)
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
            print(f"  WARNING: No skills found for {disc_name}, skipping", flush=True)
            continue

        print(f"  {disc_name}: {len(skills)} skill(s) -> {[s['key'] for s in skills]}", flush=True)

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
            "clamping to 5 for stability",
            flush=True,
        )
        max_concurrency = 5
    print(f"  Total: {len(annotation_specs)} LLM calls (max {max_concurrency} concurrent)", flush=True)
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
            print(f"  [{completed}/{total}] [fail] {disc}/{lens_key} FAILED: {error}", flush=True)
            continue

        # Normalize unexpected outputs from providers/models.
        normalized_result = None
        if isinstance(result, dict):
            normalized_result = result
        elif isinstance(result, list):
            for item in result:
                if isinstance(item, dict):
                    normalized_result = item
                    break
            if normalized_result is None:
                print(
                    f"  [{completed}/{total}] ! {disc}/{lens_key}: "
                    "unexpected list output (no dict item), skipped",
                    flush=True,
                )
                continue
        else:
            print(
                f"  [{completed}/{total}] ! {disc}/{lens_key}: "
                f"unexpected output type={type(result).__name__}, skipped",
                flush=True,
            )
            continue

        normalized_result.setdefault("discipline", disc)
        normalized_result.setdefault("lens", lens_key)
        valid_annotations.append(normalized_result)
        construct_count = len(normalized_result.get("constructs", []))
        emergent_count = len(normalized_result.get("emergent_constructs", []))
        print(
            f"  [{completed}/{total}] [ok] {disc}/{lens_key}: "
            f"{construct_count} constructs, {emergent_count} emergent",
            flush=True,
        )
        # Save individual lens file
        (lenses_dir / f"{disc}_{lens_key}.json").write_text(
            json.dumps(normalized_result, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(f"  [discipline] {len(valid_annotations)}/{len(annotation_specs)} successful", flush=True)

    # Build construct matrix for synthesizer
    construct_matrix = build_construct_matrix(valid_annotations, config)

    # ── Stage 3: Critic ───────────────────────────────────────
    print("\n[Stage 3] Running critic...", flush=True)
    critic_assembly, critic_analyses = _prepare_critic_inputs(assembly, valid_annotations)
    print(
        f"  [critic] compact payload: "
        f"{len(critic_assembly.get('evidence_cards', []))} cards, "
        f"{len(critic_analyses)} analyses",
        flush=True,
    )
    critic_raw = await run_agent(
        agents["critique"][0],
        "critique",
        {"subject": subject, "assembly": critic_assembly, "analyses": critic_analyses},
        config,
    )
    critic_output = _coerce_to_dict_output(critic_raw, "critic")
    flagged_count = len(critic_output.get("flagged_claims", []))
    confidence_count = len(critic_output.get("construct_confidence", []))
    print(f"  [critic] {flagged_count} flagged claims, {confidence_count} construct confidence entries", flush=True)
    (out_dir / "critic_output.json").write_text(
        json.dumps(critic_output, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── Stage 4: Synthesis ────────────────────────────────────
    print("\n[Stage 4] Synthesizing...", flush=True)
    synth_analyses, synth_critic, synth_matrix = _prepare_synthesis_inputs(
        valid_annotations,
        critic_output,
        construct_matrix,
    )
    print(
        f"  [synthesize] compact payload: "
        f"{len(synth_analyses)} analyses, "
        f"{len(synth_critic.get('flagged_claims', []))} flags, "
        f"{len(synth_matrix)} chars matrix",
        flush=True,
    )
    synthesis_raw = await run_agent(
        agents["synthesize"][0],
        "synthesize",
        {
            "subject": subject,
            "analyses": synth_analyses,
            "critic_output": synth_critic,
            "construct_matrix": synth_matrix,
        },
        config,
    )
    synthesis = _coerce_to_dict_output(synthesis_raw, "synthesize")
    findings_count = len(synthesis.get("summary_findings", []))
    tensions_count = len(synthesis.get("tensions", []))
    scenarios_count = len(synthesis.get("scenario_implications", []))
    print(
        f"  [synthesize] {findings_count} findings, {tensions_count} tensions, "
        f"{scenarios_count} scenario implications",
        flush=True,
    )
    (out_dir / "synthesis.json").write_text(
        json.dumps(synthesis, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── Stage 5: Report generation ────────────────────────────
    print("\n[Stage 5] Generating report...", flush=True)
    report_analyses, report_critic, report_synthesis = _prepare_report_inputs(
        valid_annotations,
        critic_output,
        synthesis,
    )
    print(
        f"  [report] compact payload: "
        f"{len(report_analyses)} analyses, "
        f"{len(report_critic.get('flagged_claims', []))} flags, "
        f"{len(report_synthesis.get('summary_findings', []))} findings",
        flush=True,
    )
    report = await run_agent(
        agents["report"][0],
        "report",
        {
            "subject": subject,
            "synthesis": report_synthesis,
            "analyses": report_analyses,
            "critic_output": report_critic,
        },
        config,
    )
    report_path = out_dir / "report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"  [report] written ({len(report)} chars)", flush=True)

    # ── Done ──────────────────────────────────────────────────
    print(f"\n完成！所有产物已保存至 {out_dir}/", flush=True)
    print(f"   assembly.json            ({timeline_count} events, {card_count} cards)", flush=True)
    print(f"   lenses/                  ({len(valid_annotations)} lens annotations)", flush=True)
    for disc, lens_key in task_meta:
        marker = "[ok]" if any(
            a.get("discipline") == disc and a.get("lens") == lens_key
            for a in valid_annotations
        ) else "[fail]"
        print(f"     {marker} {disc}_{lens_key}.json", flush=True)
    print(f"   critic_output.json       ({flagged_count} flags)", flush=True)
    print(f"   synthesis.json           ({findings_count} findings)", flush=True)
    print(f"   report.md", flush=True)

    return _build_feedback_payload(
        status="ok",
        subject=subject,
        output_dir=out_dir,
        timeline_count=timeline_count,
        evidence_count=card_count,
        lens_count=len(valid_annotations),
        flagged_count=flagged_count,
        findings_count=findings_count,
        report_path=report_path,
        message=f"Pipeline completed for subject_dir={subject_path}",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run AnalyzingAnyone pipeline with optional file-based input/output feedback."
    )
    parser.add_argument(
        "subject_dir",
        nargs="?",
        help="Subject directory, e.g. data/elon_musk",
    )
    parser.add_argument(
        "--input-file",
        type=str,
        help="Read subject_dir from a file (text path or JSON with subject_dir/input key).",
    )
    parser.add_argument(
        "--feedback-out",
        type=str,
        help="Write a JSON feedback file with run status and artifact locations.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only validate input and dataset availability, do not call LLM.",
    )
    args = parser.parse_args()

    if args.subject_dir and args.input_file:
        print("Use either <subject_dir> or --input-file, not both.")
        sys.exit(1)

    if args.input_file:
        try:
            final_subject_dir = _read_subject_dir_from_input_file(Path(args.input_file))
        except Exception as exc:
            print(f"Input parse failed: {exc}")
            sys.exit(1)
    elif args.subject_dir:
        final_subject_dir = args.subject_dir
    else:
        print("Usage: uv run python main.py <subject_dir>")
        print("   or: uv run python main.py --input-file input.txt")
        sys.exit(1)

    subject_path = Path(final_subject_dir)
    manifest_path = subject_path / "manifest.json"
    if not subject_path.exists():
        print(f"Subject directory not found: {subject_path}")
        sys.exit(1)
    if not manifest_path.exists():
        print(f"manifest.json not found in: {subject_path}")
        sys.exit(1)

    if args.check_only:
        data = loader.load(subject_path)
        subject = data["subject"]
        output_dir = Path("output") / subject.lower().replace(" ", "_")
        feedback = _build_feedback_payload(
            status="checked",
            subject=subject,
            output_dir=output_dir,
            message=f"Input valid. Ready to run full pipeline for {final_subject_dir}",
        )
    else:
        feedback = asyncio.run(run(final_subject_dir))

    if args.feedback_out:
        feedback_path = Path(args.feedback_out)
        feedback_path.parent.mkdir(parents=True, exist_ok=True)
        feedback_path.write_text(
            json.dumps(feedback, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Feedback written to: {feedback_path}")

    print(json.dumps(feedback, ensure_ascii=False, indent=2))

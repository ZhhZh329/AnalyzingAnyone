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


async def run(subject_dir: str) -> None:
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
    data = loader.load(Path(subject_dir))
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
    print(f"  → {timeline_count} timeline events, {card_count} evidence cards", flush=True)
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

        print(f"  {disc_name}: {len(skills)} skill(s) → {[s['key'] for s in skills]}", flush=True)

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
            print(f"  [{completed}/{total}] ✗ {disc}/{lens_key} FAILED: {error}", flush=True)
            continue

        # Ensure discipline and lens fields are set
        if isinstance(result, dict):
            result.setdefault("discipline", disc)
            result.setdefault("lens", lens_key)
        valid_annotations.append(result)
        construct_count = len(result.get("constructs", []))
        emergent_count = len(result.get("emergent_constructs", []))
        print(
            f"  [{completed}/{total}] ✓ {disc}/{lens_key}: "
            f"{construct_count} constructs, {emergent_count} emergent",
            flush=True,
        )
        # Save individual lens file
        (lenses_dir / f"{disc}_{lens_key}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(f"  → {len(valid_annotations)}/{len(annotation_specs)} successful", flush=True)

    # Build construct matrix for synthesizer
    construct_matrix = build_construct_matrix(valid_annotations, config)

    # ── Stage 3: Critic ───────────────────────────────────────
    print("\n[Stage 3] Running critic...", flush=True)
    critic_output = await run_agent(
        agents["critique"][0],
        "critique",
        {"subject": subject, "assembly": assembly, "analyses": valid_annotations},
        config,
    )
    flagged_count = len(critic_output.get("flagged_claims", []))
    confidence_count = len(critic_output.get("construct_confidence", []))
    print(f"  → {flagged_count} flagged claims, {confidence_count} construct confidence entries", flush=True)
    (out_dir / "critic_output.json").write_text(
        json.dumps(critic_output, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── Stage 4: Synthesis ────────────────────────────────────
    print("\n[Stage 4] Synthesizing...", flush=True)
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
    print(f"  → {findings_count} findings, {tensions_count} tensions, {scenarios_count} scenario implications", flush=True)
    (out_dir / "synthesis.json").write_text(
        json.dumps(synthesis, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── Stage 5: Report generation ────────────────────────────
    print("\n[Stage 5] Generating report...", flush=True)
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
    print(f"  → Report written ({len(report)} chars)", flush=True)

    # ── Done ──────────────────────────────────────────────────
    print(f"\n完成！所有产物已保存至 {out_dir}/", flush=True)
    print(f"   assembly.json            ({timeline_count} events, {card_count} cards)", flush=True)
    print(f"   lenses/                  ({len(valid_annotations)} lens annotations)", flush=True)
    for disc, lens_key in task_meta:
        marker = "✓" if any(
            a.get("discipline") == disc and a.get("lens") == lens_key
            for a in valid_annotations
        ) else "✗"
        print(f"     {marker} {disc}_{lens_key}.json", flush=True)
    print(f"   critic_output.json       ({flagged_count} flags)", flush=True)
    print(f"   synthesis.json           ({findings_count} findings)", flush=True)
    print(f"   report.md", flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run python main.py <subject_dir>")
        print("Example: uv run python main.py data/elon_musk")
        sys.exit(1)

    asyncio.run(run(sys.argv[1]))

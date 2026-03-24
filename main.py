"""
main.py — Orchestrator for the multi-disciplinary human profiling pipeline.

Usage:
    python main.py data/elon_musk
"""

import asyncio
import json
import sys
from pathlib import Path

import yaml

import loader
from runtime import discover_agents, run_agent


async def run(subject_dir: str) -> None:
    # ── Load config ───────────────────────────────────────────
    config = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))

    # Load llm.yaml and merge into config (keys, api_bases, default provider/model)
    llm_path = Path("llm.yaml")
    if llm_path.exists():
        llm = yaml.safe_load(llm_path.read_text(encoding="utf-8")) or {}
        config["keys"]      = llm.get("keys", {})
        config["api_bases"] = llm.get("api_bases", {})
        config.setdefault("provider", llm.get("default", {}).get("provider", "anthropic"))
        config.setdefault("model",    llm.get("default", {}).get("model", ""))

    provider = config.get("provider", "anthropic")
    model    = config.get("model", "")
    print(f"Provider: {provider}")
    print(f"Model:    {model}")

    # ── Discover agents ───────────────────────────────────────
    agents = discover_agents(Path("agents"))
    print(f"Discovered agents: { {k: [p.name for p in v] for k, v in agents.items()} }")

    # ── Load data ─────────────────────────────────────────────
    data = loader.load(Path(subject_dir))
    subject = data["subject"]
    print(f"\nSubject: {subject}")
    print(f"Sources loaded: {len(data['sources'])}")

    # Prepare output directory
    out_dir = Path("output") / subject.lower().replace(" ", "_")
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Stage 1: Event extraction ─────────────────────────────
    print("\n[Stage 1] Extracting events...")
    events = await run_agent(
        agents["extract"][0],
        "extract",
        {"subject": subject, "sources": data["sources"]},
        config,
    )
    event_count = len(events.get("events", []))
    print(f"  → {event_count} events extracted")
    (out_dir / "events.json").write_text(
        json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── Stage 2: Discipline analyses (parallel) ───────────────
    print("\n[Stage 2] Running discipline analyses in parallel...")
    discipline_agents = agents.get("discipline", [])
    print(f"  Disciplines: {[p.name for p in discipline_agents]}")

    analyses = list(
        await asyncio.gather(*[
            run_agent(
                agent_dir,
                "discipline",
                {"subject": subject, "events": events, "config": config},
                config,
            )
            for agent_dir in discipline_agents
        ])
    )

    for analysis in analyses:
        discipline = analysis.get("discipline", "unknown")
        anchored_count = len(analysis.get("anchored", {}))
        emergent_count = len(analysis.get("emergent", []))
        print(f"  → {discipline}: {anchored_count} anchored, {emergent_count} emergent dimensions")
        (out_dir / f"analysis_{discipline}.json").write_text(
            json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ── Stage 3: Triangulation ────────────────────────────────
    print("\n[Stage 3] Triangulating across disciplines...")
    triangulation = await run_agent(
        agents["triangulate"][0],
        "triangulate",
        {"subject": subject, "analyses": analyses},
        config,
    )
    convergence_count = len(triangulation.get("convergences", []))
    tension_count = len(triangulation.get("tensions", []))
    echo_count = len(triangulation.get("cross_echoes", []))
    print(f"  → {convergence_count} convergences, {echo_count} cross-echoes, {tension_count} tensions")
    (out_dir / "triangulation.json").write_text(
        json.dumps(triangulation, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── Stage 4: Report generation ────────────────────────────
    print("\n[Stage 4] Generating final report...")
    report = await run_agent(
        agents["report"][0],
        "report",
        {"subject": subject, "triangulation": triangulation, "analyses": analyses},
        config,
    )
    report_path = out_dir / "report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"  → Report written ({len(report)} chars)")

    # ── Done ──────────────────────────────────────────────────
    print(f"\n✅ 完成！所有产物已保存至 {out_dir}/")
    print(f"   events.json          ({event_count} events)")
    for a in analyses:
        d = a.get("discipline", "unknown")
        print(f"   analysis_{d}.json")
    print(f"   triangulation.json")
    print(f"   report.md")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <subject_dir>")
        print("Example: python main.py data/elon_musk")
        sys.exit(1)

    asyncio.run(run(sys.argv[1]))

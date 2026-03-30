from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import loader
from runtime import build_analyses_block, discover_skills, resolve_llm_config, run_agent, call_llm


def load_config() -> dict:
    config = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
    llm_path = Path("llm.yaml")
    if llm_path.exists():
        llm = yaml.safe_load(llm_path.read_text(encoding="utf-8")) or {}
        config["keys"] = llm.get("keys", {})
        config["api_bases"] = llm.get("api_bases", {})
        config.setdefault("provider", llm.get("default", {}).get("provider", "anthropic"))
        config.setdefault("model", llm.get("default", {}).get("model", ""))
        config.setdefault("max_concurrency", llm.get("default", {}).get("max_concurrency", 5))
    return config


def is_valid_lens_output(payload: dict, expected_lens: str) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("discipline") != "medicine":
        return False
    if payload.get("lens") != expected_lens:
        return False
    if not isinstance(payload.get("constructs"), list):
        return False
    if "emergent_constructs" in payload and not isinstance(payload.get("emergent_constructs"), list):
        return False
    return True


async def generate_report(subject: str, assembly: dict, analyses: list[dict], config: dict) -> str:
    agent_cfg = yaml.safe_load(Path("agents/discipline/medicine/agent.yaml").read_text(encoding="utf-8"))
    provider, model, api_key, api_base = resolve_llm_config(agent_cfg, config)

    evidence_cards_json = json.dumps(assembly.get("evidence_cards", []), ensure_ascii=False, indent=2)
    analyses_block = build_analyses_block(analyses)

    system = """你是一位医学视角的人物分析报告撰写者。

要求：
- 只基于给定的医学 lens 分析结果和证据卡写作
- 不做临床诊断，不推断未公开病史
- 只讨论身体负荷、恢复能力、功能稳定性、长期健康风险、工作负荷、生活方式与预防倾向
- 尽量使用医学或健康科学相关表述来组织结论，例如：睡眠债、昼夜节律扰动、恢复窗口、全静负荷、疲劳暴露、功能稳定性、长期风险暴露、负荷-恢复失衡、健康可持续性
- 重点写“生理代价、功能负荷、恢复机制、风险暴露”，不要把报告写成纯心理分析
- 重要结论必须引用具体 evidence card ID（ev_XXX）
- 结论要区分：高把握的模式、合理推断、证据不足之处
- 用中文输出 Markdown
"""

    user = f"""分析对象：{subject}

证据卡：
{evidence_cards_json}

医学 lens 分析结果：
{analyses_block}

请写一份医学视角报告，结构如下：

# {subject} — 医学视角画像

## 核心结论
提炼 3-4 条最重要结论，引用证据卡。
每条都尽量写清楚对应的医学维度，例如：
- 睡眠/昼夜节律
- 压力生理与全静负荷
- 职业性疲劳暴露
- 负荷-恢复失衡
- 长期健康可持续性

## 分 lens 分析
按以下 lens 组织：
- sleep_circadian_medicine
- stress_allostatic_load
- occupational_medicine
- lifestyle_medicine
- preventive_risk_management

每个 lens 用 1 段，写清它看到了什么、证据是什么、边界是什么。
每段都尽量带出该 lens 对应的医学语言，而不是只用抽象人格词。

## 交叉收敛
说明这 5 个医学 lens 之间哪些地方形成了交叉支持，哪些只是局部支持。

## 医学边界与证据薄弱处
明确写出这份分析不能说明什么，哪些推断证据不足。
"""

    return await call_llm(
        system=system,
        user=user,
        model=model,
        api_key=api_key,
        provider=provider,
        api_base=api_base,
        max_tokens=12000,
    )


async def main(subject_dir: str) -> int:
    force = "--force" in sys.argv[1:]
    config = load_config()
    data = loader.load(Path(subject_dir))
    subject = data["subject"]
    source_types = {s["type"] for s in data["sources"]}

    subject_slug = subject.lower().replace(" ", "_")
    base_out_dir = Path("output") / subject_slug
    assembly_path = base_out_dir / "assembly.json"
    if not assembly_path.exists():
        raise FileNotFoundError(f"assembly.json not found at {assembly_path}")

    assembly = json.loads(assembly_path.read_text(encoding="utf-8"))

    medicine_dir = Path("agents/discipline/medicine")
    skills = discover_skills(medicine_dir / "skills")
    if not skills:
        raise RuntimeError("No medicine skills found")

    out_dir = base_out_dir / "medicine"
    out_dir.mkdir(parents=True, exist_ok=True)

    analyses: list[dict] = []
    for skill in skills:
        skill_path = out_dir / f"{skill['key']}.json"
        if skill_path.exists() and not force:
            result = json.loads(skill_path.read_text(encoding="utf-8"))
            if is_valid_lens_output(result, skill["key"]):
                analyses.append(result)
                print(f"loaded {skill['key']}.json", flush=True)
                continue
            print(f"invalid cached {skill['key']}.json, regenerating", flush=True)

        result = await run_agent(
            medicine_dir,
            "discipline",
            {
                "subject": subject,
                "assembly": assembly,
                "config": config,
                "source_types": source_types,
                "current_lens": skill,
                "discipline_name": "medicine",
                "discipline_display": "医学 Medicine",
            },
            config,
        )
        if isinstance(result, dict):
            result.setdefault("discipline", "medicine")
            result.setdefault("lens", skill["key"])
        analyses.append(result)
        skill_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"saved {skill['key']}.json", flush=True)

    report = await generate_report(subject, assembly, analyses, config)
    report_path = out_dir / "report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"saved {report_path}", flush=True)
    return 0


if __name__ == "__main__":
    args = [arg for arg in sys.argv[1:] if arg != "--force"]
    target = args[0] if args else "data/elon_musk"
    raise SystemExit(asyncio.run(main(target)))

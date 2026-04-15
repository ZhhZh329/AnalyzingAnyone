"""
runtime.py — Agent execution engine.

Routes by `role`, not by class hierarchy.
Checks for override.py per-function.
"""

import asyncio
import importlib.util
import json
import os
import re
from pathlib import Path
from typing import Any

import httpx
import yaml


# ── Agent discovery ───────────────────────────────────────────

def discover_agents(agents_dir: Path) -> dict[str, list[Path]]:
    """
    Recursively find all agent.yaml files.
    Return a dict grouped by role: {"extract": [Path], "discipline": [...], ...}
    """
    result: dict[str, list[Path]] = {}
    for yaml_path in sorted(agents_dir.rglob("agent.yaml")):
        cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        if not isinstance(cfg, dict):
            print(f"  [runtime] WARNING: invalid agent.yaml (skipped): {yaml_path}")
            continue
        role = cfg.get("role")
        if not role:
            print(f"  [runtime] WARNING: missing role in agent.yaml (skipped): {yaml_path}")
            continue
        result.setdefault(role, []).append(yaml_path.parent)
    return result


# ── Skill discovery ──────────────────────────────────────────

def discover_skills(skills_dir: Path) -> list[dict]:
    """
    Scan a discipline agent's skills/ directory.
    Returns a list of skill dicts: [{"key": str, "content": str, "source": str}]

    Rules:
    - Top-level .md → 1 call
    - Subdirectory + skill.yaml:
      - independent: true  → each .md = 1 independent call
      - independent: false (default) → all .md merged into 1 call
      - no skill.yaml → default independent: false
    """
    if not skills_dir.exists():
        return []
    skills = []
    for item in sorted(skills_dir.iterdir()):
        if item.is_file() and item.suffix == ".md":
            skills.append({
                "key": item.stem,
                "content": item.read_text(encoding="utf-8"),
                "source": str(item),
            })
        elif item.is_dir():
            cfg_file = item / "skill.yaml"
            independent = False
            if cfg_file.exists():
                cfg = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}
                independent = cfg.get("independent", False)

            md_files = sorted(item.glob("*.md"))
            if not md_files:
                continue

            if independent:
                for md in md_files:
                    skills.append({
                        "key": f"{item.name}_{md.stem}",
                        "content": md.read_text(encoding="utf-8"),
                        "source": str(md),
                    })
            else:
                combined = "\n\n---\n\n".join(
                    md.read_text(encoding="utf-8") for md in md_files
                )
                skills.append({
                    "key": item.name,
                    "content": combined,
                    "source": str(item),
                })
    return skills


def build_construct_matrix(all_annotations: list[dict], config: dict) -> str:
    """
    Reorganize all lens annotations into a construct-centric matrix view
    for the synthesizer.

    Output:
      construct: agency_orientation
        pragmatism (philosophy):     strong — "assessment text"
        systems_thinking (cs_eng):   moderate — "assessment text"
    """
    constructs = config.get("shared_constructs", [])
    construct_keys = [c["key"] for c in constructs]

    # Build lookup: construct_key → list of (discipline, lens, assessment, support)
    matrix: dict[str, list[tuple]] = {k: [] for k in construct_keys}
    emergent_all: list[dict] = []

    for ann in all_annotations:
        disc = ann.get("discipline", "unknown")
        lens = ann.get("lens", "unknown")
        for c in ann.get("constructs", []):
            key = c.get("construct_key", "")
            if key in matrix:
                matrix[key].append((
                    disc, lens,
                    c.get("assessment", ""),
                    c.get("local_support", ""),
                    c.get("finding", ""),
                ))
        for e in ann.get("emergent_constructs", []):
            e_copy = dict(e)
            e_copy["originating_lens"] = f"{lens} ({disc})"
            emergent_all.append(e_copy)

    lines = []
    for key in construct_keys:
        q = next((c["question"] for c in constructs if c["key"] == key), "")
        lines.append(f"construct: {key}")
        lines.append(f"  question: {q}")
        for disc, lens, assessment, support, finding in matrix[key]:
            if support == "not_applicable":
                continue
            lines.append(f"  {lens} ({disc}): {support} — {assessment}")
            if finding:
                # indent finding for readability
                lines.append(f"    {finding[:300]}")
        lines.append("")

    if emergent_all:
        lines.append("=== EMERGENT CONSTRUCTS (discovered by individual lenses) ===")
        for e in emergent_all:
            lines.append(f"  [{e.get('originating_lens', '?')}] {e.get('dimension_name', '?')}: {e.get('finding', '')[:200]}")
        lines.append("")

    return "\n".join(lines)


# ── Prompt helpers ────────────────────────────────────────────

def parse_prompt_md(content: str) -> tuple[str, str]:
    """
    Split a prompt.md file on the ---USER--- separator.
    Returns (system_prompt, user_prompt).
    If no separator, the whole file is treated as system prompt.
    """
    if "---USER---" in content:
        parts = content.split("---USER---", 1)
        return parts[0].strip(), parts[1].strip()
    return content.strip(), ""


def build_sources_block(sources: list[dict]) -> str:
    """
    Format sources with metadata header for the extractor.

    [src_001 | biography | 1977] Childhood in Pretoria, bullying, family dynamics
    <content>

    ---

    [src_002 | tweet | 2022-10-28]
    <content>
    """
    parts = []
    for s in sources:
        context = s.get("context", "")
        header = f"[{s['id']} | {s['type']} | {s['date']}]"
        if context:
            header += f" {context}"
        parts.append(f"{header}\n{s['content']}")
    return "\n\n---\n\n".join(parts)


def build_analyses_block(analyses: list[dict]) -> str:
    """
    Concatenate analyses with clear labels.
    Supports both v2 (discipline-level) and v2.1 (lens-level) format.

    === philosophy / pragmatism ===
    { ... }
    """
    parts = []
    for a in analyses:
        discipline = a.get("discipline", "unknown")
        lens = a.get("lens", "")
        label = f"{discipline} / {lens}" if lens else discipline
        parts.append(
            f"=== {label} ===\n"
            + json.dumps(a, ensure_ascii=False, indent=2)
        )
    return "\n\n".join(parts)


def build_shared_constructs(config: dict) -> str:
    """
    Render shared_constructs from config.yaml as a bullet list.

    - agency_orientation: Does this person mainly act as a world-shaper or structure-responder?
    - epistemic_style: How does this person form beliefs and judgments?
    """
    lines = []
    for dim in config.get("shared_constructs", []):
        lines.append(f"- {dim['key']}: {dim['question']}")
    return "\n".join(lines)


def load_source_context(skills_dir: Path, source_types: set) -> str:
    """
    Load source-context skill YAML files for the given source types.
    Returns a formatted string to inject into discipline prompts.
    """
    parts = []
    for stype in sorted(source_types):
        f = skills_dir / "source_context" / f"{stype}.yaml"
        if f.exists():
            skill = yaml.safe_load(f.read_text(encoding="utf-8"))
            parts.append(
                f"### {stype}\n"
                + skill.get("credibility_notes", "").strip() + "\n"
                + skill.get("weight_guidance", "").strip()
            )
    return "\n\n".join(parts)


def fill_placeholders(template: str, **kwargs: Any) -> str:
    """Replace {key} placeholders. Silently skip keys not present in template."""
    for key, value in kwargs.items():
        template = template.replace("{" + key + "}", str(value))
    return template


def default_build_prompt(
    role: str, context: dict, template: str, config: dict
) -> tuple[str, str]:
    """
    Role-aware placeholder filling.
    Returns (system_prompt, user_prompt).
    """
    system_raw, user_raw = parse_prompt_md(template)

    subject = context.get("subject", "")
    cfg = context.get("config", config)

    # ── V1 legacy roles (kept for backward compatibility) ──────
    if role == "extract":
        sources_block = build_sources_block(context["sources"])
        system = fill_placeholders(system_raw, subject=subject, sources_block=sources_block)
        user = fill_placeholders(user_raw, subject=subject, sources_block=sources_block)

    elif role == "triangulate":
        analyses = context["analyses"]
        analyses_block = build_analyses_block(analyses)
        system = fill_placeholders(system_raw, subject=subject, analyses_block=analyses_block)
        user = fill_placeholders(user_raw, subject=subject, analyses_block=analyses_block)

    # ── V2 roles ───────────────────────────────────────────────
    elif role == "assemble":
        sources_block = build_sources_block(context["sources"])
        timeline_limit = context.get("timeline_limit", 40)
        evidence_limit = context.get("evidence_limit", 60)
        system = fill_placeholders(
            system_raw,
            subject=subject,
            sources_block=sources_block,
            timeline_limit=timeline_limit,
            evidence_limit=evidence_limit,
        )
        user = fill_placeholders(
            user_raw,
            subject=subject,
            sources_block=sources_block,
            timeline_limit=timeline_limit,
            evidence_limit=evidence_limit,
        )

    elif role == "discipline":
        assembly = context["assembly"]
        events_json = json.dumps(assembly.get("timeline", []), ensure_ascii=False, indent=2)
        evidence_cards_json = json.dumps(assembly.get("evidence_cards", []), ensure_ascii=False, indent=2)
        shared_constructs = build_shared_constructs(cfg)
        source_types = context.get("source_types", set())
        skills_dir = Path("skills")
        source_context = load_source_context(skills_dir, source_types)

        # V2.1: skill-based sub-lens injection
        current_lens = context.get("current_lens", {})
        skill_content = current_lens.get("content", "") if isinstance(current_lens, dict) else ""
        lens_key = current_lens.get("key", "") if isinstance(current_lens, dict) else ""
        discipline_name = context.get("discipline_name", "")
        discipline_display = context.get("discipline_display", discipline_name)

        common_kwargs = dict(
            subject=subject,
            events_json=events_json,
            evidence_cards_json=evidence_cards_json,
            shared_constructs=shared_constructs,
            source_context=source_context,
            skill_content=skill_content,
            lens_key=lens_key,
            discipline_name=discipline_name,
            discipline_display=discipline_display,
        )
        system = fill_placeholders(system_raw, **common_kwargs)
        user = fill_placeholders(user_raw, **common_kwargs)

    elif role == "critique":
        assembly = context["assembly"]
        analyses = context["analyses"]
        evidence_cards_json = json.dumps(assembly.get("evidence_cards", []), ensure_ascii=False, indent=2)
        analyses_block = build_analyses_block(analyses)
        system = fill_placeholders(
            system_raw,
            subject=subject,
            evidence_cards_json=evidence_cards_json,
            analyses_block=analyses_block,
        )
        user = fill_placeholders(
            user_raw,
            subject=subject,
            evidence_cards_json=evidence_cards_json,
            analyses_block=analyses_block,
        )

    elif role == "synthesize":
        analyses = context["analyses"]
        critic_output = context["critic_output"]
        analyses_block = build_analyses_block(analyses)
        critic_output_json = json.dumps(critic_output, ensure_ascii=False, indent=2)
        # V2.1: construct matrix for flat cross-lens synthesis
        construct_matrix = context.get("construct_matrix", "")
        system = fill_placeholders(
            system_raw,
            subject=subject,
            analyses_block=analyses_block,
            critic_output_json=critic_output_json,
            construct_matrix=construct_matrix,
        )
        user = fill_placeholders(
            user_raw,
            subject=subject,
            analyses_block=analyses_block,
            critic_output_json=critic_output_json,
            construct_matrix=construct_matrix,
        )

    elif role == "report":
        synthesis = context.get("synthesis") or context.get("triangulation", {})
        analyses = context["analyses"]
        critic_output = context.get("critic_output", {})
        synthesis_json = json.dumps(synthesis, ensure_ascii=False, indent=2)
        analyses_block = build_analyses_block(analyses)
        critic_output_json = json.dumps(critic_output, ensure_ascii=False, indent=2)
        system = fill_placeholders(
            system_raw,
            subject=subject,
            synthesis_json=synthesis_json,
            analyses_block=analyses_block,
            critic_output_json=critic_output_json,
        )
        user = fill_placeholders(
            user_raw,
            subject=subject,
            synthesis_json=synthesis_json,
            analyses_block=analyses_block,
            critic_output_json=critic_output_json,
        )

    else:
        system = system_raw
        user = user_raw

    return system, user


# ── JSON parsing ──────────────────────────────────────────────

def extract_json_from_response(text: str) -> dict:
    """
    Parse JSON from LLM response, handling markdown code blocks.
    Raises json.JSONDecodeError on failure.
    """
    text = text.strip()
    # Strip complete <think>...</think> reasoning blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    # Handle incomplete <think> blocks (model cut off before </think>):
    # everything from <think> to end-of-string is pure reasoning, no JSON follows
    if "<think>" in text:
        before = text[:text.index("<think>")].strip()
        after_match = re.search(r"</think>(.*)", text, re.DOTALL)
        text = (after_match.group(1).strip() if after_match else before)
    # Strip markdown code fences if present
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    if not text:
        raise json.JSONDecodeError("Empty response after stripping think blocks", "", 0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        candidate = extract_balanced_json(text)
        if candidate is None:
            raise
        return json.loads(candidate)


def extract_balanced_json(text: str) -> str | None:
    """
    Find the first balanced top-level JSON object/array inside a noisy response.
    This is useful when the model adds a short preamble or epilogue around JSON.
    """
    for start, char in enumerate(text):
        if char not in "{[":
            continue

        stack = ["}" if char == "{" else "]"]
        in_string = False
        escaped = False

        for idx in range(start + 1, len(text)):
            current = text[idx]

            if in_string:
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == "\"":
                    in_string = False
                continue

            if current == "\"":
                in_string = True
                continue

            if current == "{":
                stack.append("}")
            elif current == "[":
                stack.append("]")
            elif current in "}]":
                if not stack or current != stack[-1]:
                    break
                stack.pop()
                if not stack:
                    return text[start:idx + 1]

    return None


# ── Provider defaults ─────────────────────────────────────────

# format: "anthropic" uses native Messages API; "openai" uses /chat/completions
PROVIDER_DEFAULTS: dict[str, dict] = {
    "anthropic": {
        "api_base":    "https://api.anthropic.com",
        "api_key_env": "ANTHROPIC_API_KEY",
        "format":      "anthropic",
    },
    "openai": {
        "api_base":    "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "format":      "openai",
        "stream":      True,
        "read_timeout": 120.0,
    },
    "google": {
        # Gemini OpenAI-compatible endpoint
        "api_base":    "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_key_env": "GOOGLE_API_KEY",
        "format":      "openai",
        "stream":      True,
        "read_timeout": 120.0,
    },
    "glm": {
        "api_base":    "https://open.bigmodel.cn/api/paas/v4",
        "api_key_env": "GLM_API_KEY",
        "format":      "openai",
        "stream":      True,
        "read_timeout": 120.0,
    },
    "minimax": {
        "api_base":    "https://api.minimaxi.com/anthropic",
        "api_key_env": "MINIMAX_API_KEY",
        "format":      "anthropic",
    },
    "kimi": {
        "api_base":    "https://api.moonshot.cn/v1",
        "api_key_env": "KIMI_API_KEY",
        "format":      "openai",
        "stream":      True,
        "read_timeout": 120.0,
    },
    "qwen": {
        "api_base":    "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key_env": "QWEN_API_KEY",
        "format":      "openai",
        "stream":      True,
        "read_timeout": 120.0,
    },
    "grok": {
        "api_base":    "https://api.x.ai/v1",
        "api_key_env": "GROK_API_KEY",
        "format":      "openai",
        "stream":      True,
        "read_timeout": 120.0,
    },
}


def get_api_key_env(provider: str) -> str:
    """Return the env var name for a given provider's API key."""
    return PROVIDER_DEFAULTS.get(provider, {}).get("api_key_env", "ANTHROPIC_API_KEY")


def resolve_llm_config(agent_cfg: dict, config: dict) -> tuple[str, str, str, str | None]:
    """
    Resolve (provider, model, api_key, api_base) with priority:
      1. agent.yaml  — per-agent override
      2. llm.yaml default — global default (merged into config by main.py)
      3. environment variable — fallback for key lookup

    Raises EnvironmentError if no API key can be found.
    """
    provider = agent_cfg.get("provider") or config.get("provider", "anthropic")
    model    = agent_cfg.get("model")    or config.get("model", "")

    # API key: llm.yaml keys[provider] → env var
    key_from_yaml = config.get("keys", {}).get(provider, "")
    if key_from_yaml:
        api_key = key_from_yaml
    else:
        env_var = PROVIDER_DEFAULTS.get(provider, {}).get("api_key_env", "")
        api_key = os.environ.get(env_var, "")

    if not api_key:
        env_var = PROVIDER_DEFAULTS.get(provider, {}).get("api_key_env", f"{provider.upper()}_API_KEY")
        raise EnvironmentError(
            f"No API key for provider '{provider}'. "
            f"Set it in llm.yaml under keys.{provider} "
            f"or via environment variable {env_var}."
        )

    # api_base: llm.yaml api_bases[provider] → PROVIDER_DEFAULTS
    api_base = config.get("api_bases", {}).get(provider) or None

    return provider, model, api_key, api_base


# ── LLM call ─────────────────────────────────────────────────

async def call_llm(
    system: str,
    user: str,
    model: str,
    api_key: str,
    provider: str = "anthropic",
    api_base: str | None = None,
    max_tokens: int = 8192,
    _retries: int = 4,
) -> str:
    """
    Dispatch to the correct LLM API based on provider.
    - anthropic → native Messages API
    - everything else → OpenAI-compatible /chat/completions

    Retries up to _retries times on 429 with exponential backoff (2, 4, 8, 16 s).
    """
    defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["openai"])
    base = (api_base or defaults["api_base"]).rstrip("/")
    fmt = defaults["format"]
    stream = defaults.get("stream", True)
    read_timeout = defaults.get("read_timeout", 120.0)

    for attempt in range(_retries):
        try:
            if fmt == "anthropic":
                return await _call_anthropic(system, user, model, api_key, base, max_tokens)
            else:
                return await _call_openai_compat(
                    system,
                    user,
                    model,
                    api_key,
                    base,
                    max_tokens,
                    stream=stream,
                    read_timeout=read_timeout,
                )
        except httpx.HTTPStatusError as e:
            try:
                # Streaming responses may not have been read yet.
                await e.response.aread()
                body = e.response.text[:500]
            except Exception:
                body = "<response body unavailable>"
            status = e.response.status_code
            if (status == 429 or 500 <= status < 600) and attempt < _retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"  [runtime] {status} — {body}")
                print(f"  [runtime] waiting {wait}s (attempt {attempt + 1}/{_retries})")
                await asyncio.sleep(wait)
            else:
                raise httpx.HTTPStatusError(
                    f"{status} from {provider}: {body}",
                    request=e.request,
                    response=e.response,
                ) from e
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError, httpx.ConnectError) as e:
            if attempt < _retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"  [runtime] {type(e).__name__} (attempt {attempt + 1}/{_retries}), retrying in {wait}s…")
                await asyncio.sleep(wait)
            else:
                raise


async def _call_anthropic(
    system: str, user: str, model: str, api_key: str, api_base: str, max_tokens: int
) -> str:
    url = f"{api_base}/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    _timeout = httpx.Timeout(connect=30.0, read=600.0, write=60.0, pool=10.0)
    async with httpx.AsyncClient(timeout=_timeout) as client:
        response = await client.post(url, headers=headers, json=body)
        response.raise_for_status()
        payload = response.json()
        content = payload.get("content", [])
        if isinstance(content, list):
            text_parts = [
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            if text_parts:
                return "".join(text_parts)
        return payload["content"][0]["text"]


async def _call_openai_compat(
    system: str,
    user: str,
    model: str,
    api_key: str,
    api_base: str,
    max_tokens: int,
    stream: bool = True,
    read_timeout: float = 120.0,
) -> str:
    url = f"{api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "content-type": "application/json",
    }
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    _timeout = httpx.Timeout(connect=30.0, read=read_timeout, write=60.0, pool=10.0)

    if not stream:
        async with httpx.AsyncClient(timeout=_timeout) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()
            message = payload["choices"][0]["message"]
            content = message.get("content") or ""
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for part in content:
                    if isinstance(part, str):
                        parts.append(part)
                    elif isinstance(part, dict) and part.get("type") == "text":
                        parts.append(part.get("text", ""))
                return "".join(parts)
            return str(content)

    body["stream"] = True
    # Per-chunk read timeout is appropriate only for providers that actually
    # emit SSE chunks during generation.
    chunks: list[str] = []
    async with httpx.AsyncClient(timeout=_timeout) as client:
        async with client.stream("POST", url, headers=headers, json=body) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0]["delta"]
                    content = delta.get("content") or ""
                    if content:
                        chunks.append(content)
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
    return "".join(chunks)


# ── Override loading ──────────────────────────────────────────

def load_override(agent_dir: Path):
    """
    If override.py exists in agent_dir, import and return the module.
    Returns None if no override.py present.
    """
    override_path = agent_dir / "override.py"
    if not override_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("override", override_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── Main agent runner ─────────────────────────────────────────

async def run_agent(
    agent_dir: Path,
    role: str,
    context: dict,
    config: dict,
) -> dict | str:
    """
    Execute a single agent.

    1. Load agent.yaml + prompt.md
    2. Resolve provider/model/api_key (agent override > llm.yaml default > env var)
    3. Check for override.py (per-function)
    4. Build prompt (role-aware placeholder filling)
    5. Call LLM
    6. Parse response (JSON for most roles, raw string for 'report')
    7. Retry once on JSON parse failure
    8. Return dict or str
    """
    # Load agent config
    agent_cfg = yaml.safe_load((agent_dir / "agent.yaml").read_text(encoding="utf-8"))
    prompt_file = agent_cfg.get("prompt", "prompt.md")
    template = (agent_dir / prompt_file).read_text(encoding="utf-8")

    # Resolve LLM settings with priority: agent.yaml > llm.yaml > env var
    provider, model, api_key, api_base = resolve_llm_config(agent_cfg, config)

    # Load optional override module
    override = load_override(agent_dir)

    # ── pre_process ──
    if override and hasattr(override, "pre_process"):
        context = override.pre_process(context)

    # ── build_prompt ──
    if override and hasattr(override, "build_prompt"):
        system, user = override.build_prompt(role, context, template, config)
    else:
        system, user = default_build_prompt(role, context, template, config)

    # If there's no user prompt (single-section prompt.md), use the whole thing as user
    if not user:
        system, user = "", system

    # ── call LLM ──
    max_tokens = agent_cfg.get("max_tokens", 8192)
    raw = await call_llm(system, user, model, api_key, provider=provider, api_base=api_base,
                         max_tokens=max_tokens)

    # ── parse_response ──
    if override and hasattr(override, "parse_response"):
        result = override.parse_response(raw, role)
        # Support both sync and async override.parse_response
        if asyncio.iscoroutine(result):
            result = await result
    else:
        result = await default_parse_response(raw, role, system, user, model, api_key,
                                              provider=provider, api_base=api_base,
                                              max_tokens=max_tokens)

    # ── post_process ──
    if override and hasattr(override, "post_process"):
        result = override.post_process(result)

    return result


async def default_parse_response(
    raw: str,
    role: str,
    system: str,
    user: str,
    model: str,
    api_key: str,
    provider: str = "anthropic",
    api_base: str | None = None,
    max_tokens: int = 8192,
) -> dict | str:
    """
    'report' role → return raw Markdown string.
    All other roles → parse JSON, retry once on failure.
    """
    if role == "report":
        return raw

    try:
        return extract_json_from_response(raw)
    except (json.JSONDecodeError, ValueError):
        print(f"  [runtime] JSON parse failed for role={role}, retrying once...")
        raw2 = await call_llm(system, user, model, api_key, provider=provider, api_base=api_base,
                              max_tokens=max_tokens)
        try:
            return extract_json_from_response(raw2)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"  [runtime] JSON parse failed twice for role={role}, attempting repair pass...")
            repaired = await attempt_json_repair_with_llm(
                raw2,
                role,
                model,
                api_key,
                provider=provider,
                api_base=api_base,
                max_tokens=min(max_tokens, 4096),
            )
            try:
                return extract_json_from_response(repaired)
            except (json.JSONDecodeError, ValueError) as repair_error:
                raise ValueError(
                    f"JSON parse failed after retry+repair for role={role}.\n"
                    f"Last response:\n{raw2[:500]}"
                ) from repair_error


async def attempt_json_repair_with_llm(
    broken_json_text: str,
    role: str,
    model: str,
    api_key: str,
    provider: str = "anthropic",
    api_base: str | None = None,
    max_tokens: int = 4096,
) -> str:
    """
    Ask the model to repair malformed JSON text and return strict JSON only.
    This is a best-effort fallback for providers/models that occasionally emit
    invalid JSON (e.g. unescaped quotes or truncated braces).
    """
    repair_system = (
        "You repair malformed JSON. "
        "Return valid JSON only, with no markdown, no commentary, no extra text. "
        "Preserve original fields and values whenever possible. "
        "If the input is truncated, minimally complete the structure."
    )
    repair_user = (
        f"role={role}\n"
        "Fix this malformed JSON and output strict valid JSON only:\n\n"
        "```json\n"
        f"{broken_json_text[:20000]}\n"
        "```"
    )
    return await call_llm(
        repair_system,
        repair_user,
        model,
        api_key,
        provider=provider,
        api_base=api_base,
        max_tokens=max_tokens,
    )

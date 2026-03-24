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
        role = cfg["role"]
        result.setdefault(role, []).append(yaml_path.parent)
    return result


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
    Concatenate discipline analyses with clear labels.

    === philosophy ===
    { ... }

    === psychology ===
    { ... }
    """
    parts = []
    for a in analyses:
        discipline = a.get("discipline", "unknown")
        parts.append(
            f"=== {discipline} ===\n"
            + json.dumps(a, ensure_ascii=False, indent=2)
        )
    return "\n\n".join(parts)


def build_anchored_dimensions(config: dict) -> str:
    """
    Render anchored_dimensions from config.yaml as a bullet list.

    - core_values: What matters most to this person?
    - decision_logic: How do they reason through dilemmas?
    """
    lines = []
    for dim in config.get("anchored_dimensions", []):
        lines.append(f"- {dim['key']}: {dim['question']}")
    return "\n".join(lines)


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

    if role == "extract":
        sources_block = build_sources_block(context["sources"])
        system = fill_placeholders(system_raw, subject=subject, sources_block=sources_block)
        user = fill_placeholders(user_raw, subject=subject, sources_block=sources_block)

    elif role == "discipline":
        events = context["events"]
        events_json = json.dumps(events, ensure_ascii=False, indent=2)
        anchored_dimensions = build_anchored_dimensions(cfg)
        system = fill_placeholders(
            system_raw,
            subject=subject,
            events_json=events_json,
            anchored_dimensions=anchored_dimensions,
        )
        user = fill_placeholders(
            user_raw,
            subject=subject,
            events_json=events_json,
            anchored_dimensions=anchored_dimensions,
        )

    elif role == "triangulate":
        analyses = context["analyses"]
        analyses_block = build_analyses_block(analyses)
        system = fill_placeholders(system_raw, subject=subject, analyses_block=analyses_block)
        user = fill_placeholders(user_raw, subject=subject, analyses_block=analyses_block)

    elif role == "report":
        triangulation = context["triangulation"]
        analyses = context["analyses"]
        triangulation_json = json.dumps(triangulation, ensure_ascii=False, indent=2)
        analyses_block = build_analyses_block(analyses)
        system = fill_placeholders(
            system_raw,
            subject=subject,
            triangulation_json=triangulation_json,
            analyses_block=analyses_block,
        )
        user = fill_placeholders(
            user_raw,
            subject=subject,
            triangulation_json=triangulation_json,
            analyses_block=analyses_block,
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
    # Strip markdown code fences if present
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    return json.loads(text)


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
    },
    "google": {
        # Gemini OpenAI-compatible endpoint
        "api_base":    "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_key_env": "GOOGLE_API_KEY",
        "format":      "openai",
    },
    "glm": {
        "api_base":    "https://open.bigmodel.cn/api/paas/v4",
        "api_key_env": "GLM_API_KEY",
        "format":      "openai",
    },
    "minimax": {
        "api_base":    "https://api.minimax.chat/v1",
        "api_key_env": "MINIMAX_API_KEY",
        "format":      "openai",
    },
    "kimi": {
        "api_base":    "https://api.moonshot.cn/v1",
        "api_key_env": "KIMI_API_KEY",
        "format":      "openai",
    },
    "qwen": {
        "api_base":    "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key_env": "QWEN_API_KEY",
        "format":      "openai",
    },
    "grok": {
        "api_base":    "https://api.x.ai/v1",
        "api_key_env": "GROK_API_KEY",
        "format":      "openai",
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

    for attempt in range(_retries):
        try:
            if fmt == "anthropic":
                return await _call_anthropic(system, user, model, api_key, base, max_tokens)
            else:
                return await _call_openai_compat(system, user, model, api_key, base, max_tokens)
        except httpx.HTTPStatusError as e:
            body = e.response.text[:500]
            if e.response.status_code == 429 and attempt < _retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"  [runtime] 429 — {body}")
                print(f"  [runtime] waiting {wait}s (attempt {attempt + 1}/{_retries})")
                await asyncio.sleep(wait)
            else:
                raise httpx.HTTPStatusError(
                    f"{e.response.status_code} from {provider}: {body}",
                    request=e.request,
                    response=e.response,
                ) from e


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
    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(url, headers=headers, json=body)
        response.raise_for_status()
        return response.json()["content"][0]["text"]


async def _call_openai_compat(
    system: str, user: str, model: str, api_key: str, api_base: str, max_tokens: int
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
    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(url, headers=headers, json=body)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


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
    raw = await call_llm(system, user, model, api_key, provider=provider, api_base=api_base)

    # ── parse_response ──
    if override and hasattr(override, "parse_response"):
        result = override.parse_response(raw, role)
        # Support both sync and async override.parse_response
        if asyncio.iscoroutine(result):
            result = await result
    else:
        result = await default_parse_response(raw, role, system, user, model, api_key,
                                              provider=provider, api_base=api_base)

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
        raw2 = await call_llm(system, user, model, api_key, provider=provider, api_base=api_base)
        try:
            return extract_json_from_response(raw2)
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(
                f"JSON parse failed twice for role={role}.\n"
                f"Last response:\n{raw2[:500]}"
            ) from e

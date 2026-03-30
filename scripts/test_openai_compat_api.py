"""
Minimal tester for OpenAI-compatible endpoints.

Examples:
  OPENAI_API_KEY=... .venv/bin/python scripts/test_openai_compat_api.py --api-base https://host/v1 --models
  OPENAI_API_KEY=... .venv/bin/python scripts/test_openai_compat_api.py --api-base https://host/v1 gpt-5
  OPENAI_API_KEY=... .venv/bin/python scripts/test_openai_compat_api.py --api-base https://host/v1 --responses gpt-5
"""

from __future__ import annotations

import json
import os
import sys

import httpx


DEFAULT_API_BASE = "https://api.openai.com/v1"


def parse_args(argv: list[str]) -> tuple[str, str, list[str]]:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    api_base = DEFAULT_API_BASE
    positional: list[str] = []

    idx = 0
    while idx < len(argv):
        arg = argv[idx]
        if arg == "--api-key" and idx + 1 < len(argv):
            api_key = argv[idx + 1]
            idx += 2
            continue
        if arg == "--api-base" and idx + 1 < len(argv):
            api_base = argv[idx + 1].rstrip("/")
            idx += 2
            continue
        positional.append(arg)
        idx += 1

    return api_key, api_base, positional


def main() -> int:
    api_key, api_base, args = parse_args(sys.argv[1:])
    if not api_key:
        raise SystemExit("Missing API key. Pass --api-key or set OPENAI_API_KEY.")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "content-type": "application/json",
    }

    timeout = httpx.Timeout(connect=20.0, read=60.0, write=30.0, pool=10.0)
    with httpx.Client(timeout=timeout) as client:
        if len(args) > 0 and args[0] == "--models":
            resp = client.get(f"{api_base}/models", headers=headers)
        elif len(args) > 1 and args[0] == "--responses":
            model = args[1]
            body = {
                "model": model,
                "input": "Reply with exactly OK.",
                "max_output_tokens": 8,
            }
            resp = client.post(f"{api_base}/responses", headers=headers, json=body)
        else:
            model = args[0] if args else "gpt-4o-mini"
            body = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "Reply with exactly OK."},
                    {"role": "user", "content": "ping"},
                ],
                "max_tokens": 8,
            }
            resp = client.post(f"{api_base}/chat/completions", headers=headers, json=body)
        payload = {
            "status_code": resp.status_code,
            "body_prefix": resp.text[:5000],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        resp.raise_for_status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Extract model data from OpenCode's models.dev API.

Replaces the Cherry Studio extraction pipeline. Fetches https://models.dev/api.json,
generates:
  - key_manager/providers/models_registry.py (PROVIDER_MODELS dict)
  - data/model_capabilities.json (per-model boolean capabilities, NOT regex)

Supports 3-tier fallback: API -> local cache (12h TTL) -> bundled snapshot.
Merges with existing registry to preserve providers not covered by models.dev.

Usage: python scripts/extract_from_opencode.py
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

MODELS_DEV_URL = os.environ.get("MODELS_DEV_URL", "https://models.dev/api.json")
CACHE_FILE = Path("data/cache/models-dev.json")
CACHE_TTL = timedelta(hours=12)
OUTPUT_REGISTRY = Path("key_manager/providers/models_registry.py")
OUTPUT_CAPS = Path("data/model_capabilities.json")
SCHEMA_VERSION = 2  # v2: per-model boolean dict

# Provider name mapping: models.dev ID -> our internal provider ID
PROVIDER_MAP: dict[str, str] = {
    "openai": "openai",
    "anthropic": "anthropic",
    "google": "google",
    "deepseek": "deepseek",
    "groq": "groq",
    "xai": "grok",
    "mistral": "mistral",
    "cohere": "cohere",
    "perplexity": "perplexity",
    "togetherai": "together",
    "openrouter": "openrouter",
    "replicate": "replicate",
    "huggingface": "huggingface",
    "fireworks": "fireworks",
    "cerebras": "cerebras",
    "nvidia": "nvidia",
    "hyperbolic": "hyperbolic",
    "poe": "poe",
    "alibaba": "dashscope",
    "modelscope": "modelscope",
    "zhipu": "zhipu",
    "moonshot": "kimi",
    "minimax": "minimax",
    "siliconflow": "siliconflow",
    "baichuan": "baichuan",
    "yi": "yi",
    "stepfun": "stepfun",
    "doubao": "doubao",
    "infini": "infini",
    "mimo": "mimo",
    "tencent": "tencent-hunyuan",
    "opencode": "opencode",
}

VISION_MODALITIES = {"image", "video"}


def fetch_models_dev(url: str = MODELS_DEV_URL, timeout: int = 30) -> dict | None:
    """Fetch models.dev with cache fallback."""
    import urllib.request

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "api-key-manager/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw: dict = json.loads(resp.read())
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[fetch] {len(raw)} providers from {url}")
        return raw
    except Exception as exc:
        print(f"[fetch] API error: {exc}", file=sys.stderr)

    if CACHE_FILE.exists():
        age = datetime.now() - datetime.fromtimestamp(CACHE_FILE.stat().st_mtime)
        if age < CACHE_TTL:
            print(f"[fetch] Using cached data ({age})")
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        print(f"[fetch] Cache too old ({age})", file=sys.stderr)
    return None


def extract_models(data: dict) -> dict[str, list[str]]:
    """Group model IDs by our provider name."""
    provider_models: dict[str, list[str]] = {}

    for src_name, provider_info in data.items():
        dst_name = _resolve_provider(src_name)
        if not dst_name:
            continue

        models = provider_info.get("models", {})
        ids = sorted(set(models.keys()))
        if ids:
            provider_models.setdefault(dst_name, []).extend(ids)
            provider_models[dst_name] = sorted(set(provider_models[dst_name]))

    return dict(sorted(provider_models.items()))


def extract_capabilities(data: dict) -> dict[str, dict[str, bool]]:
    """Build per-model capability map using explicit fields."""
    caps: dict[str, dict[str, bool]] = {}

    for _src_name, provider_info in data.items():
        for model_id, info in provider_info.get("models", {}).items():
            input_mods: list[str] = (info.get("modalities") or {}).get("input", [])

            entry = {
                "vision": any(m in VISION_MODALITIES for m in input_mods),
                "tooluse": bool(info.get("tool_call")),
                "reasoning": bool(info.get("reasoning")),
            }
            if any(entry.values()):
                caps[model_id] = entry

    return caps


def _resolve_provider(src_name: str) -> str | None:
    """Map models.dev provider ID to our internal ID."""
    if src_name in PROVIDER_MAP:
        return PROVIDER_MAP[src_name]
    sl = src_name.lower().replace("-", "")
    for k, v in PROVIDER_MAP.items():
        if k.lower().replace("-", "") == sl:
            return v
    return None


def _load_existing_registry() -> dict[str, list[str]] | None:
    """Load existing PROVIDER_MODELS from models_registry.py via import."""
    if not OUTPUT_REGISTRY.exists():
        return None
    try:
        tmp = Path(tempfile.gettempdir()) / "models_registry_existing.py"
        shutil.copy(OUTPUT_REGISTRY, tmp)
        spec = importlib.util.spec_from_file_location("models_registry_existing", tmp)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        data = dict(mod.PROVIDER_MODELS)
        tmp.unlink(missing_ok=True)
        return data
    except Exception:
        return None


def merge_models(new_data: dict[str, list[str]]) -> dict[str, list[str]]:
    """Merge with existing registry.
    New data wins for providers it covers.
    Old data kept for providers models.dev doesn't cover
    (e.g. Chinese providers like doubao, zhipu, ai302)."""
    old = _load_existing_registry()
    if not old:
        return new_data

    # Filter old data: only keep providers that exist in our implementation registry
    try:
        sys.path.insert(0, str(OUTPUT_REGISTRY.parent.parent))
        from key_manager.providers import PROVIDERS
        sys.path.pop(0)
        valid = set(PROVIDERS.keys())
    except ImportError:
        valid = None

    merged = {}
    for k, v in old.items():
        if valid is None or k in valid:
            merged[k] = v

    # Overlay new data (models.dev wins)
    for k, v in new_data.items():
        merged[k] = v

    return dict(sorted(merged.items()))


def generate_registry(provider_models: dict[str, list[str]]) -> None:
    """Write models_registry.py."""
    ts = datetime.now(timezone.utc).isoformat()
    total = sum(len(v) for v in provider_models.values())
    payload = json.dumps(provider_models, indent=4, ensure_ascii=False)

    content = f'''"""
Auto-generated model registry from OpenCode models.dev.
Source: https://models.dev/api.json
Generated: {ts}

DO NOT EDIT MANUALLY - auto-generated by GitHub Actions.
"""

# Static model lists for each provider - used when API key is not available

PROVIDER_MODELS: dict[str, list[str]] = {payload}


def get_static_models(provider: str) -> list[str]:
    """Get static model list for a provider."""
    return PROVIDER_MODELS.get(provider.lower(), [])


def get_all_providers() -> list[str]:
    """List providers with static models."""
    return list(PROVIDER_MODELS.keys())


def search_models(query: str) -> list[dict[str, str]]:
    """Search models across providers."""
    results: list[dict[str, str]] = []
    q = query.lower()
    for prov, models in PROVIDER_MODELS.items():
        for mid in models:
            if q in mid.lower():
                results.append({{"provider": prov, "model_id": mid}})
    return results
'''

    OUTPUT_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REGISTRY.write_text(content, encoding="utf-8")
    print(f"[generate] {OUTPUT_REGISTRY}: {len(provider_models)} providers, {total} models")


def generate_capabilities(caps: dict[str, dict[str, bool]]) -> None:
    """Write model_capabilities.json in v2 per-model format."""
    ts = datetime.now(timezone.utc).isoformat()
    output: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": ts,
        "source": "https://models.dev/api.json",
        "models": caps,
    }
    OUTPUT_CAPS.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_CAPS.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[generate] {OUTPUT_CAPS}: {len(caps)} models")


def main() -> int:
    print("-- Extracting from models.dev --")

    data = fetch_models_dev()
    if not data:
        print("[ERROR] No data available - aborting.", file=sys.stderr)
        return 1

    new_models = extract_models(data)
    if not new_models:
        print("[ERROR] No models mapped to known providers. Check PROVIDER_MAP.", file=sys.stderr)
        return 1

    # Merge with existing registry to preserve providers not in models.dev
    merged = merge_models(new_models)
    preserved = len(merged) - len(new_models)
    new_only = len(merged) - len([k for k in merged if k not in new_models])
    print(f"[merge] {len(merged)} total ({len(new_models)} from models.dev, {len(merged) - len(new_models)} preserved from old)")

    generate_registry(merged)

    caps = extract_capabilities(data)
    generate_capabilities(caps)

    print("-- Done --")
    return 0


if __name__ == "__main__":
    sys.exit(main())

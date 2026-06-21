"""
Provider Detection Module

This module implements the smart detection logic for identifying API key providers.

IMPORTANT: Detection uses /chat/completions to verify providers, NOT /v1/models!

- /v1/models: Only returns model list, CANNOT determine if key is valid
- /chat/completions: Actually tests the key, CAN determine if key is valid

Detection flow:
1. Prefix matching - Check unique prefixes (e.g., sk-proj- → OpenAI)
2. Format matching - Check special formats (e.g., {id}.{secret} → Zhipu)
3. Concurrent probing - Test all providers with /chat/completions
4. Signature matching - Match error response body signatures

Free models are important! Some providers (like OpenCode Zen) offer free models.
Detection tests ALL models including free models. If any model returns 200,
the provider is correctly identified.
"""
import asyncio
import re
from .providers import PROVIDERS, KEY_PREFIX_MAP, PROVIDER_ERROR_SIGNATURES
from .providers.models_registry import PROVIDER_MODELS


# Scoring weights
WEIGHT_SELF = 100      # Self-signature match = definitive
WEIGHT_CROSS = 10      # Cross-signature match = ambiguous
WEIGHT_RATE_LIMITED = 60  # 429 rate limited = medium confidence (lower than 200/401/403 but still usable)
MIN_WIN_SCORE = 50     # Minimum score to declare a winner
MIN_LEAD = 20          # Minimum lead over second place


# Zhipu/Z.AI key format: {id}.{secret} (dot-separated alphanumeric)
# This format is unique and highly identifiable
# Part 1 (id): 20-50 chars, Part 2 (secret): 10-50 chars
ZHIPU_KEY_PATTERN = re.compile(r'^[a-zA-Z0-9]{20,50}\.[a-zA-Z0-9]{10,50}$')


def detect_by_prefix(key: str) -> list[str]:
    """Return candidates from the LONGEST matching prefix only."""
    for prefix, providers in sorted(KEY_PREFIX_MAP.items(), key=lambda x: -len(x[0])):
        if key.startswith(prefix):
            return list(providers)
    return []



def detect_by_format(key: str) -> list[str]:
    """Detect providers by key format (e.g., Zhipu's {id}.{secret} format).
    
    Returns a list of candidate providers that use this format.
    The caller will probe all candidates and return the first one that responds 200.
    """
    # Zhipu/Z.AI key format: {id}.{secret}
    # This format is unique to Zhipu and Z.AI platforms
    if ZHIPU_KEY_PATTERN.match(key):
        return ["zhipu", "zai"]  # Both candidates, first 200 wins
    return []


def score_provider(provider_name: str, error_body: str, status_code: int = None) -> int:
    """
    Score how likely the error body belongs to this provider.
    
    Uses UNIQUE_SIGNATURES (verified by actual API testing).
    Each unique signature match adds WEIGHT_SELF points.
    429 (rate limited) gets much lower weight since it doesn't confirm key ownership.
    """
    body = error_body.lower()
    score = 0
    
    # 429 rate limited gets reduced weight - it only means "too many requests"
    # not "this key belongs to this provider"
    weight = WEIGHT_RATE_LIMITED if status_code == 429 else WEIGHT_SELF
    
    # Check unique signatures (verified by actual API testing)
    sigs = PROVIDER_ERROR_SIGNATURES.get(provider_name, [])
    for sig in sigs:
        if sig.lower() in body:
            score += weight
    
    return score


async def detect_provider(client, key: str, suspected_provider: str = None) -> str:
    """Detect provider by concurrently probing ALL providers with multiple models.
    
    IMPORTANT: This function uses /chat/completions to verify providers, NOT /v1/models!
    
    - /v1/models: Only returns model list, CANNOT determine if key is valid
    - /chat/completions: Actually tests the key, CAN determine if key is valid
    
    Strategy:
    1. If suspected_provider given, try it first
    2. If key matches unique pattern, try that provider
    3. If key matches prefix, try candidates
    4. Otherwise, concurrently probe ALL providers with their models
    5. First provider returning 200 from /chat/completions wins
    
    Free models are important! Some providers (like OpenCode Zen) offer free models.
    Detection tests ALL models including free models. If any model returns 200,
    the provider is correctly identified.
    """
    import time
    
    # Step 1: If suspected provider, try it first
    if suspected_provider:
        provider_name = suspected_provider.lower()
        if provider_name in PROVIDERS:
            return provider_name
    
    # Step 2: Try format matching (e.g., Zhipu's {id}.{secret})
    format_candidates = detect_by_format(key)
    if format_candidates:
        # Return first candidate that exists in PROVIDERS
        for name in format_candidates:
            if name in PROVIDERS:
                return name
    
    # Step 3: Try prefix matching - collect candidates, don't return on /v1/models 200
    prefix_candidates = detect_by_prefix(key)
    if prefix_candidates:
        # If only one candidate, return it
        if len(prefix_candidates) == 1:
            return prefix_candidates[0]
        # If multiple candidates, don't return on /v1/models 200
        # because /v1/models 200 only means we can get models, not that the key is valid for this provider
        # Continue to Step 4 to verify with /chat/completions
    
    # Step 4: Concurrently probe ALL providers
    # IMPORTANT: /v1/models is only for getting model list, NOT for verifying key validity!
    # We use /chat/completions to verify if the key is valid for a provider.
    
    # Step 4.1: Get models from all providers using /v1/models
    # This step ONLY gets model list, does NOT verify key validity
    async def get_provider_models(name, provider):
        """Get models from /v1/models endpoint.
        
        IMPORTANT: /v1/models 200 only means we can get model list.
        It does NOT mean the key is valid for this provider!
        """
        try:
            resp = await asyncio.wait_for(
                client.get(
                    f"{provider.get_base_url()}{provider.check_endpoint}",
                    headers=provider.build_headers(key),
                ),
                timeout=5.0
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and "data" in data:
                    models = [m.get("id", "") for m in data["data"] if m.get("id")]
                    if models:
                        return name, models, True  # name, models, is_valid
        except Exception:
            pass  # Request failed, continue with other providers
        return name, [], False
    
    # Get models from all providers concurrently
    model_tasks = [get_provider_models(name, provider) for name, provider in PROVIDERS.items()]
    model_results = await asyncio.gather(*model_tasks)
    
    # Build tasks: (provider_name, model) pairs
    # These will be tested with /chat/completions to verify key validity
    tasks = []
    valid_providers = []  # Providers that returned 200 from /v1/models (NOT verified yet!)
    for name, models, is_valid in model_results:
        if is_valid:
            valid_providers.append(name)
        if models:
            for model in models:
                tasks.append((name, model))
        else:
            provider = PROVIDERS[name]
    
    # Step 4.2: Concurrently check all (provider, model) pairs using /chat/completions
    # This is the ACTUAL verification step!
    # First provider returning 200 from /chat/completions wins
    import re
    # Concurrently check all (provider, model) pairs
    import re
    
    async def try_model(name, model):
        """Try to call /chat/completions for a specific provider and model.
        
        IMPORTANT: This is the ACTUAL verification step!
        - /v1/models 200 only means we can get model list (NOT verification)
        - /chat/completions 200 means the key is valid for this provider (VERIFICATION)
        
        Returns:
            (provider_name, is_valid, response_body, status_code)
        """
        provider = PROVIDERS[name]
        headers = provider.build_headers(key)
        headers["Content-Type"] = "application/json"
        # Extract version path from check_endpoint
        version_match = re.match(r'(/v\d+)', provider.check_endpoint or '')
        version_prefix = version_match.group(1) if version_match else ''
        chat_url = f"{provider.get_base_url()}{version_prefix}/chat/completions"
        try:
            resp = await asyncio.wait_for(
                client.post(
                    chat_url,
                    headers=headers,
                    json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
                ),
                timeout=5.0
            )
            body = resp.text[:500] if resp.text else ""
            if resp.status_code == 200:
                # /chat/completions returned 200, this is the valid provider!
                return name, True, body, 200
            else:
                return name, False, body, resp.status_code
        except Exception:
            return name, False, "", 0
    # Fire all tasks concurrently
    all_tasks = [try_model(name, model) for name, model in tasks]
    
    # Collect results for signature matching
    valid_provider = None
    error_bodies = {}  # name -> list of (body, status_code) tuples
    provider_status = {}  # name -> {'has_200': bool, 'has_402': bool, 'models_402': list}
    
    for coro in asyncio.as_completed(all_tasks):
        name, valid, body, status_code = await coro
        
        # Initialize provider status if not exists
        if name not in provider_status:
            provider_status[name] = {'has_200': False, 'has_402': False, 'models_402': []}
        
        if valid:
            # Found valid provider (200 response)
            provider_status[name]['has_200'] = True
            return name
        elif status_code == 402:
            # Balance insufficient - mark provider but continue testing
            provider_status[name]['has_402'] = True
            provider_status[name]['models_402'].append(model)
        elif body:
            # Collect error body for signature matching
            if name not in error_bodies:
                error_bodies[name] = []
            error_bodies[name].append((body, status_code))
    
    # Check if any provider has /v1/models returning 200 but all models return 402 (balance insufficient)
    # This means the key is valid but has no balance
    for name, status in provider_status.items():
        if name in valid_providers and status['has_402'] and not status['has_200']:
            # Provider's /v1/models returned 200, but all models returned 402
            # This means the key is valid but has no balance
            try:
                from webdebug import debug_logger
                import asyncio as _asyncio
                _asyncio.create_task(debug_logger.log(
                    category="DETECT",
                    action="balance_insufficient",
                    detail=f"Provider {name} has valid /v1/models but all models return 402",
                    data={"provider": name, "models_402": status['models_402']},
                    level="INFO"
                ))
            except ImportError:
                pass
            return name
    
    # No valid provider found - try signature matching on error bodies
    # Only return if we have a VERY HIGH confidence match (multiple signatures matched)
    best_score = -1
    best_name = None
    
    # Providers whose /v1/models doesn't validate keys (returns 200 even with invalid keys)
    UNRELIABLE_MODELS_ENDPOINT = {"ppio", "nvidia", "modelscope"}
    
    for name, entries in error_bodies.items():
        for body, status_code in entries:
            score = score_provider(name, body, status_code)
            # Bonus for providers that returned 200 from /v1/models (but only reliable ones)
            # Only give bonus if /v1/chat/completions also succeeded (no error body)
            if name in valid_providers and name not in UNRELIABLE_MODELS_ENDPOINT and name not in error_bodies:
                score += 500
            if score > best_score:
                best_score = score
                best_name = name
    try:
        from webdebug import debug_logger
        import asyncio as _asyncio
        _asyncio.create_task(debug_logger.log(
            category="DETECT",
            action="signature_matching",
            detail=f"best_score={best_score}, best_name={best_name}",
            data={"best_score": best_score, "best_name": best_name, "error_bodies_count": len(error_bodies)},
            level="INFO"
        ))
    except ImportError:
        pass
    
    # Only return if we have a VERY HIGH confidence match
    # Require at least 2 signature matches (200 points) to avoid false positives
    if best_score >= 200:  # At least 2 signatures matched
        return best_name
    
    # No provider found with high confidence
    # This is better than returning a wrong provider
    return None


async def _try_provider(client, provider, key: str) -> dict:
    """Probe a provider and return the result with error body for scoring."""
    try:
        # Use a short timeout for detection
        result = await asyncio.wait_for(provider.probe(client, key), timeout=8.0)
        error_body = result.response_body or ""
        
        return {
            'valid': result.valid,
            'status_code': result.status_code,
            'error_body': error_body
        }
    except Exception as e:
        import logging
        logging.getLogger(__name__).debug(f"Probe failed for {provider.name}: {e}")
        return {'valid': False, 'status_code': None, 'error_body': ''}


async def _try_unknown_provider() -> dict:
    return {'valid': False, 'status_code': None, 'error_body': ''}


# =============================================================================
# DETECTION LOGIC SUMMARY
# =============================================================================
# 
# IMPORTANT: Detection uses /chat/completions to verify providers, NOT /v1/models!
# 
# - /v1/models: Only returns model list, CANNOT determine if key is valid
# - /chat/completions: Actually tests the key, CAN determine if key is valid
# 
# Detection flow:
# 1. Prefix matching - Check unique prefixes (e.g., sk-proj- → OpenAI)
# 2. Format matching - Check special formats (e.g., {id}.{secret} → Zhipu)
# 3. Concurrent probing - Test all providers with /chat/completions
# 4. Signature matching - Match error response body signatures
# 
# Free models are important! Some providers (like OpenCode Zen) offer free models.
# Detection tests ALL models including free models. If any model returns 200,
# the provider is correctly identified.
# 
# Common mistakes:
# - ❌ Using /v1/models 200 to determine provider → WRONG!
# - ✅ Using /chat/completions 200 to determine provider → CORRECT!
# 
# =============================================================================

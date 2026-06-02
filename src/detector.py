import asyncio
from .providers import PROVIDERS, KEY_PREFIX_MAP, PROVIDER_ERROR_SIGNATURES


# Extended key patterns for better detection
KEY_PATTERNS = {
    # AI Providers - unique prefixes for pattern detection
    "sk-or-v1-": "openrouter",
    "sk-ant-api03-": "anthropic",
    "sk-proj-": "openai",
    "sk-sp-": "dashscope",
    "sk-kimi-": "kimi-coding",
    "sk-cp-": "minimax-plan",
    "ms-": "modelscope",
    "AIza": "google",
    "xai-": "grok",
    "hf_": "huggingface",
    "r8_": "replicate",
    "pplx-": "perplexity",
    "gsk_": "groq",
    "fw_": "fireworks",
    "poe-": "poe",
    "AKID": "cstcloud",
    "tp-": "mimo-plan",
}


# Scoring weights
WEIGHT_SELF = 100      # Self-signature match = definitive
WEIGHT_CROSS = 10      # Cross-signature match = ambiguous
WEIGHT_RATE_LIMITED = 60  # 429 rate limited = medium confidence (lower than 200/401/403 but still usable)
MIN_WIN_SCORE = 50     # Minimum score to declare a winner
MIN_LEAD = 20          # Minimum lead over second place

# Unique signatures that ONLY belong to one provider.
# These are verified by actual API testing.
UNIQUE_SIGNATURES: dict[str, list[str]] = {
    "dashscope": ["aliyun", "model-studio", "modelstudio", "apikey-error"],
    "cerebras": ["cerebras"],
    "tencent-hunyuan": ["hunyuan", "tencent"],
    "baichuan": ["baichuan-ai.com"],
    "minimax": ["authorized_error", "login fail"],
    "minimax-plan": ["authorized_error", "login fail"],
    "yi": ["illegal apikey"],
    "kimi": ["invalid_authentication_error"],
    "dmxapi": ["rix_api_error"],
    "ocoolai": ["shell_api_error"],
    "hyperbolic": ["could not validate credentials"],
    "zai": ["token expired or incorrect"],
    "deepseek": ["authentication fails"],
    "doubao": ["authenticationerror"],
    "anthropic": ["anthropic", "x-api-key"],
    "openrouter": ["openrouter"],
    "together": ["together.xyz", "together.ai"],
    "mistral": ["mistral", "la plateforme"],
    "cohere": ["cohere"],
    "replicate": ["replicate"],
    "huggingface": ["huggingface", "hf_"],
    "fireworks": ["fireworks", "accounts/fireworks"],
    "perplexity": ["perplexity"],
    "grok": ["xai", "grok"],
    "zhipu": ["bigmodel", "zhipu"],
    "siliconflow": ["siliconflow", "silicon flow"],
    "stepfun": ["stepfun", "step-star"],
    "infini": ["infini", "infini-ai"],
    "nvidia": ["nvidia", "nim.api"],
    "poe": ["poe.com"],
    "modelscope": ["modelscope"],
    "mimo": ["xiaomimimo", "mimo"],
    "mimo-plan": ["xiaomimimo", "mimo"],
    "ai302": ["302.ai"],
    "ppio": ["ppio"],
    "cstcloud": ["cstcloud", "zhongsuanyun"],
    "longcat": ["longcat"],
    "openai": ["openai"],
    "dashscope-coding": ["dashscope-coding"],
    "google": ["generativelanguage"],
    "groq": ["groq"],
}


def detect_by_prefix(key: str) -> list[str]:
    """Return candidates from the LONGEST matching prefix only."""
    for prefix, providers in sorted(KEY_PREFIX_MAP.items(), key=lambda x: -len(x[0])):
        if key.startswith(prefix):
            return list(providers)
    return []


def detect_by_pattern(key: str) -> str:
    """Detect provider by key pattern."""
    for pattern, provider in sorted(KEY_PATTERNS.items(), key=lambda x: -len(x[0])):
        if key.startswith(pattern):
            return provider
    return None


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
    sigs = UNIQUE_SIGNATURES.get(provider_name, [])
    for sig in sigs:
        if sig.lower() in body:
            score += weight
    
    return score


async def detect_provider(client, key: str, suspected_provider: str = None) -> str:
    # If suspected provider is given and exists, try it first
    if suspected_provider:
        provider_name = suspected_provider.lower()
        if provider_name in PROVIDERS:
            provider = PROVIDERS[provider_name]
            result = await provider.probe(client, key)
            if result.valid:
                return provider_name

    # Try pattern matching first
    pattern_match = detect_by_pattern(key)
    if pattern_match:
        if pattern_match in PROVIDERS:
            provider = PROVIDERS[pattern_match]
            result = await provider.probe(client, key)
            if result.valid:
                return pattern_match
            # Probe failed — fall through to prefix matching below
        else:
            return pattern_match  # Not in PROVIDERS, return for detection only

    # Try prefix matching
    candidates = detect_by_prefix(key)
    if len(candidates) == 1:
        return candidates[0]
    elif len(candidates) > 1:
        # Probe all candidates concurrently
        tasks = []
        for name in candidates:
            if name in PROVIDERS:
                tasks.append(asyncio.create_task(_try_provider(client, PROVIDERS[name], key)))
            else:
                tasks.append(asyncio.create_task(_try_unknown_provider()))
        
        # Wait for all to complete, with early exit on 200
        auth_results = []  # Collect 401/402/403 results for scoring
        pending_tasks = set(tasks)
        
        while pending_tasks:
            done, pending_tasks = await asyncio.wait(pending_tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                try:
                    result = task.result()
                    idx = tasks.index(task)
                    if isinstance(result, dict):
                        status_code = result.get('status_code')
                        if status_code == 200:
                            # 200 = definitely this provider
                            for t in pending_tasks:
                                t.cancel()
                            return candidates[idx]
                        elif status_code in (400, 401, 402, 403, 429):
                            # Save for scoring
                            auth_results.append((idx, result))
                except Exception:
                    pass
        
        # All probes done. No 200 found.
        # Use fingerprint scoring to identify the provider.
        if auth_results:
            scores = {}
            for idx, result in auth_results:
                provider_name = candidates[idx]
                error_body = result.get('error_body', '')
                score = score_provider(provider_name, error_body, result.get('status_code'))
                scores[provider_name] = score
            
            # Find the winner
            if scores:
                sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                top_provider, top_score = sorted_scores[0]
                
                # Check if winner meets minimum score and has clear lead
                if top_score >= MIN_WIN_SCORE:
                    if len(sorted_scores) == 1:
                        return top_provider
                    second_score = sorted_scores[1][1]
                    if top_score - second_score >= MIN_LEAD:
                        return top_provider
        
        return 'unknown'


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

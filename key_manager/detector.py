import asyncio
import re
from .providers import PROVIDERS, KEY_PREFIX_MAP, PROVIDER_ERROR_SIGNATURES
from .providers.models_registry import PROVIDER_MODELS

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
    # ═══ 国内服务商 ═══
    # dashscope: 实际返回 "Incorrect API key provided. For details, see: https://help.aliyun.com/zh/model-studio/error-code#apikey-error"
    "dashscope": ["model-studio", "modelstudio", "apikey-error"],
    "dashscope-coding": ["aliyun", "model-studio", "modelstudio"],
    # tencent-hunyuan: 实际返回 "Incorrect API key provided: sk-inval...You can find your API key at https://console.cloud.tencent.com/hunyuan/start"
    "tencent-hunyuan": ["hunyuan", "console.cloud.tencent.com"],
    "baichuan": ["baichuan-ai.com", "platform.baichuan-ai.com"],
    # minimax: 实际返回 "authorized_error", "login fail"
    "minimax": ["authorized_error", "login fail"],
    "minimax-plan": ["authorized_error", "login fail"],
    # yi: 实际返回 "Illegal ApiKey"
    "yi": ["illegal apikey"],
    # kimi: 实际返回 "invalid_authentication_error"
    "kimi": ["invalid_authentication_error"],
    "kimi-coding": ["invalid_authentication_error", "the api key appears to be invalid"],
    # siliconflow: 实际返回 "Api key is invalid" (注意大小写)
    "siliconflow": ["api key is invalid"],
    # stepfun: 实际返回 "Incorrect API key provided" (与 dashscope 重复，用 type 区分)
    "stepfun": ["incorrect api key provided", "invalid_api_key"],
    # doubao: 实际返回 "AuthenticationError"
    "doubao": ["authenticationerror"],
    # infini: 实际返回 "请使用正确的api key进行请求"
    "infini": ["请使用正确的api key进行请求"],
    "infini-coding": ["请使用正确的api key进行请求"],
    # zhipu: 实际返回 "令牌已过期或验证不正确"
    "zhipu": ["令牌已过期或验证不正确"],
    "zhipu-coding": ["令牌已过期或验证不正确"],
    # mimo: 实际返回 "Invalid API Key", "Please provide valid API Key"
    "mimo": ["invalid api key", "please provide valid api key"],
    "mimo-plan": ["invalid api key", "please provide valid api key"],
    # cstcloud: 实际返回 {"code":401,"message":"Unauthorized"}
    "cstcloud": ["cstcloud", "zhongsuanyun"],
    "modelscope": ["modelscope"],
    "longcat": ["longcat"],
    "ppio": ["ppio"],
    # ═══ 国外服务商 ═══
    # deepseek: 实际返回 "Authentication Fails, Your api key: ****2345 is invalid"
    "deepseek": ["authentication fails"],
    # anthropic: 实际返回 "Request not allowed"
    "anthropic": ["request not allowed", "anthropic", "x-api-key"],
    # openrouter: 实际返回 "Missing Authentication header"
    "openrouter": ["missing authentication header"],
    # together: 实际返回 "Unauthorized"
    "together": [],
    "mistral": ["mistral", "la plateforme"],
    # cohere: 实际返回 403 HTML 页面
    "cohere": [],
    # replicate: 实际返回 "Unauthenticated"
    "replicate": ["unauthenticated", "you did not pass a valid authentication token"],
    "huggingface": ["huggingface", "hf_"],
    "fireworks": ["fireworks", "accounts/fireworks"],
    "perplexity": ["perplexity"],
    # grok: 实际返回 "Incorrect API key provided: sk***45...console.x.ai."
    "grok": ["console.x.ai"],
    "cerebras": ["cerebras"],
    "nvidia": ["nvidia", "nim.api"],
    # hyperbolic: 实际返回 "Could not validate credentials"
    "hyperbolic": ["could not validate credentials"],
    "poe": ["poe.com"],
    "ai302": ["302.ai"],
    # dmxapi: 实际返回 "rix_api_error"
    "dmxapi": ["rix_api_error"],
    # ocoolai: 实际返回 "shell_api_error"
    "ocoolai": ["shell_api_error"],
    # zai: 实际返回 "token expired or incorrect"
    "zai": ["token expired or incorrect"],
    # openai: 实际返回 "Incorrect API key provided: sk-inval...platform.openai.com..."
    "openai": ["platform.openai.com"],
    "google": ["generativelanguage"],
    "groq": ["groq"],
}

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


def detect_by_pattern(key: str) -> str:
    """Detect provider by key pattern."""
    for pattern, provider in sorted(KEY_PATTERNS.items(), key=lambda x: -len(x[0])):
        if key.startswith(pattern):
            return provider
    return None


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
    sigs = UNIQUE_SIGNATURES.get(provider_name, [])
    for sig in sigs:
        if sig.lower() in body:
            score += weight
    
    return score


async def detect_provider(client, key: str, suspected_provider: str = None) -> str:
    """Detect provider by concurrently probing ALL providers with multiple models.
    
    Strategy:
    1. If suspected_provider given, try it first
    2. If key matches unique pattern, try that provider
    3. Otherwise, concurrently probe ALL providers with their top 5 models
    4. First provider returning 200 wins
    """
    import time
    
    # Step 1: If suspected provider, try it first
    if suspected_provider:
        provider_name = suspected_provider.lower()
        if provider_name in PROVIDERS:
            provider = PROVIDERS[provider_name]
            result = await provider.check(client, key)
            if result.valid:
                return provider_name
    
    # Step 2: Try pattern matching for unique prefixes
    pattern_match = detect_by_pattern(key)
    if pattern_match and pattern_match in PROVIDERS:
        provider = PROVIDERS[pattern_match]
        result = await provider.check(client, key)
        if result.valid:
            return pattern_match
    
    # Step 3: Try format matching (e.g., Zhipu's {id}.{secret})
    format_candidates = detect_by_format(key)
    if format_candidates:
        # Debug logging
        try:
            from webdebug import debug_logger
            import asyncio as _asyncio
            _asyncio.create_task(debug_logger.log(
                category="DETECT",
                action="detect_by_format",
                detail=f"Key format matched {len(format_candidates)} candidates",
                data={"key_prefix": key[:10] + "...", "candidates": format_candidates},
                level="INFO"
            ))
        except ImportError:
            pass
        
        # Try each format candidate
        async def try_format(name):
            if name in PROVIDERS:
                result = await PROVIDERS[name].check(client, key)
                return name, result.valid
            return name, False
        format_tasks = [try_format(n) for n in format_candidates]
        format_results = await asyncio.gather(*format_tasks)
        for name, valid in format_results:
            if valid:
                return name
    # Step 4: Concurrently probe ALL providers
    # First, get models from all providers concurrently
    async def get_provider_models(name, provider):
        """Get models from /v1/models endpoint."""
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
                        return name, models
        except:
            pass
        return name, []
    
    # Get models from all providers concurrently
    model_tasks = [get_provider_models(name, provider) for name, provider in PROVIDERS.items()]
    model_results = await asyncio.gather(*model_tasks)
    
    # Build tasks: (provider_name, model) pairs
    tasks = []
    for name, models in model_results:
        if not models:
            continue
        for model in models:
            tasks.append((name, model))
    
    # Concurrently check all (provider, model) pairs
    import re
    
    async def try_model(name, model):
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
                return name, True, body
            elif resp.status_code in (401, 403):
                # Invalid key, but return body for signature matching
                return name, False, body
            return name, False, body
        except:
            return name, False, ""
    
    # Fire all tasks concurrently
    all_tasks = [try_model(name, model) for name, model in tasks]
    
    # Collect results for signature matching
    valid_provider = None
    error_bodies = {}  # name -> list of error bodies
    
    for coro in asyncio.as_completed(all_tasks):
        name, valid, body = await coro
        if valid:
            # Found valid provider, return immediately
            return name
        elif body:
            # Collect error body for signature matching
            if name not in error_bodies:
                error_bodies[name] = []
            error_bodies[name].append(body)
    
    # No valid provider found - try signature matching on error bodies
    # Only return if we have a VERY HIGH confidence match (multiple signatures matched)
    best_score = -1
    best_name = None
    
    for name, bodies in error_bodies.items():
        for body in bodies:
            score = score_provider(name, body, 401)
            if score > best_score:
                best_score = score
                best_name = name
    
    # Debug logging for signature matching
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

from .base import ProviderBase, CheckResult, TestResult
from .openai import OpenAIProvider
from .anthropic import AnthropicProvider
from .google import GoogleProvider
from .grok import GrokProvider
from .deepseek import DeepSeekProvider
from .groq import GroqProvider
from .perplexity import PerplexityProvider
from .together import TogetherProvider
from .mistral import MistralProvider
from .cohere import CohereProvider
from .replicate import ReplicateProvider
from .huggingface import HuggingFaceProvider
from .fireworks import FireworksProvider
from .openrouter import OpenRouterProvider
from .dashscope import DashScopeProvider
from .modelscope import ModelScopeProvider
from .zhipu import ZhipuProvider
from .kimi import KimiProvider
from .minimax import MiniMaxProvider
from .minimax_plan import MiniMaxTokenPlanProvider
from .siliconflow import SiliconFlowProvider
from .baichuan import BaichuanProvider
from .yi import YiProvider
from .cerebras import CerebrasProvider
from .nvidia import NvidiaProvider
from .hyperbolic import HyperbolicProvider
from .poe import PoeProvider
from .longcat import LongCatProvider
from .mimo import MiMoProvider
from .mimo_plan import MiMoPlanProvider
from .stepfun import StepFunProvider
from .doubao import DoubaoProvider
from .infini import InfiniProvider
from .zai import ZAIProvider
from .ai302 import AI302Provider
from .ppio import PPIOProvider
from .dmxapi import DMXAPIProvider
from .ocoolai import OCoolAIProvider
from .dashscope_coding import DashScopeCodingProvider
from .tencent_hunyuan import TencentHunyuanProvider
from .cstcloud import CSTCloudProvider
from .zhipu_coding import ZhipuCodingProvider
from .kimi_coding import KimiCodingProvider
from .infini_coding import InfiniCodingProvider
from .opencode import OpenCodeGoProvider
from .opencode_zen import OpenCodeZenProvider

# Provider registry
PROVIDERS: dict[str, ProviderBase] = {
    "openai": OpenAIProvider(),
    "anthropic": AnthropicProvider(),
    "google": GoogleProvider(),
    "grok": GrokProvider(),
    "deepseek": DeepSeekProvider(),
    "groq": GroqProvider(),
    "perplexity": PerplexityProvider(),
    "together": TogetherProvider(),
    "mistral": MistralProvider(),
    "cohere": CohereProvider(),
    "replicate": ReplicateProvider(),
    "huggingface": HuggingFaceProvider(),
    "fireworks": FireworksProvider(),
    "openrouter": OpenRouterProvider(),
    "dashscope": DashScopeProvider(),
    "modelscope": ModelScopeProvider(),
    "zhipu": ZhipuProvider(),
    "kimi": KimiProvider(),
    "minimax": MiniMaxProvider(),
    "minimax-plan": MiniMaxTokenPlanProvider(),
    "siliconflow": SiliconFlowProvider(),
    "baichuan": BaichuanProvider(),
    "yi": YiProvider(),
    "cerebras": CerebrasProvider(),
    "nvidia": NvidiaProvider(),
    "hyperbolic": HyperbolicProvider(),
    "poe": PoeProvider(),
    "longcat": LongCatProvider(),
    "mimo": MiMoProvider(),
    "mimo-plan": MiMoPlanProvider(),
    "stepfun": StepFunProvider(),
    "doubao": DoubaoProvider(),
    "infini": InfiniProvider(),
    "zai": ZAIProvider(),
    "ai302": AI302Provider(),
    "ppio": PPIOProvider(),
    "dmxapi": DMXAPIProvider(),
    "ocoolai": OCoolAIProvider(),
    "dashscope-coding": DashScopeCodingProvider(),
    "tencent-hunyuan": TencentHunyuanProvider(),
    "cstcloud": CSTCloudProvider(),
    "zhipu-coding": ZhipuCodingProvider(),
    "kimi-coding": KimiCodingProvider(),
    "infini-coding": InfiniCodingProvider(),
    "opencode-go": OpenCodeGoProvider(),
    "opencode-zen": OpenCodeZenProvider(),
}

# Key prefix to provider mapping (for auto-detection)
# Key prefix to provider mapping (for auto-detection)
# Ordered by specificity (longer prefixes first)
KEY_PREFIX_MAP: dict[str, list[str]] = {
    # AI Providers - unique prefixes
    "sk-ant-api03-": ["anthropic"],
    "sk-or-v1-": ["openrouter"],
    "sk-proj-": ["openai"],
    "sk-sp-": ["dashscope-coding"],
    "sk-ws-": ["dashscope"],
    "ms-": ["modelscope"],
    "AIza": ["google"],
    "xai-": ["grok"],
    "hf_": ["huggingface"],
    "r8_": ["replicate"],
    "pplx-": ["perplexity"],
    "gsk_": ["groq"],
    "fw_": ["fireworks"],
    "poe-": ["poe"],
    "AKID": ["cstcloud"],
    # Generic sk- prefix (must be last - shared by multiple providers)
    # Excluded: ppio, nvidia, modelscope, ai21 - their /models endpoints don't validate keys
    "sk-": ["openai", "deepseek", "together", "fireworks", "perplexity", "dashscope", "kimi", "siliconflow", "cerebras", "hyperbolic", "mimo", "stepfun", "infini", "zai", "ai302", "dmxapi", "ocoolai", "dashscope-coding", "tencent-hunyuan", "opencode-go", "opencode-zen"],
    # MiniMax Token Plan keys
    "sk-cp-": ["minimax-plan", "infini-coding"],
    # Kimi Coding Plan keys
    "sk-kimi-": ["kimi-coding"],
    # MiMo Token Plan keys
    "tp-": ["mimo-plan"],
}

# Display names for UI (maps internal provider name → human-readable name)
DISPLAY_NAMES: dict[str, str] = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google Gemini",
    "deepseek": "DeepSeek",
    "groq": "Groq",
    "grok": "Grok (xAI)",
    "perplexity": "Perplexity",
    "together": "Together AI",
    "mistral": "Mistral",
    "cohere": "Cohere",
    "replicate": "Replicate",
    "huggingface": "Hugging Face",
    "fireworks": "Fireworks",
    "openrouter": "OpenRouter",
    "dashscope": "阿里百炼",
    "dashscope-coding": "阿里百炼编程",
    "modelscope": "魔搭 ModelScope",
    "zhipu": "智谱 GLM",
    "kimi": "Kimi (月之暗面)",
    "minimax": "MiniMax",
    "minimax-plan": "MiniMax 计划版",
    "siliconflow": "硅基流动",
    "baichuan": "百川",
    "yi": "零一万物",
    "cerebras": "Cerebras",
    "nvidia": "NVIDIA",
    "hyperbolic": "Hyperbolic",
    "poe": "Poe",
    "longcat": "LongCat",
    "mimo": "MiMo",
    "mimo-plan": "MiMo 计划版",
    "stepfun": "阶跃星辰",
    "doubao": "豆包 (字节)",
    "infini": "无问芯穹",
    "zai": "ZAI",
    "ai302": "AI302",
    "ppio": "PPIO",
    "dmxapi": "DMXAPI",
    "ocoolai": "OCoolAI",
    "tencent-hunyuan": "腾讯混元",
    "zhipu-coding": "智谱 GLM 编程版",
    "kimi-coding": "Kimi 编程版",
    "infini-coding": "无问芯穹 编程版",
    "cstcloud": "中算云",
}


def get_display_name(provider_name: str) -> str:
    """Get human-readable display name for a provider."""
    return DISPLAY_NAMES.get(provider_name, provider_name)


# Error body signatures for provider detection when keys are invalid.
# Each provider maps to a list of lowercase substrings found in their error responses.
PROVIDER_ERROR_SIGNATURES: dict[str, list[str]] = {
    # ═══ 国内服务商 ═══
    "dashscope": ["aliyun", "model-studio", "modelstudio", "apikey-error"],
    "dashscope-coding": ["aliyun", "model-studio", "modelstudio"],
    "tencent-hunyuan": ["hunyuan", "console.cloud.tencent.com"],
    "baichuan": ["baichuan-ai.com", "platform.baichuan-ai.com"],
    "minimax": ["authorized_error", "login fail"],
    "minimax-plan": ["authorized_error", "login fail"],
    "yi": ["illegal apikey"],
    "kimi": ["invalid_authentication_error"],
    "kimi-coding": ["invalid_authentication_error", "the api key appears to be invalid"],
    "siliconflow": ["api key is invalid"],
    "stepfun": ["incorrect api key provided", "invalid_api_key"],
    "doubao": ["authenticationerror"],
    "infini": ["请使用正确的api key进行请求"],
    "infini-coding": ["请使用正确的api key进行请求"],
    "zhipu": ["令牌已过期或验证不正确"],
    "zhipu-coding": ["令牌已过期或验证不正确"],
    "mimo": ["invalid api key", "please provide valid api key"],
    "mimo-plan": ["invalid api key", "please provide valid api key"],
    "cstcloud": ["cstcloud", "zhongsuanyun"],
    "modelscope": ["modelscope"],
    "longcat": ["longcat"],
    "ppio": ["ppio"],
    # ═══ 国外服务商 ═══
    "deepseek": ["authentication fails"],
    "anthropic": ["request not allowed", "anthropic", "x-api-key"],
    "openrouter": ["missing authentication header"],
    "together": [],
    "mistral": ["mistral", "la plateforme"],
    "cohere": [],
    "replicate": ["unauthenticated", "you did not pass a valid authentication token"],
    "huggingface": ["huggingface", "hf_"],
    "fireworks": ["fireworks", "accounts/fireworks"],
    "perplexity": ["perplexity"],
    # grok: 实际返回 "Incorrect API key provided: sk***45...console.x.ai."
    "grok": ["console.x.ai"],
    "cerebras": ["cerebras"],
    "nvidia": ["nvidia", "nim.api"],
    "hyperbolic": ["could not validate credentials"],
    "poe": ["poe.com"],
    "ai302": ["302.ai"],
    "dmxapi": ["rix_api_error"],
    "ocoolai": ["shell_api_error"],
    "zai": ["token expired or incorrect"],
    # openai: 实际返回 "Incorrect API key provided: sk-inval...platform.openai.com..."
    "openai": ["platform.openai.com"],
    "google": ["generativelanguage"],
    # grok: 实际返回 "Incorrect API key provided: sk***45...console.x.ai."
    "groq": ["groq"],
    "opencode-go": ["opencode.ai", "zen/go", "creditserror", "no payment method"],
    "opencode-zen": ["opencode.ai", "zen/v1", "creditserror", "no payment method"],
}




# Provider website and documentation URLs
PROVIDER_WEBSITES: dict[str, dict[str, str]] = {
    "openai": {"name": "OpenAI", "url": "https://platform.openai.com", "docs": "https://platform.openai.com/docs"},
    "anthropic": {"name": "Anthropic", "url": "https://console.anthropic.com", "docs": "https://docs.anthropic.com"},
    "google": {"name": "Google AI", "url": "https://aistudio.google.com", "docs": "https://ai.google.dev/docs"},
    "deepseek": {"name": "DeepSeek", "url": "https://platform.deepseek.com", "docs": "https://platform.deepseek.com/api-docs"},
    "groq": {"name": "Groq", "url": "https://console.groq.com", "docs": "https://docs.groq.com"},
    "mistral": {"name": "Mistral AI", "url": "https://console.mistral.ai", "docs": "https://docs.mistral.ai"},
    "cohere": {"name": "Cohere", "url": "https://dashboard.cohere.com", "docs": "https://docs.cohere.com"},
    "replicate": {"name": "Replicate", "url": "https://replicate.com", "docs": "https://replicate.com/docs"},
    "huggingface": {"name": "Hugging Face", "url": "https://huggingface.co", "docs": "https://huggingface.co/docs"},
    "fireworks": {"name": "Fireworks AI", "url": "https://fireworks.ai", "docs": "https://docs.fireworks.ai"},
    "perplexity": {"name": "Perplexity", "url": "https://perplexity.ai", "docs": "https://docs.perplexity.ai"},
    "together": {"name": "Together AI", "url": "https://api.together.xyz", "docs": "https://docs.together.ai"},
    "openrouter": {"name": "OpenRouter", "url": "https://openrouter.ai", "docs": "https://openrouter.ai/docs"},
    "dashscope": {"name": "阿里百炼", "url": "https://dashscope.aliyun.com", "docs": "https://help.aliyun.com/zh/dashscope/"},
    "zhipu": {"name": "智谱 AI", "url": "https://open.bigmodel.cn", "docs": "https://open.bigmodel.cn/dev/api"},
    "kimi": {"name": "Kimi", "url": "https://platform.moonshot.cn", "docs": "https://platform.moonshot.cn/docs"},
    "minimax": {"name": "MiniMax", "url": "https://platform.minimaxi.com", "docs": "https://platform.minimaxi.com/document"},
    "siliconflow": {"name": "硅基流动", "url": "https://siliconflow.cn", "docs": "https://docs.siliconflow.cn"},
    "baichuan": {"name": "百川智能", "url": "https://platform.baichuan-ai.com", "docs": "https://platform.baichuan-ai.com/docs"},
    "yi": {"name": "零一万物", "url": "https://platform.lingyiwanwu.com", "docs": "https://platform.lingyiwanwu.com/docs"},
    "cerebras": {"name": "Cerebras", "url": "https://cerebras.ai", "docs": "https://docs.cerebras.ai"},
    "nvidia": {"name": "NVIDIA", "url": "https://build.nvidia.com", "docs": "https://docs.api.nvidia.com"},
    "grok": {"name": "Grok (xAI)", "url": "https://console.x.ai", "docs": "https://docs.x.ai"},
    "poe": {"name": "Poe", "url": "https://poe.com", "docs": "https://developer.poe.com"},
    "stepfun": {"name": "阶跃星辰", "url": "https://platform.stepfun.com", "docs": "https://platform.stepfun.com/docs"},
    "doubao": {"name": "豆包", "url": "https://console.volcengine.com/ark", "docs": "https://www.volcengine.com/docs/82379"},
    "infini": {"name": "无问芯穹", "url": "https://cloud.infini-ai.com", "docs": "https://docs.infini-ai.com"},
    "mimo": {"name": "MiMo", "url": "https://mimo.xiaomi.com", "docs": "https://mimo.xiaomi.com/docs"},
    "hyperbolic": {"name": "Hyperbolic", "url": "https://hyperbolic.xyz", "docs": "https://docs.hyperbolic.xyz"},
    "modelscope": {"name": "魔搭", "url": "https://modelscope.cn", "docs": "https://modelscope.cn/docs"},
    "ppio": {"name": "PPIO", "url": "https://ppinfra.com", "docs": "https://docs.ppinfra.com"},
    "dmxapi": {"name": "DMXAPI", "url": "https://www.dmxapi.cn", "docs": "https://www.dmxapi.cn/docs"},
    "ocoolai": {"name": "OCoolAI", "url": "https://ocoolai.com", "docs": "https://ocoolai.com/docs"},
    "ai302": {"name": "AI302", "url": "https://302.ai", "docs": "https://302.ai/docs"},
    "zai": {"name": "ZAI", "url": "https://zai.ai", "docs": "https://zai.ai/docs"},
    "longcat": {"name": "LongCat", "url": "https://longcat.com", "docs": "https://longcat.com/docs"},
    "tencent-hunyuan": {"name": "腾讯混元", "url": "https://cloud.tencent.com/product/hunyuan", "docs": "https://cloud.tencent.com/document/product/1729"},
    "cstcloud": {"name": "中算云", "url": "https://www.cstcloud.com", "docs": "https://www.cstcloud.com/docs"},
    "opencode-go": {"name": "OpenCode Go", "url": "https://opencode.ai", "docs": "https://opencode.ai/docs/zh-cn/go/"},
    "opencode-zen": {"name": "OpenCode Zen", "url": "https://opencode.ai", "docs": "https://opencode.ai/docs/"},
    "dashscope-coding": {"name": "阿里百炼编程", "url": "https://dashscope.aliyun.com", "docs": "https://help.aliyun.com/zh/dashscope/"},
    "mimo-plan": {"name": "MiMo 计划版", "url": "https://mimo.xiaomi.com", "docs": "https://mimo.xiaomi.com/docs"},
    "minimax-plan": {"name": "MiniMax 计划版", "url": "https://platform.minimaxi.com", "docs": "https://platform.minimaxi.com/document"},
    "zhipu-coding": {"name": "智谱 GLM 编程版", "url": "https://open.bigmodel.cn", "docs": "https://open.bigmodel.cn/dev/api"},
    "kimi-coding": {"name": "Kimi 编程版", "url": "https://platform.moonshot.cn", "docs": "https://platform.moonshot.cn/docs"},
    "infini-coding": {"name": "无问芯穹 编程版", "url": "https://cloud.infini-ai.com", "docs": "https://docs.infini-ai.com"},
}


"""
模型能力检测模块 v2

从 models.dev (https://models.dev/api.json) 获取模型能力数据，
基于显式字段而非正则模式匹配。支持三层降级：
1. 从 GitHub/本地加载 models.dev 数据
2. 使用本地缓存（12h TTL）
3. 使用硬编码兜底数据

v2 变更:
- vision/tooluse/reasoning: O(1) dict 查表 (来自 models.dev 显式字段)
- embedding/rerank/websearch/free: 已移除 (models.dev 无对应字段, 不可靠)

用法:
    from key_manager.model_capabilities import detector
    await detector.load()
    if detector.is_vision_model("gpt-5"):
        print("支持视觉")
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# ── 配置 ─────────────────────────────────────────────────────────────────

CAPS_FILE = Path("data/model_capabilities.json")       # models.dev 生成的能力文件
CACHE_FILE = Path("data/cache/model_capabilities.json")  # 本地缓存
FALLBACK_FILE = Path("data/model_capabilities_fallback.json")
CACHE_TTL = timedelta(hours=12)
SCHEMA_VERSION = 2  # v2: per-model dict format


# ── 检测器 ───────────────────────────────────────────────────────────────

class ModelCapabilityDetector:
    """模型能力检测器 v2 — 仅 models.dev 字段 (vision/tooluse/reasoning)"""

    def __init__(self) -> None:
        self._models: dict[str, dict[str, bool]] = {}   # v2: per-model dict
        self._loaded_from: str | None = None
        self._loaded_at: datetime | None = None

    # ── 加载 ─────────────────────────────────────────────────────────

    async def load(self, force: bool = False) -> str:
        """三层降级加载: 主文件 → 缓存 → 兜底

        Returns:
            数据来源: "primary", "cache", "fallback"
        """
        if not force and self._models and self._loaded_at:
            if datetime.utcnow() - self._loaded_at < timedelta(hours=1):
                return self._loaded_from or "primary"

        # 第 1 层: 主文件
        try:
            self._load_models(CAPS_FILE)
            self._loaded_from = "primary"
            self._loaded_at = datetime.utcnow()
            logger.info("模型能力加载成功 (primary)")
            return self._loaded_from
        except Exception as e:
            logger.warning(f"主文件加载失败: {e}")

        # 第 2 层: 缓存
        try:
            self._load_models(CACHE_FILE)
            self._loaded_from = "cache"
            self._loaded_at = datetime.utcnow()
            logger.info("模型能力加载成功 (cache)")
            return self._loaded_from
        except Exception as e:
            logger.warning(f"缓存加载失败: {e}")

        # 第 3 层: 兜底
        self._load_fallback()
        self._loaded_from = "fallback"
        self._loaded_at = datetime.utcnow()
        logger.info("模型能力加载成功 (fallback — minimal data)")
        return self._loaded_from

    def _load_models(self, path: Path) -> None:
        """加载 v2 格式的能力文件."""
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))

        # 兼容 v1 (regex) 和 v2 (per-model dict)
        if data.get("schema_version") == 2 and "models" in data:
            self._models = data["models"]
        elif data.get("schema_version") == 1:
            # v1 兼容: 从 regex patterns 构建 dict (保留已匹配结果)
            logger.warning("加载 v1 格式数据 — 功能降级")
            self._models = {}
        else:
            raise ValueError(f"不支持的 schema 版本: {data.get('schema_version')}")

    def _load_fallback(self) -> None:
        """硬编码最小兜底数据."""
        if FALLBACK_FILE.exists():
            return self._load_models(FALLBACK_FILE)

        self._models = {
            "gpt-5":      {"vision": True,  "tooluse": True,  "reasoning": True},
            "gpt-4o":     {"vision": True,  "tooluse": True,  "reasoning": False},
            "gpt-4o-mini":{"vision": True,  "tooluse": True,  "reasoning": False},
            "claude-sonnet-4": {"vision": True, "tooluse": True, "reasoning": False},
            "claude-opus-4":   {"vision": True, "tooluse": True, "reasoning": False},
            "gemini-2.5-pro":  {"vision": True, "tooluse": True, "reasoning": False},
            "deepseek-chat":   {"vision": False,"tooluse": True, "reasoning": False},
            "deepseek-reasoner":{"vision": False,"tooluse": True, "reasoning": True},
        }

    async def _fetch_remote(self) -> dict | None:
        """从 GitHub 拉取最新能力文件 (可选, 用于热更新)."""
        url = "https://raw.githubusercontent.com/Townrain/API-Key-Manager/main/data/model_capabilities.json"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                if data.get("schema_version") == 2 and "models" in data:
                    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                    CACHE_FILE.write_text(
                        json.dumps(data, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    return data["models"]
        except Exception as e:
            logger.warning(f"远程拉取失败: {e}")
        return None

    # ── models.dev 能力 (dict 查表, O(1)) ────────────────────────────

    def is_vision_model(self, model_id: str) -> bool:
        """判断是否为视觉模型。

        Args: model_id: 模型 ID (如 "gpt-5", "claude-sonnet-4-5")
        Returns: 是否支持图像/视频输入
        """
        entry = self._models.get(model_id)
        return entry.get("vision", False) if entry else False

    def is_tool_model(self, model_id: str) -> bool:
        """判断是否支持工具调用。

        Args: model_id: 模型 ID
        Returns: 是否支持 function-calling
        """
        entry = self._models.get(model_id)
        return entry.get("tooluse", False) if entry else False

    def is_reasoning_model(self, model_id: str) -> bool:
        """判断是否为推理模型 (支持思维链/thinking)。

        Args: model_id: 模型 ID
        Returns: 是否支持 reasoning
        """
        entry = self._models.get(model_id)
        return entry.get("reasoning", False) if entry else False

    # ── 聚合 ─────────────────────────────────────────────────────────

    def get_model_capabilities(self, model_id: str) -> dict[str, bool]:
        """获取模型的所有能力。

        Only vision/tooluse/reasoning from models.dev

        Returns:
            {"vision": bool, "tooluse": bool, "reasoning": bool}
        """
        return {
            "vision":    self.is_vision_model(model_id),
            "tooluse":   self.is_tool_model(model_id),
            "reasoning": self.is_reasoning_model(model_id),
        }

    # ── 元信息 ────────────────────────────────────────────────────────

    @property
    def loaded_from(self) -> str | None:
        """数据来源: primary / cache / fallback."""
        return self._loaded_from

    @property
    def is_loaded(self) -> bool:
        """是否已加载."""
        return bool(self._models)

    @property
    def model_count(self) -> int:
        """已加载的模型数量."""
        return len(self._models)


# 全局单例
detector = ModelCapabilityDetector()
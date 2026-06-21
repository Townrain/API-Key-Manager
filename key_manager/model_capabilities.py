"""
模型能力检测模块

从 GitHub 同步 Cherry Studio 的模型能力规则，支持三层降级：
1. 从 GitHub 拉取最新版
2. 使用本地缓存（7天 TTL）
3. 使用硬编码兜底数据

用法:
    from src.model_capabilities import detector

    # 初始化（在应用启动时调用）
    await detector.load()

    # 检测模型能力
    if detector.is_vision_model("gpt-4o"):
        print("支持视觉")

    if detector.is_tool_model("claude-sonnet-4"):
        print("支持工具调用")
"""

import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# 配置
CAPS_URL = "https://raw.githubusercontent.com/Townrain/API-Key-Manager/main/data/model_capabilities.json"
CACHE_FILE = Path("data/cache/model_capabilities.json")
FALLBACK_FILE = Path("data/model_capabilities_fallback.json")
CACHE_TTL = timedelta(days=7)
SCHEMA_VERSION = 1


class ModelCapabilityDetector:
    """模型能力检测器（三层降级）"""

    def __init__(self):
        self._caps: dict | None = None
        self._loaded_from: str | None = None
        self._loaded_at: datetime | None = None

    async def load(self, force: bool = False) -> str:
        """
        加载模型能力配置（三层降级）

        Returns:
            str: 数据来源 ("github", "cache", "fallback")

        降级顺序:
            1. 从 GitHub 拉取最新版
            2. 使用本地缓存（7天 TTL）
            3. 使用硬编码兜底数据
        """
        if not force and self._caps and self._loaded_at:
            # 检查是否需要重新加载（1小时内的请求直接返回缓存）
            if datetime.utcnow() - self._loaded_at < timedelta(hours=1):
                return self._loaded_from

        # 第 1 层：尝试从 GitHub 拉取
        try:
            self._caps = await self._fetch_from_github()
            if self._validate_schema(self._caps):
                self._save_to_cache(self._caps)
                self._loaded_from = "github"
                self._loaded_at = datetime.utcnow()
                logger.info("从 GitHub 加载模型能力配置成功")
                return self._loaded_from
            else:
                logger.warning("GitHub 返回的配置 schema 版本不兼容")
        except Exception as e:
            logger.warning(f"GitHub 拉取失败: {e}")

        # 第 2 层：使用本地缓存
        try:
            self._caps = self._load_from_cache()
            self._loaded_from = "cache"
            self._loaded_at = datetime.utcnow()
            logger.info("从本地缓存加载模型能力配置成功")
            return self._loaded_from
        except Exception as e:
            logger.warning(f"本地缓存加载失败: {e}")

        # 第 3 层：使用硬编码兜底
        self._caps = self._load_fallback()
        self._loaded_from = "fallback"
        self._loaded_at = datetime.utcnow()
        logger.info("使用硬编码兜底数据")
        return self._loaded_from

    async def _fetch_from_github(self) -> dict:
        """从 GitHub 拉取最新配置"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(CAPS_URL, timeout=10)
            resp.raise_for_status()
            return resp.json()

    def _validate_schema(self, data: dict) -> bool:
        """验证 schema 版本"""
        return data.get("schema_version") == SCHEMA_VERSION

    def _save_to_cache(self, data: dict):
        """保存到本地缓存"""
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def _load_from_cache(self) -> dict:
        """从本地缓存加载"""
        if not CACHE_FILE.exists():
            raise FileNotFoundError("缓存文件不存在")

        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))

        # 检查 schema 版本
        if not self._validate_schema(data):
            raise ValueError(f"Schema 版本不兼容: {data.get('schema_version')}")

        # 检查是否过期
        updated_str = data.get("updated_at", "")
        if updated_str:
            updated = datetime.fromisoformat(updated_str.rstrip("Z"))
            if datetime.utcnow() - updated > CACHE_TTL:
                raise ValueError("缓存已过期")

        return data

    def _load_fallback(self) -> dict:
        """加载硬编码兜底数据"""
        if FALLBACK_FILE.exists():
            return json.loads(FALLBACK_FILE.read_text(encoding="utf-8"))

        # 如果兜底文件也不存在，返回最小可用数据
        return {
            "schema_version": 1,
            "updated_at": "2026-01-01T00:00:00Z",
            "source": "hardcoded-minimal",
            "capabilities": {
                "vision": {
                    "allowed_patterns": ["gpt-4o", "claude-3", "gemini", "o1", "o3"],
                    "excluded_patterns": ["o1-mini", "o3-mini"]
                },
                "tooluse": {
                    "allowed_patterns": ["gpt-4o", "gpt-4", "claude", "deepseek", "gemini"],
                    "excluded_patterns": ["o1-mini"]
                },
                "embedding": {
                    "embedding_regex": "(?i)(?:text-embedding|embed|bge-|e5-|gte-|voyage-)",
                    "rerank_regex": "(?i)(?:rerank|re-rank)"
                }
            }
        }

    def is_vision_model(self, model_id: str) -> bool:
        """
        判断是否为视觉模型

        Args:
            model_id: 模型 ID (如 "gpt-4o", "claude-sonnet-4")

        Returns:
            bool: 是否支持视觉输入
        """
        if not self._caps:
            return False

        vision = self._caps["capabilities"].get("vision", {})
        allowed = vision.get("allowed_patterns", [])
        excluded = vision.get("excluded_patterns", [])

        # 检查排除列表
        for pattern in excluded:
            try:
                if re.search(pattern, model_id, re.IGNORECASE):
                    return False
            except re.error:
                continue

        # 检查允许列表
        for pattern in allowed:
            try:
                if re.search(pattern, model_id, re.IGNORECASE):
                    return True
            except re.error:
                continue

        return False

    def is_tool_model(self, model_id: str) -> bool:
        """
        判断是否支持工具调用

        Args:
            model_id: 模型 ID

        Returns:
            bool: 是否支持工具调用
        """
        if not self._caps:
            return False

        tooluse = self._caps["capabilities"].get("tooluse", {})
        allowed = tooluse.get("allowed_patterns", [])
        excluded = tooluse.get("excluded_patterns", [])

        # 检查排除列表
        for pattern in excluded:
            try:
                if re.search(pattern, model_id, re.IGNORECASE):
                    return False
            except re.error:
                continue

        # 检查允许列表
        for pattern in allowed:
            try:
                if re.search(pattern, model_id, re.IGNORECASE):
                    return True
            except re.error:
                continue

        return False

    def is_embedding_model(self, model_id: str) -> bool:
        """
        判断是否为嵌入模型

        Args:
            model_id: 模型 ID

        Returns:
            bool: 是否为嵌入模型
        """
        if not self._caps:
            return False

        regex = self._caps["capabilities"]["embedding"].get("embedding_regex")
        if regex:
            try:
                return bool(re.search(regex, model_id, re.IGNORECASE))
            except re.error:
                return False
        return False

    def is_rerank_model(self, model_id: str) -> bool:
        """
        判断是否为重排模型

        Args:
            model_id: 模型 ID

        Returns:
            bool: 是否为重排模型
        """
        if not self._caps:
            return False

        regex = self._caps["capabilities"]["embedding"].get("rerank_regex")
        if regex:
            try:
                return bool(re.search(regex, model_id, re.IGNORECASE))
            except re.error:
                return False
        return False

    def is_reasoning_model(self, model_id: str) -> bool:
        """
        判断是否为推理模型

        Args:
            model_id: 模型 ID

        Returns:
            bool: 是否为推理模型
        """
        if not self._caps:
            return False

        # 从配置中获取推理模型列表
        reasoning = self._caps["capabilities"].get('reasoning', {})
        allowed = reasoning.get('allowed_patterns', [])
        excluded = reasoning.get('excluded_patterns', [])

        # 检查排除列表
        for pattern in excluded:
            try:
                if re.search(pattern, model_id, re.IGNORECASE):
                    return False
            except re.error:
                continue

        # 检查允许列表
        for pattern in allowed:
            try:
                if re.search(pattern, model_id, re.IGNORECASE):
                    return True
            except re.error:
                continue

        return False

    def is_websearch_model(self, model_id: str) -> bool:
        """
        判断是否为联网搜索模型

        Args:
            model_id: 模型 ID

        Returns:
            bool: 是否支持联网搜索
        """
        if not self._caps:
            return False

        # 从配置中获取联网模型列表
        websearch = self._caps["capabilities"].get('websearch', {})
        allowed = websearch.get('allowed_patterns', [])
        excluded = websearch.get('excluded_patterns', [])

        # 检查排除列表
        for pattern in excluded:
            try:
                if re.search(pattern, model_id, re.IGNORECASE):
                    return False
            except re.error:
                continue

        # 检查允许列表
        for pattern in allowed:
            try:
                if re.search(pattern, model_id, re.IGNORECASE):
                    return True
            except re.error:
                continue

        return False

    def is_free_model(self, model_id: str) -> bool:
        """
        判断是否为免费模型

        Args:
            model_id: 模型 ID

        Returns:
            bool: 是否为免费模型
        """
        if not self._caps:
            return False

        # 从配置中获取免费模型列表
        free = self._caps["capabilities"].get('free', {})
        allowed = free.get('allowed_patterns', [])

        # 检查允许列表
        for pattern in allowed:
            try:
                if re.search(pattern, model_id, re.IGNORECASE):
                    return True
            except re.error:
                continue

        return False

    def get_model_capabilities(self, model_id: str) -> dict[str, bool]:
        """
        获取模型的所有能力

        Args:
            model_id: 模型 ID

        Returns:
            dict: 能力字典
        """
        return {
            "vision": self.is_vision_model(model_id),
            "tooluse": self.is_tool_model(model_id),
            "embedding": self.is_embedding_model(model_id),
            "rerank": self.is_rerank_model(model_id),
            "reasoning": self.is_reasoning_model(model_id),
            "websearch": self.is_websearch_model(model_id),
            "free": self.is_free_model(model_id),
        }

    @property
    def loaded_from(self) -> str | None:
        """数据来源: github / cache / fallback"""
        return self._loaded_from

    @property
    def is_loaded(self) -> bool:
        """是否已加载"""
        return self._caps is not None

    @property
    def updated_at(self) -> str | None:
        """数据更新时间"""
        if self._caps:
            return self._caps.get("updated_at")
        return None


# 全局单例
detector = ModelCapabilityDetector()

"""
从 Cherry Studio 的 JSON 数据中提取模型能力，生成 Python 硬编码文件。

Cherry Studio 新路径:
packages/provider-registry/data/models.json

用法: python scripts/extract_model_caps.py
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime, timezone

# 新路径：JSON 数据文件
CHERRY_DATA_DIR = Path(os.environ.get("CHERRY_DATA_DIR", "cherry-studio/packages/provider-registry/data"))
MODELS_FILE = CHERRY_DATA_DIR / "models.json"
OUTPUT_FILE = Path("data/model_capabilities.json")
SCHEMA_VERSION = 1

# Cherry Studio capabilities 映射到我们的能力类型
CAPABILITY_MAP = {
    "vision": ["image-recognition", "video-recognition"],
    "tooluse": ["function-call"],
    "reasoning": ["reasoning"],
    "websearch": ["web-search"],
    "embedding": ["embedding"],
}


def extract_capabilities_from_json(file_path: Path) -> dict:
    """从 JSON 文件提取模型能力"""
    if not file_path.exists():
        print(f"Error: {file_path} not found")
        return {}

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    models = data.get("models", [])

    # 收集每种能力的模型 ID
    capability_models = {
        "vision": [],
        "tooluse": [],
        "reasoning": [],
        "websearch": [],
        "embedding": [],
    }

    for model in models:
        model_id = model.get("id", "")
        capabilities = model.get("capabilities", [])
        input_modalities = model.get("inputModalities", [])
        pricing = model.get("pricing", {})

        # 视觉：有 image-recognition 或 video-recognition 能力，或者输入包含 image/video
        if ("image-recognition" in capabilities or
            "video-recognition" in capabilities or
            "image" in input_modalities or
            "video" in input_modalities):
            capability_models["vision"].append(model_id)

        # 工具调用：有 function-call 能力
        if "function-call" in capabilities:
            capability_models["tooluse"].append(model_id)

        # 推理：有 reasoning 能力
        if "reasoning" in capabilities:
            capability_models["reasoning"].append(model_id)

        # 联网：有 web-search 能力
        if "web-search" in capabilities:
            capability_models["websearch"].append(model_id)

        # 嵌入：有 embedding 能力
        if "embedding" in capabilities:
            capability_models["embedding"].append(model_id)

    return capability_models


def main():
    print("Extracting model capabilities from Cherry Studio JSON...")
    print(f"Source: {MODELS_FILE}")

    if not MODELS_FILE.exists():
        print(f"Error: {MODELS_FILE} not found!")
        print("Please run the cherry-studio checkout first.")
        return 1

    capability_models = extract_capabilities_from_json(MODELS_FILE)

    # 统计
    total = sum(len(v) for v in capability_models.values())
    print(f"Extracted {total} capability entries from {len(capability_models)} categories")

    for cap_name, models in capability_models.items():
        print(f"  {cap_name}: {len(models)} models")

    # 生成输出
    timestamp = datetime.now(timezone.utc).isoformat()
    output = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": timestamp,
        "source": "https://github.com/CherryHQ/cherry-studio",
        "capabilities": {}
    }

    # 转换为正则匹配格式（精确匹配模型 ID）
    for cap_name, models in capability_models.items():
        if models:
            # 创建精确匹配的正则列表
            patterns = [re.escape(m) for m in models]
            output["capabilities"][cap_name] = {
                "allowed_patterns": patterns,
                "excluded_patterns": []
            }

    # 写入文件
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nOutput: {OUTPUT_FILE}")
    print(f"Schema version: {SCHEMA_VERSION}")
    print(f"Capabilities: {list(output['capabilities'].keys())}")

    return 0


if __name__ == "__main__":
    exit(main())

"""
从 Cherry Studio 的 TypeScript 源码中提取模型能力正则，
转译为 Python 可用的 JSON 格式。

用法: python scripts/extract_model_caps.py
"""

import json
import re
from pathlib import Path
from datetime import datetime

# 配置
CHERRY_MODELS_DIR = Path("cherry-studio/src/renderer/src/config/models")
OUTPUT_FILE = Path("data/model_capabilities.json")
SCHEMA_VERSION = 1


def extract_array_with_regex(content: str, var_name: str) -> list[str]:
    """使用正则从 TypeScript 源码中提取字符串数组"""
    # 匹配多种格式的数组定义
    patterns = [
        # export const VAR = ['str1', 'str2', ...]
        rf"(?:export\s+)?const\s+{var_name}\s*=\s*\[(.*?)\]",
        # const VAR: readonly [...] = [...]
        rf"(?:export\s+)?const\s+{var_name}\s*(?::\s*[^=]+)?\s*=\s*\[(.*?)\]",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            # 提取引号内的字符串（单引号和双引号）
            items = re.findall(r"'([^']*)'|\"([^\"]*)\"", match.group(1))
            return [a or b for a, b in items if (a or b)]
    
    return []


def extract_regex_pattern(content: str, var_name: str) -> str | None:
    """提取单个正则表达式"""
    # 匹配: const VAR = /pattern/i 或 new RegExp('pattern', 'i')
    patterns = [
        rf"(?:export\s+)?const\s+{var_name}\s*=\s*(/[^\n]+)",
        rf"(?:export\s+)?const\s+{var_name}\s*=\s*new\s+RegExp\(['\"]([^'\"]+)['\"](?:,\s*['\"]([^'\"]+)['\"])?\)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            regex_str = match.group(1)
            
            # 处理 /pattern/i 格式
            if regex_str.startswith('/'):
                # 提取正则内容和标志
                last_slash = regex_str.rfind('/')
                if last_slash > 0:
                    body = regex_str[1:last_slash]
                    flags = regex_str[last_slash + 1:]
                    if 'i' in flags:
                        return f"(?i){body}"
                    return body
            
            # 处理 new RegExp 格式
            return regex_str
    
    return None


def process_vision(content: str) -> dict:
    """处理 vision.ts"""
    return {
        "allowed_patterns": extract_array_with_regex(content, "visionAllowedModels"),
        "excluded_patterns": extract_array_with_regex(content, "visionExcludedModels")
    }


def process_tooluse(content: str) -> dict:
    """处理 tooluse.ts"""
    return {
        "allowed_patterns": extract_array_with_regex(content, "FUNCTION_CALLING_MODELS"),
        "excluded_patterns": extract_array_with_regex(content, "FUNCTION_CALLING_EXCLUDED_MODELS")
    }


def process_embedding(content: str) -> dict:
    """处理 embedding.ts"""
    return {
        "embedding_regex": extract_regex_pattern(content, "EMBEDDING_REGEX"),
        "rerank_regex": extract_regex_pattern(content, "RERANKING_REGEX")
    }


def main():
    print(f"Extracting model capabilities from Cherry Studio...")
    print(f"Source: {CHERRY_MODELS_DIR}")
    
    if not CHERRY_MODELS_DIR.exists():
        print(f"Error: {CHERRY_MODELS_DIR} not found!")
        print("Please run: git clone --depth 1 --sparse https://github.com/CherryHQ/cherry-studio.git cherry-studio")
        print("Then: cd cherry-studio && git sparse-checkout set src/renderer/src/config/models")
        return 1
    
    result = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "source": "https://github.com/CherryHQ/cherry-studio",
        "capabilities": {}
    }
    
    # 处理各文件
    processors = {
        "vision": ("vision.ts", process_vision),
        "tooluse": ("tooluse.ts", process_tooluse),
        "embedding": ("embedding.ts", process_embedding),
    }
    
    success_count = 0
    for cap_name, (filename, processor) in processors.items():
        filepath = CHERRY_MODELS_DIR / filename
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8")
            result["capabilities"][cap_name] = processor(content)
            
            # 统计提取结果
            cap_data = result["capabilities"][cap_name]
            if "allowed_patterns" in cap_data:
                print(f"  ✓ {cap_name}: {len(cap_data['allowed_patterns'])} allowed, "
                      f"{len(cap_data.get('excluded_patterns', []))} excluded")
            elif "embedding_regex" in cap_data:
                print(f"  ✓ {cap_name}: embedding={bool(cap_data['embedding_regex'])}, "
                      f"rerank={bool(cap_data['rerank_regex'])}")
            success_count += 1
        else:
            print(f"  ✗ {cap_name}: {filename} not found")
    
    if success_count == 0:
        print("Error: No capabilities extracted!")
        return 1
    
    # 输出
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nOutput: {OUTPUT_FILE}")
    print(f"Schema version: {SCHEMA_VERSION}")
    print(f"Capabilities: {list(result['capabilities'].keys())}")
    
    return 0


if __name__ == "__main__":
    exit(main())

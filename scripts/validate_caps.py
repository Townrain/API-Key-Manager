"""
验证提取的模型能力正则是否正确。

用法: python scripts/validate_caps.py
"""

import json
import re
import sys
from pathlib import Path

CAPS_FILE = Path("data/model_capabilities.json")
FALLBACK_FILE = Path("data/model_capabilities_fallback.json")

# 测试用例: (模型ID, 能力类型, 预期结果)
TEST_CASES = [
    # 视觉模型 - 应该匹配
    ("gpt-4o", "vision", True),
    ("gpt-4o-mini", "vision", True),
    ("gpt-5", "vision", True),
    ("gpt-5-5", "vision", True),
    ("gpt-5", "vision", True),
    ("claude-3-opus", "vision", True),
    ("claude-sonnet-4", "vision", True),
    ("gemini-2-5-flash", "vision", True),
    ("gemini-3-pro", "vision", True),
    ("qwen2-5-vl-instruct", "vision", True),
    ("o1", "vision", True),
    ("o3", "vision", True),
    ("o4-mini", "vision", True),
    
    # 视觉模型 - 应该排除
    ("o1-mini", "vision", False),
    ("o1-preview", "vision", False),
    ("gpt-4-32k", "vision", False),
    
    # 视觉模型 - 不应该匹配
    ("text-embedding-3-small", "vision", False),
    
    # 工具调用 - 应该匹配
    ("gpt-4o", "tooluse", True),
    ("gpt-4", "tooluse", True),
    ("gpt-5", "tooluse", True),
    ("claude-3-opus", "tooluse", True),
    ("claude-sonnet-4", "tooluse", True),
    ("deepseek-chat", "tooluse", True),
    ("qwen-max", "tooluse", True),
    ("gemini-2-5-flash", "tooluse", True),
    ("deepseek-r1", "tooluse", True),
    ("o3-mini", "tooluse", True),
    
    # 工具调用 - 应该排除
    ("o1-mini", "tooluse", False),
    ("o1-preview", "tooluse", False),
    # 工具调用 - 不应该匹配
    ("text-embedding-3-small", "tooluse", False),
    
    # 嵌入模型 - 应该匹配
    ("text-embedding-3-small", "embedding", True),
    ("text-embedding-3-large", "embedding", True),
    ("bge-large-zh", "embedding", True),
    ("bge-m3", "embedding", True),
    ("gte-large", "embedding", True),
    
    # 嵌入模型 - 不应该匹配
    ("gpt-4o", "embedding", False),
    ("claude-3-opus", "embedding", False),
    ("deepseek-chat", "embedding", False),
    
    # 重排模型 - 应该匹配
    ("bge-reranker-v2-m3", "rerank", True),
    ("qwen3-reranker", "rerank", True),
    
    # 重排模型 - 不应该匹配
    ("gpt-4o", "rerank", False),
    ("text-embedding-3-small", "rerank", False),
]


def validate_caps(caps: dict, source: str) -> tuple[int, int]:
    """验证能力配置"""
    passed = 0
    failed = 0
    
    for model_id, cap_type, expected in TEST_CASES:
        result = None
        
        if cap_type == "vision":
            vision = caps["capabilities"].get("vision", {})
            allowed = vision.get("allowed_patterns", [])
            excluded = vision.get("excluded_patterns", [])
            
            is_excluded = any(re.search(p, model_id, re.IGNORECASE) for p in excluded)
            is_allowed = any(re.search(p, model_id, re.IGNORECASE) for p in allowed)
            result = is_allowed and not is_excluded
            
        elif cap_type == "tooluse":
            tooluse = caps["capabilities"].get("tooluse", {})
            allowed = tooluse.get("allowed_patterns", [])
            excluded = tooluse.get("excluded_patterns", [])
            
            is_excluded = any(re.search(p, model_id, re.IGNORECASE) for p in excluded)
            is_allowed = any(re.search(p, model_id, re.IGNORECASE) for p in allowed)
            result = is_allowed and not is_excluded
            
        elif cap_type == "embedding":
            regex = caps["capabilities"]["embedding"].get("embedding_regex")
            if regex:
                result = bool(re.search(regex, model_id, re.IGNORECASE))
            else:
                result = False
                
        elif cap_type == "rerank":
            regex = caps["capabilities"]["embedding"].get("rerank_regex")
            if regex:
                result = bool(re.search(regex, model_id, re.IGNORECASE))
            else:
                result = False
        
        if result == expected:
            passed += 1
        else:
            failed += 1
            print(f"  FAIL {model_id}: {cap_type} expected={expected}, got={result}")
    
    return passed, failed


def main():
    print("=" * 60)
    print("Model Capabilities Validation")
    print("=" * 60)
    
    total_passed = 0
    total_failed = 0
    
    # 验证主配置文件
    if CAPS_FILE.exists():
        print(f"\nValidating {CAPS_FILE}...")
        caps = json.loads(CAPS_FILE.read_text(encoding="utf-8"))
        
        # 检查 schema 版本
        if caps.get("schema_version") != 1:
            print(f"  Warning: schema_version={caps.get('schema_version')}, expected=1")
        
        passed, failed = validate_caps(caps, "main")
        total_passed += passed
        total_failed += failed
        print(f"  Results: {passed} passed, {failed} failed")
    else:
        print(f"\n{CAPS_FILE} not found, skipping...")
    
    # 验证兜底配置文件
    if FALLBACK_FILE.exists():
        print(f"\nValidating {FALLBACK_FILE}...")
        fallback = json.loads(FALLBACK_FILE.read_text(encoding="utf-8"))
        
        if fallback.get("schema_version") != 1:
            print(f"  Warning: schema_version={fallback.get('schema_version')}, expected=1")
        
        passed, failed = validate_caps(fallback, "fallback")
        print(f"  Results: {passed} passed, {failed} failed")
    else:
        print(f"\n{FALLBACK_FILE} not found, skipping...")
    
    # 总结
    print("\n" + "=" * 60)
    print(f"Total: {total_passed} passed, {total_failed} failed")
    print("=" * 60)
    
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
合同审查前的保密与敏感信息预检。

本脚本不调用任何外部 API，只基于本地正则和关键词扫描，输出 JSON 供
SKILL.md 决定是否提示用户选择直接审查、脱敏审查或取消。
"""

import argparse
import json
import re
from pathlib import Path


PATTERNS = {
    "身份证号": re.compile(r"(?<![0-9A-Za-z])[1-9]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?![0-9A-Za-z])"),
    "手机号": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "邮箱": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "银行卡号": re.compile(r"(?<!\d)(?:\d[ -]?){16,19}(?!\d)"),
    "统一社会信用代码": re.compile(r"\b[0-9A-Z]{18}\b"),
    "金额": re.compile(r"(?:人民币|RMB|¥)\s*[\[\]【】●*0-9,.，万亿元]+"),
}

SENSITIVE_KEYWORDS = {
    "融资/股权": ["股东协议", "增资协议", "投资协议", "清算优先权", "回购", "估值", "领售", "反稀释", "投后"],
    "商业秘密": ["商业秘密", "技术秘密", "源代码", "客户名单", "供应商名单", "财务数据", "经营数据", "商业计划"],
    "个人信息": ["个人信息", "敏感个人信息", "身份证", "手机号", "住址", "员工信息", "用户数据"],
    "跨境数据": ["跨境传输", "境外接收方", "标准合同", "SCC", "安全评估", "数据出境"],
    "监管/合规": ["反洗钱", "反腐败", "反商业贿赂", "出口管制", "数据安全", "等保"],
}


def count_pattern(pattern: re.Pattern, text: str) -> int:
    return len(pattern.findall(text))


def scan_text(text: str) -> dict:
    sensitive_items = []
    score = 0

    id_matches = set(PATTERNS["身份证号"].findall(text))
    for label, pattern in PATTERNS.items():
        if label == "银行卡号":
            matches = [m for m in pattern.findall(text) if re.sub(r"\D", "", m) not in id_matches]
            count = len(matches)
        else:
            count = count_pattern(pattern, text)
        if count:
            sensitive_items.append({"type": label, "count": count})
            score += min(count, 5) * (3 if label in ["身份证号", "银行卡号"] else 1)

    keyword_hits = []
    for category, keywords in SENSITIVE_KEYWORDS.items():
        hits = [kw for kw in keywords if kw in text]
        if hits:
            keyword_hits.append({"category": category, "keywords": hits[:12], "count": len(hits)})
            score += len(hits)

    if any(item["type"] in ["身份证号", "银行卡号"] for item in sensitive_items):
        level = "HIGH"
    elif score >= 8:
        level = "HIGH"
    elif score >= 3:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "confidentiality_level": level,
        "sensitive_items": sensitive_items,
        "keyword_hits": keyword_hits,
        "requires_user_confirmation": level in ["HIGH", "MEDIUM"],
        "recommended_mode": "redacted_review" if level == "HIGH" else "direct_review",
        "message": build_message(level, sensitive_items, keyword_hits),
    }


def build_message(level: str, sensitive_items: list, keyword_hits: list) -> str:
    if level == "LOW":
        return "未检测到明显高敏信息，可继续审查。"
    item_text = "、".join(f"{item['type']}({item['count']})" for item in sensitive_items) or "无明确正则命中"
    keyword_text = "、".join(item["category"] for item in keyword_hits) or "无关键词命中"
    return f"检测到{level}级敏感信息：{item_text}；敏感类别：{keyword_text}。建议用户确认是否脱敏后审查。"


def main():
    parser = argparse.ArgumentParser(description="合同保密与敏感信息预检")
    parser.add_argument("--contract", required=True, help="合同文本路径")
    args = parser.parse_args()

    text = Path(args.contract).expanduser().read_text(encoding="utf-8")
    print(json.dumps(scan_text(text), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

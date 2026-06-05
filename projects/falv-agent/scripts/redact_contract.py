#!/usr/bin/env python3
"""
合同文本本地脱敏工具。

输出：
- 脱敏后的合同文本
- 本地映射表 JSON（敏感文件，不应提交 Git）
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path


REDACTION_RULES = [
    ("身份证号", re.compile(r"(?<![0-9A-Za-z])[1-9]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?![0-9A-Za-z])"), "[身份证号_{n}]"),
    ("手机号", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "[手机号_{n}]"),
    ("邮箱", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[邮箱_{n}]"),
    ("统一社会信用代码", re.compile(r"\b[0-9A-Z]{18}\b"), "[统一社会信用代码_{n}]"),
    ("金额", re.compile(r"(?:人民币|RMB|¥)\s*[\[\]【】●*0-9,.，万亿元]+"), "人民币[金额_{n}]"),
    ("公司名称", re.compile(r"[\u4e00-\u9fa5A-Za-z0-9（）()·]{2,60}(?:有限公司|股份有限公司|有限合伙企业|合伙企业|集团|基金)"), "公司_{n}"),
]


def redact(text: str) -> tuple[str, list]:
    mappings = []
    redacted = text
    counters = {}

    for label, pattern, replacement_template in REDACTION_RULES:
        counters[label] = 0
        seen = {}

        def repl(match):
            original = match.group(0)
            if original not in seen:
                counters[label] += 1
                replacement = replacement_template.format(n=counters[label])
                seen[original] = replacement
                mappings.append({"type": label, "placeholder": replacement, "original": original})
            return seen[original]

        redacted = pattern.sub(repl, redacted)

    return redacted, mappings


def main():
    parser = argparse.ArgumentParser(description="合同文本本地脱敏")
    parser.add_argument("--contract", required=True, help="原始合同文本路径")
    parser.add_argument("--output", required=True, help="脱敏文本输出路径")
    parser.add_argument("--map", required=True, help="脱敏映射表输出路径")
    args = parser.parse_args()

    contract_path = Path(args.contract).expanduser()
    output_path = Path(args.output).expanduser()
    map_path = Path(args.map).expanduser()

    text = contract_path.read_text(encoding="utf-8")
    redacted, mappings = redact(text)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(redacted, encoding="utf-8")
    map_path.write_text(json.dumps({
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source": str(contract_path),
        "redacted_output": str(output_path),
        "mappings": mappings,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "redacted_file": str(output_path),
        "map_file": str(map_path),
        "mapping_count": len(mappings),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

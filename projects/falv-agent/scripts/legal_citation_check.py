#!/usr/bin/env python3
"""
结构化法条知识库校验器。

职责：
- 抽取文本中的《法律名称》第X条引用
- 检查废止法、是否本地库命中、是否过期、上下文主题是否弱匹配
- 输出可写入报告的结构化 warnings
"""

import argparse
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = ROOT / "legal_knowledge"
CITATION_RE = re.compile(r"《([^》]+)》第([一二三四五六七八九十百千万零〇两]+)条")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_law(name: str) -> str:
    return re.sub(r"^中华人民共和国", "", name or "").strip()


def normalize_article(raw: str) -> str:
    return f"第{raw}条"


def load_knowledge() -> tuple[dict, dict]:
    citations_data = load_json(KNOWLEDGE_DIR / "citations.json")
    deprecated_data = load_json(KNOWLEDGE_DIR / "deprecated_map.json")
    index = {}
    for item in citations_data.get("citations", []):
        key = (normalize_law(item.get("law", "")), item.get("article", ""))
        index[key] = item
    return index, deprecated_data.get("deprecated_laws", {})


def extract_text_from_json(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(extract_text_from_json(v) for v in value.values())
    if isinstance(value, list):
        return "\n".join(extract_text_from_json(v) for v in value)
    return str(value) if value is not None else ""


def days_since(iso_date: str) -> Optional[int]:
    try:
        parsed = datetime.strptime(iso_date, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    return (date.today() - parsed).days


def local_context(text: str, start: int, end: int, radius: int = 80) -> str:
    return text[max(0, start - radius):min(len(text), end + radius)]


def topic_match(citation: dict, context: str) -> bool:
    keywords = citation.get("keywords", []) + citation.get("scenarios", [])
    if not keywords:
        return True
    return any(keyword and keyword in context for keyword in keywords)


def check_text(text: str) -> dict:
    citation_index, deprecated = load_knowledge()
    findings = []
    seen = set()

    for match in CITATION_RE.finditer(text):
        law = normalize_law(match.group(1))
        article = normalize_article(match.group(2))
        citation_text = match.group(0)
        dedupe_key = (law, article, match.start())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        if law in deprecated:
            info = deprecated[law]
            findings.append({
                "citation": citation_text,
                "law": law,
                "article": article,
                "status": "deprecated",
                "level": "error",
                "message": info.get("message", f"《{law}》已废止或不应引用。"),
                "replaced_by": info.get("replaced_by", ""),
            })
            continue

        item = citation_index.get((law, article))
        if not item:
            findings.append({
                "citation": citation_text,
                "law": law,
                "article": article,
                "status": "unknown",
                "level": "warning",
                "message": "本地结构化法条库未收录该条文，需人工复核；不视为已确认现行有效。",
            })
            continue

        age = days_since(item.get("last_verified_at"))
        cycle = int(item.get("verification_cycle_days") or 90)
        context = local_context(text, match.start(), match.end())
        is_topic_match = topic_match(item, context)
        status = "current"
        level = "info"
        message = "本地结构化法条库命中，且在校验周期内。"

        if age is None or age > cycle:
            status = "stale"
            level = "warning"
            message = "本地结构化法条库命中，但已超过校验周期，建议复核现行有效版本。"
        elif not is_topic_match:
            status = "topic_mismatch"
            level = "warning"
            message = "条文已收录且未过期，但上下文关键词弱匹配，建议人工复核适用性。"

        findings.append({
            "citation": citation_text,
            "law": law,
            "article": article,
            "status": status,
            "level": level,
            "message": message,
            "knowledge_id": item.get("id", ""),
            "title": item.get("title", ""),
            "last_verified_at": item.get("last_verified_at", ""),
            "verification_cycle_days": cycle,
            "source_name": item.get("source_name", ""),
            "source_url": item.get("source_url", ""),
        })

    summary = {"current": 0, "stale": 0, "unknown": 0, "deprecated": 0, "topic_mismatch": 0}
    for item in findings:
        if item["status"] in summary:
            summary[item["status"]] += 1

    return {
        "summary": summary,
        "findings": findings,
        "knowledge_base": {
            "path": str(KNOWLEDGE_DIR / "citations.json"),
            "checked_at": date.today().isoformat(),
            "upstreams": ["国家法律法规数据库", "北大法宝"],
        },
    }


def main():
    parser = argparse.ArgumentParser(description="检查文本或 JSON 中的法条引用")
    parser.add_argument("--input", required=True, help="待检查文件路径（txt/md/json）")
    parser.add_argument("--output", help="输出 JSON 路径；省略则打印到 stdout")
    args = parser.parse_args()

    path = Path(args.input).expanduser()
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        text = extract_text_from_json(json.loads(raw))
    else:
        text = raw
    result = check_text(text)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).expanduser().write_text(payload, encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()

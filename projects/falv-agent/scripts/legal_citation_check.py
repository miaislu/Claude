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

try:
    from pkulaw_mcp_client import PkulawMcpError, get_law_item_content, summarize_law_item_response
except ImportError:
    PkulawMcpError = RuntimeError
    get_law_item_content = None
    summarize_law_item_response = None


ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = ROOT / "legal_knowledge"
CITATION_RE = re.compile(r"《([^》]+)》第([一二三四五六七八九十百千万零〇两]+)条")
CHINESE_NUMERALS = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}
CHINESE_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10000}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_law(name: str) -> str:
    return re.sub(r"^中华人民共和国", "", name or "").strip()


def normalize_article(raw: str) -> str:
    return f"第{raw}条"


def chinese_article_to_number(raw: str) -> Optional[int]:
    total = 0
    section = 0
    number = 0
    for char in raw:
        if char in CHINESE_NUMERALS:
            number = CHINESE_NUMERALS[char]
        elif char in CHINESE_UNITS:
            unit = CHINESE_UNITS[char]
            if unit == 10000:
                section = (section + number) * unit
                total += section
                section = 0
            else:
                section += (number or 1) * unit
            number = 0
        else:
            return None
    return total + section + number


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


PKULAW_POLICIES = {"local", "on-demand", "always"}


def pkulaw_verify_law_item(law: str, raw_article: str) -> dict:
    if get_law_item_content is None:
        return {"status": "unavailable", "message": "未加载 pkulaw_mcp_client。"}
    article_number = chinese_article_to_number(raw_article)
    if article_number is None:
        return {"status": "unavailable", "message": f"无法解析中文条号：{raw_article}"}
    try:
        result = get_law_item_content(law, article_number)
    except PkulawMcpError as exc:
        return {"status": "error", "message": str(exc)}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
    return {
        "status": "verified",
        "source_name": "北大法宝 MCP",
        "tool": "get_law_item_content",
        "query": {"title": law, "tiao_num": article_number},
        "summary": summarize_law_item_response(result) if summarize_law_item_response else {},
    }


def is_major_context(context: str) -> bool:
    return any(token in context for token in [
        "重大风险", "高度风险", "高危", "必须修改", "must_fix", "行政处罚",
        "合同无效", "不得实施集中", "个人信息", "数据出境", "无限责任",
    ])


def should_use_pkulaw(policy: str, status: str, major_context: bool = False) -> bool:
    if policy == "always":
        return True
    if policy == "on-demand":
        return status in ["unknown", "stale", "topic_mismatch"] or major_context
    return False


def check_text(text: str, use_pkulaw: bool = False, pkulaw_policy: str = "local") -> dict:
    if use_pkulaw:
        pkulaw_policy = "on-demand"
    if pkulaw_policy not in PKULAW_POLICIES:
        raise ValueError(f"不支持的北大法宝校验策略：{pkulaw_policy}")

    citation_index, deprecated = load_knowledge()
    findings = []
    seen = set()

    for match in CITATION_RE.finditer(text):
        law = normalize_law(match.group(1))
        raw_article = match.group(2)
        article = normalize_article(raw_article)
        citation_text = match.group(0)
        dedupe_key = (law, article, match.start())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        context = local_context(text, match.start(), match.end())
        major_context = is_major_context(context)

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
            finding = {
                "citation": citation_text,
                "law": law,
                "article": article,
                "status": "unknown",
                "level": "warning",
                "message": "本地结构化法条库未收录该条文，需人工复核；不视为已确认现行有效。",
            }
            if should_use_pkulaw(pkulaw_policy, "unknown", major_context):
                finding["upstream_check"] = pkulaw_verify_law_item(law, raw_article)
                finding["upstream_reason"] = "policy_on_demand_unknown_or_major"
            findings.append(finding)
            continue

        age = days_since(item.get("last_verified_at"))
        cycle = int(item.get("verification_cycle_days") or 90)
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

        finding = {
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
        }
        if should_use_pkulaw(pkulaw_policy, status, major_context):
            finding["upstream_check"] = pkulaw_verify_law_item(law, raw_article)
            finding["upstream_reason"] = (
                "policy_always"
                if pkulaw_policy == "always"
                else "policy_on_demand_stale_topic_or_major"
            )
        findings.append(finding)

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
            "pkulaw_policy": pkulaw_policy,
            "pkulaw_mcp_enabled": pkulaw_policy != "local",
        },
    }


def main():
    parser = argparse.ArgumentParser(description="检查文本或 JSON 中的法条引用")
    parser.add_argument("--input", required=True, help="待检查文件路径（txt/md/json）")
    parser.add_argument("--output", help="输出 JSON 路径；省略则打印到 stdout")
    parser.add_argument("--use-pkulaw", action="store_true", help="对 unknown/stale/topic_mismatch 条文调用北大法宝 MCP 做上游核验")
    parser.add_argument("--pkulaw-policy", choices=sorted(PKULAW_POLICIES), default="local",
                        help="北大法宝校验策略：local=只查本地；on-demand=仅 unknown/stale/topic mismatch/重大上下文查；always=所有引用均查")
    args = parser.parse_args()

    path = Path(args.input).expanduser()
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        text = extract_text_from_json(json.loads(raw))
    else:
        text = raw
    result = check_text(text, use_pkulaw=args.use_pkulaw, pkulaw_policy=args.pkulaw_policy)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).expanduser().write_text(payload, encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()

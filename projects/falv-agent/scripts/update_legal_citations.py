#!/usr/bin/env python3
"""
人工刷新结构化法条知识库的校验元数据。

默认只更新元数据；可显式使用 --from-pkulaw 从北大法宝 MCP 获取上游核验摘要。
"""

import argparse
import json
import re
from datetime import date
from pathlib import Path

try:
    from legal_citation_check import chinese_article_to_number
    from pkulaw_mcp_client import get_law_item_content, summarize_law_item_response
except ImportError:
    chinese_article_to_number = None
    get_law_item_content = None
    summarize_law_item_response = None


ROOT = Path(__file__).resolve().parents[1]
CITATIONS = ROOT / "legal_knowledge" / "citations.json"


def article_number(article: str):
    raw = re.sub(r"^第|条$", "", article or "")
    if raw.isdigit():
        return int(raw)
    if chinese_article_to_number is None:
        raise SystemExit("无法加载中文条号解析器。")
    parsed = chinese_article_to_number(raw)
    if parsed is None:
        raise SystemExit(f"无法解析条号：{article}")
    return parsed


def find_citation(data: dict, citation_id: str) -> dict:
    for item in data.get("citations", []):
        if item.get("id") == citation_id:
            return item
    raise SystemExit(f"未找到法条 id：{citation_id}")


def pkulaw_refresh_payload(item: dict) -> dict:
    if get_law_item_content is None or summarize_law_item_response is None:
        raise SystemExit("无法加载北大法宝 MCP 客户端。")
    result = get_law_item_content(item.get("law", ""), article_number(item.get("article", "")))
    summary = summarize_law_item_response(result)
    timeliness = summary.get("timeliness", {})
    return {
        "source_name": "北大法宝 MCP",
        "source_url": summary.get("url") or "https://mcp.pkulaw.com/",
        "status": "current" if "现行有效" in "".join(timeliness.values()) else item.get("status", "current"),
        "last_verified_at": date.today().isoformat(),
        "upstream_summary": summary,
    }


def main():
    parser = argparse.ArgumentParser(description="刷新法条校验元数据")
    parser.add_argument("--id", required=True, help="citations.json 中的法条 id")
    parser.add_argument("--verified-at", default="", help="校验日期 YYYY-MM-DD；--from-pkulaw 时默认今天")
    parser.add_argument("--source-url", default="", help="本次人工核验的上游来源链接")
    parser.add_argument("--source-name", default="", help="来源名称，默认保留原值")
    parser.add_argument("--status", default="current", help="状态，默认 current")
    parser.add_argument("--from-pkulaw", action="store_true", help="调用北大法宝 MCP 生成刷新元数据")
    parser.add_argument("--dry-run", action="store_true", help="只输出待更新内容，不写入 citations.json")
    args = parser.parse_args()

    data = json.loads(CITATIONS.read_text(encoding="utf-8"))
    item = find_citation(data, args.id)
    before = dict(item)

    if args.from_pkulaw:
        payload = pkulaw_refresh_payload(item)
        verified_at = payload["last_verified_at"]
        source_url = payload["source_url"]
        source_name = payload["source_name"]
        status = payload["status"]
    else:
        if not args.verified_at or not args.source_url:
            raise SystemExit("未使用 --from-pkulaw 时，必须提供 --verified-at 和 --source-url。")
        verified_at = args.verified_at
        source_url = args.source_url
        source_name = args.source_name or item.get("source_name", "")
        status = args.status
        payload = {}

    after = dict(item)
    after["last_verified_at"] = verified_at
    after["source_url"] = source_url
    after["status"] = status
    if source_name:
        after["source_name"] = source_name

    if args.dry_run:
        print(json.dumps({
            "status": "dry_run",
            "id": args.id,
            "before": before,
            "after": after,
            "upstream_summary": payload.get("upstream_summary", {}),
        }, ensure_ascii=False, indent=2))
        return

    item.update(after)
    data["updated_at"] = verified_at
    CITATIONS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "ok",
        "updated_id": args.id,
        "verified_at": verified_at,
        "source_name": source_name,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

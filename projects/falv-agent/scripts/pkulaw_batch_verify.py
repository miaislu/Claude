#!/usr/bin/env python3
"""
批量使用北大法宝 MCP 核验本地 citations.json。

设计边界：
- 只保存元数据和链接，不保存法条全文。
- 默认 dry-run；加 --apply 才写回 citations.json。
- 用 --max-calls 控制免费额度消耗。
"""

import argparse
import json
import re
import time
from datetime import date
from pathlib import Path
from typing import Any

from legal_citation_check import chinese_article_to_number
from pkulaw_mcp_client import PkulawMcpError, get_law_item_content, summarize_law_item_response


ROOT = Path(__file__).resolve().parents[1]
CITATIONS = ROOT / "legal_knowledge" / "citations.json"
AUDIT_DIR = ROOT / "legal_knowledge" / "audits"


def load_citations(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_timeliness(values: dict[str, str]) -> str:
    return "；".join(values.values()) if isinstance(values, dict) else ""


def article_number(article: str) -> int:
    raw = re.sub(r"^第|条$", "", article or "")
    if raw.isdigit():
        return int(raw)
    parsed = chinese_article_to_number(raw)
    if parsed is None:
        raise ValueError(f"无法解析条号：{article}")
    return parsed


def verify_item(item: dict[str, Any]) -> dict[str, Any]:
    result = get_law_item_content(item.get("law", ""), article_number(item.get("article", "")))
    summary = summarize_law_item_response(result)
    timeliness = normalize_timeliness(summary.get("timeliness", {}))
    return {
        "status": "ok" if summary.get("code") == "ok" else "error",
        "message": summary.get("message", ""),
        "law": item.get("law", ""),
        "article": item.get("article", ""),
        "pkulaw_title": summary.get("title", ""),
        "pkulaw_article": summary.get("article", ""),
        "timeliness": timeliness,
        "issue_date": summary.get("issue_date", ""),
        "implement_date": summary.get("implement_date", ""),
        "pkulaw_update_time": summary.get("update_time", ""),
        "pkulaw_url": summary.get("url", ""),
        "verified_at": date.today().isoformat(),
    }


def apply_upstream_check(item: dict[str, Any], check: dict[str, Any]):
    upstream_checks = item.setdefault("upstream_checks", {})
    upstream_checks["pkulaw_mcp"] = {
        "verified_at": check.get("verified_at", ""),
        "status": check.get("status", ""),
        "timeliness": check.get("timeliness", ""),
        "pkulaw_title": check.get("pkulaw_title", ""),
        "pkulaw_article": check.get("pkulaw_article", ""),
        "pkulaw_update_time": check.get("pkulaw_update_time", ""),
        "pkulaw_url": check.get("pkulaw_url", ""),
    }
    if check.get("status") == "ok" and "现行有效" in check.get("timeliness", ""):
        item["status"] = "current"
        item["last_verified_at"] = check.get("verified_at", item.get("last_verified_at", ""))


def main():
    parser = argparse.ArgumentParser(description="批量调用北大法宝 MCP 核验 citations.json")
    parser.add_argument("--citations", default=str(CITATIONS), help="citations.json 路径")
    parser.add_argument("--start", type=int, default=0, help="从第几个 citation 开始，0-based")
    parser.add_argument("--max-calls", type=int, default=20, help="最多调用多少次 MCP")
    parser.add_argument("--sleep", type=float, default=0.1, help="每次调用后的间隔秒数")
    parser.add_argument("--apply", action="store_true", help="写回 citations.json；默认只 dry-run")
    parser.add_argument("--audit-output", default="", help="审计 JSON 输出路径；默认 legal_knowledge/audits/")
    args = parser.parse_args()

    path = Path(args.citations).expanduser()
    data = load_citations(path)
    citations = data.get("citations", [])
    selected = citations[args.start:args.start + args.max_calls]

    results = []
    for offset, item in enumerate(selected):
        index = args.start + offset
        try:
            check = verify_item(item)
        except (PkulawMcpError, SystemExit, Exception) as exc:
            check = {
                "status": "error",
                "message": str(exc),
                "law": item.get("law", ""),
                "article": item.get("article", ""),
                "verified_at": date.today().isoformat(),
            }
        results.append({
            "index": index,
            "id": item.get("id", ""),
            "check": check,
        })
        if args.apply and check.get("status") == "ok":
            apply_upstream_check(item, check)
        time.sleep(args.sleep)

    ok_count = sum(1 for item in results if item["check"].get("status") == "ok")
    error_count = len(results) - ok_count
    audit = {
        "schema_version": "1.0",
        "checked_at": date.today().isoformat(),
        "source": "北大法宝 MCP / mcp-fatiao / get_law_item_content",
        "apply": args.apply,
        "start": args.start,
        "max_calls": args.max_calls,
        "actual_calls": len(results),
        "ok_count": ok_count,
        "error_count": error_count,
        "results": results,
    }

    if args.apply:
        data["updated_at"] = date.today().isoformat()
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.audit_output:
        audit_path = Path(args.audit_output).expanduser()
    else:
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        audit_path = AUDIT_DIR / f"pkulaw_batch_verify_{date.today().isoformat()}.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "apply": args.apply,
        "actual_calls": len(results),
        "ok_count": ok_count,
        "error_count": error_count,
        "audit_output": str(audit_path),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

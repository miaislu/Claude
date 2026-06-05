#!/usr/bin/env python3
"""
人工刷新结构化法条知识库的校验元数据。

第一版只更新元数据，不自动抓取/解释官方全文，避免伪装成自动法律数据库。
"""

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CITATIONS = ROOT / "legal_knowledge" / "citations.json"


def main():
    parser = argparse.ArgumentParser(description="刷新法条校验元数据")
    parser.add_argument("--id", required=True, help="citations.json 中的法条 id")
    parser.add_argument("--verified-at", required=True, help="校验日期 YYYY-MM-DD")
    parser.add_argument("--source-url", required=True, help="本次人工核验的上游来源链接")
    parser.add_argument("--source-name", default="", help="来源名称，默认保留原值")
    parser.add_argument("--status", default="current", help="状态，默认 current")
    args = parser.parse_args()

    data = json.loads(CITATIONS.read_text(encoding="utf-8"))
    found = False
    for item in data.get("citations", []):
        if item.get("id") == args.id:
            item["last_verified_at"] = args.verified_at
            item["source_url"] = args.source_url
            item["status"] = args.status
            if args.source_name:
                item["source_name"] = args.source_name
            found = True
            break

    if not found:
        raise SystemExit(f"未找到法条 id：{args.id}")

    data["updated_at"] = args.verified_at
    CITATIONS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "updated_id": args.id, "verified_at": args.verified_at}, ensure_ascii=False))


if __name__ == "__main__":
    main()

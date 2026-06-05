#!/usr/bin/env python3
"""
合同类型法条覆盖矩阵校验器。

职责：
- 校验 coverage_matrix.json 中引用的 citation id 是否都存在于 citations.json。
- 查询某一合同类型的基础法条覆盖包和条件议题。
- 后续可接入使用日志/人工标注，用于发现矩阵盲区。
"""

import argparse
import json
from pathlib import Path
from typing import Any, Optional


ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = ROOT / "legal_knowledge"
DEFAULT_CITATIONS = KNOWLEDGE_DIR / "citations.json"
DEFAULT_MATRIX = KNOWLEDGE_DIR / "coverage_matrix.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_citation_index(path: Path) -> dict[str, dict[str, Any]]:
    data = load_json(path)
    return {item["id"]: item for item in data.get("citations", [])}


def collect_ids(entry: dict[str, Any]) -> list[str]:
    ids = list(entry.get("required_citation_ids", []))
    for topic_ids in entry.get("conditional_topics", {}).values():
        ids.extend(topic_ids)
    return ids


def summarize_citation(item: dict[str, Any]) -> dict[str, str]:
    return {
        "id": item.get("id", ""),
        "law": item.get("law", ""),
        "article": item.get("article", ""),
        "title": item.get("title", ""),
        "last_verified_at": item.get("last_verified_at", ""),
        "source_name": item.get("source_name", ""),
    }


def check_entry(contract_type: str, entry: dict[str, Any], citation_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required_ids = entry.get("required_citation_ids", [])
    conditional_topics = entry.get("conditional_topics", {})
    required_unknown = [item_id for item_id in required_ids if item_id not in citation_index]
    conditional_unknown = {
        topic: [item_id for item_id in ids if item_id not in citation_index]
        for topic, ids in conditional_topics.items()
        if any(item_id not in citation_index for item_id in ids)
    }
    required_found = [item_id for item_id in required_ids if item_id in citation_index]
    coverage = (len(required_found) / len(required_ids)) if required_ids else 1.0

    return {
        "contract_type": contract_type,
        "core_laws": entry.get("core_laws", []),
        "required_total": len(required_ids),
        "required_found": len(required_found),
        "coverage": round(coverage, 4),
        "missing_required_ids": required_unknown,
        "unknown_conditional_ids": conditional_unknown,
        "required_citations": [summarize_citation(citation_index[item_id]) for item_id in required_found],
        "conditional_topics": conditional_topics,
    }


def check_matrix(matrix: dict[str, Any], citation_index: dict[str, dict[str, Any]], contract_type: Optional[str]) -> dict[str, Any]:
    contract_types = matrix.get("contract_types", {})
    if contract_type:
        if contract_type not in contract_types:
            return {
                "ok": False,
                "error": f"未找到合同类型：{contract_type}",
                "available_contract_types": sorted(contract_types),
            }
        entries = {contract_type: contract_types[contract_type]}
    else:
        entries = contract_types

    results = [check_entry(name, entry, citation_index) for name, entry in entries.items()]
    ok = all(not item["missing_required_ids"] and not item["unknown_conditional_ids"] for item in results)
    return {
        "ok": ok,
        "schema_version": matrix.get("schema_version", ""),
        "updated_at": matrix.get("updated_at", ""),
        "checked_contract_types": len(results),
        "citation_count": len(citation_index),
        "results": results,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    if not payload.get("ok") and "error" in payload:
        available = "、".join(payload.get("available_contract_types", []))
        return f"## 法条覆盖矩阵校验\n\n- 结果：失败\n- 原因：{payload['error']}\n- 可用合同类型：{available}\n"

    lines = [
        "## 法条覆盖矩阵校验",
        "",
        f"- 结果：{'通过' if payload.get('ok') else '存在缺口'}",
        f"- 覆盖合同类型数：{payload.get('checked_contract_types', 0)}",
        f"- 本地法条库条目数：{payload.get('citation_count', 0)}",
        "",
    ]
    for item in payload.get("results", []):
        lines.extend([
            f"### {item['contract_type']}",
            "",
            f"- 核心法律：{'、'.join(item.get('core_laws', []))}",
            f"- 基础覆盖：{item['required_found']}/{item['required_total']} ({item['coverage']:.0%})",
        ])
        if item.get("missing_required_ids"):
            lines.append(f"- 缺失基础法条 ID：{', '.join(item['missing_required_ids'])}")
        if item.get("unknown_conditional_ids"):
            lines.append(f"- 条件议题存在未知 ID：{json.dumps(item['unknown_conditional_ids'], ensure_ascii=False)}")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="校验合同类型法条覆盖矩阵")
    parser.add_argument("--type", help="只检查指定合同类型；省略则检查全部")
    parser.add_argument("--citations", default=str(DEFAULT_CITATIONS), help="citations.json 路径")
    parser.add_argument("--matrix", default=str(DEFAULT_MATRIX), help="coverage_matrix.json 路径")
    parser.add_argument("--as-markdown", action="store_true", help="输出 Markdown 摘要")
    args = parser.parse_args()

    citation_index = load_citation_index(Path(args.citations).expanduser())
    matrix = load_json(Path(args.matrix).expanduser())
    payload = check_matrix(matrix, citation_index, args.type)

    if args.as_markdown:
        print(render_markdown(payload))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    if not payload.get("ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

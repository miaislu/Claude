#!/usr/bin/env python3
"""
falv-agent 使用日志。

日志目标：
- 统计合同类型、法条引用和覆盖矩阵缺口，用于后续扩充 citations.json/coverage_matrix.json。
- 不保存合同全文、文件路径、具体当事方名称或报告正文。

用法：
  python3 scripts/usage_log.py record --analysis /tmp/falv_results.json --contract /tmp/contract.txt
  python3 scripts/usage_log.py report
"""

import argparse
import hashlib
import json
import os
import re
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

try:
    from legal_citation_check import check_text as check_legal_citations
except ImportError:
    check_legal_citations = None


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_PROJECT_ROOT = Path("~/Documents/Claude/projects/falv-agent").expanduser()
DEFAULT_LOG = Path(
    (
        os.environ.get("FALV_USAGE_LOG")
        or str((CANONICAL_PROJECT_ROOT if CANONICAL_PROJECT_ROOT.exists() else ROOT) / "logs" / "usage_events.jsonl")
    )
).expanduser()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_text_from_json(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(extract_text_from_json(v) for v in value.values())
    if isinstance(value, list):
        return "\n".join(extract_text_from_json(v) for v in value)
    return str(value) if value is not None else ""


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def collect_citations(analysis: dict[str, Any]) -> dict[str, Any]:
    text = extract_text_from_json(analysis.get("agent_results", []))
    precomputed_problematic = []
    for item in analysis.get("citation_warnings", []):
        warning = item.get("warning", item)
        if isinstance(warning, dict):
            precomputed_problematic.append({
                "citation": warning.get("citation", ""),
                "status": warning.get("status", ""),
                "law": warning.get("law", ""),
                "article": warning.get("article", ""),
                "knowledge_id": warning.get("knowledge_id", ""),
            })

    if check_legal_citations is None:
        citations = sorted(set(re.findall(r"《[^》]+》第[一二三四五六七八九十百千万零〇两]+条", text)))
        return {
            "used_knowledge_ids": [],
            "problematic_citations": precomputed_problematic,
            "raw_citation_count": len(citations),
        }

    checked = check_legal_citations(text)
    used_ids = sorted({
        item.get("knowledge_id")
        for item in checked.get("findings", [])
        if item.get("knowledge_id")
    })
    problematic = precomputed_problematic + [
        {
            "citation": item.get("citation", ""),
            "status": item.get("status", ""),
            "law": item.get("law", ""),
            "article": item.get("article", ""),
            "knowledge_id": item.get("knowledge_id", ""),
        }
        for item in checked.get("findings", [])
        if item.get("status") in ["deprecated", "stale", "unknown", "topic_mismatch"]
    ]
    return {
        "used_knowledge_ids": used_ids,
        "problematic_citations": problematic,
        "raw_citation_count": len(checked.get("findings", [])),
    }


def build_event(analysis: dict[str, Any], contract_text: str = "") -> dict[str, Any]:
    citation_info = collect_citations(analysis)
    legal_coverage = analysis.get("legal_coverage") or {}
    required_ids = legal_coverage.get("required_citation_ids", [])
    active_topics = legal_coverage.get("active_review_topics", [])
    used_ids = citation_info["used_knowledge_ids"]
    missing_required_ids = [
        item_id for item_id in required_ids
        if item_id not in used_ids
    ]
    security = analysis.get("security_preflight") or {}

    return {
        "schema_version": "1.0",
        "event_id": str(uuid.uuid4()),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "contract_hash": short_hash(contract_text) if contract_text else "",
        "contract_type": analysis.get("contract_type", ""),
        "review_mode": analysis.get("review_mode", ""),
        "legal_risk_score": analysis.get("legal_risk_score"),
        "review_completeness_score": analysis.get("review_completeness_score"),
        "skipped_agents": analysis.get("skipped_agents", []),
        "security_preflight_level": security.get("confidentiality_level", ""),
        "legal_coverage_status": legal_coverage.get("status", ""),
        "legal_coverage_type": legal_coverage.get("contract_type", ""),
        "required_citation_ids": required_ids,
        "active_review_topic_ids": [item.get("id", "") for item in active_topics if item.get("id")],
        "confirmation_question_count": len(legal_coverage.get("confirmation_questions", [])),
        "used_knowledge_ids": used_ids,
        "missing_required_citation_ids": missing_required_ids,
        "problematic_citations": citation_info["problematic_citations"],
        "raw_citation_count": citation_info["raw_citation_count"],
    }


def append_event(event: dict[str, Any], log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def iter_events(log_path: Path):
    if not log_path.exists():
        return
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def build_report(log_path: Path) -> dict[str, Any]:
    events = list(iter_events(log_path) or [])
    by_type = Counter(event.get("contract_type", "未知") for event in events)
    used_ids = Counter()
    missing_ids_by_type: dict[str, Counter] = defaultdict(Counter)
    problematic_status = Counter()
    problematic_citations = Counter()

    for event in events:
        contract_type = event.get("contract_type", "未知")
        used_ids.update(event.get("used_knowledge_ids", []))
        missing_ids_by_type[contract_type].update(event.get("missing_required_citation_ids", []))
        for item in event.get("problematic_citations", []):
            problematic_status[item.get("status", "")] += 1
            problematic_citations[item.get("citation", "")] += 1

    return {
        "event_count": len(events),
        "contract_type_counts": dict(by_type),
        "top_used_knowledge_ids": used_ids.most_common(30),
        "missing_required_ids_by_type": {
            contract_type: counter.most_common(30)
            for contract_type, counter in missing_ids_by_type.items()
        },
        "problematic_status_counts": dict(problematic_status),
        "top_problematic_citations": problematic_citations.most_common(30),
        "log_path": str(log_path),
    }


def cmd_record(args):
    analysis = load_json(Path(args.analysis).expanduser())
    contract_text = ""
    if args.contract:
        contract_path = Path(args.contract).expanduser()
        if contract_path.exists():
            contract_text = contract_path.read_text(encoding="utf-8")
    event = build_event(analysis, contract_text)
    append_event(event, Path(args.log).expanduser())
    print(json.dumps({"status": "ok", "event_id": event["event_id"], "log": args.log}, ensure_ascii=False, indent=2))


def cmd_report(args):
    report = build_report(Path(args.log).expanduser())
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="falv-agent 使用日志")
    sub = parser.add_subparsers(dest="command")

    p_record = sub.add_parser("record", help="记录一次审查使用事件")
    p_record.add_argument("--analysis", required=True, help="pipeline.py 输出的分析 JSON")
    p_record.add_argument("--contract", default="", help="合同文本路径；只用于生成短 hash，不记录原文")
    p_record.add_argument("--log", default=str(DEFAULT_LOG), help="usage JSONL 日志路径")

    p_report = sub.add_parser("report", help="汇总使用日志")
    p_report.add_argument("--log", default=str(DEFAULT_LOG), help="usage JSONL 日志路径")

    args = parser.parse_args()
    if args.command == "record":
        cmd_record(args)
    elif args.command == "report":
        cmd_report(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

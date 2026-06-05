#!/usr/bin/env python3
"""
将 pipeline.py 的 JSON 结果渲染为固定结构的法律审查 Markdown。

这个脚本只负责结构化呈现，不重新判断风险。它的存在是为了把最终报告
从“Claude 自由整合”收敛成可复用、可审计的法律 issue list。
"""

import argparse
import json
from datetime import datetime
from pathlib import Path


def agent_map(data: dict) -> dict:
    return {item.get("agent_name"): item for item in data.get("agent_results", [])}


def parsed(item: dict) -> dict:
    value = item.get("parsed") if item else None
    return value if isinstance(value, dict) else {}


def risk_degree(score) -> str:
    try:
        score = float(score)
    except (TypeError, ValueError):
        return "一般"
    if score >= 8:
        return "重大"
    if score >= 5:
        return "一般"
    return "轻微"


def issue_source_tag(item: dict) -> str:
    text = " ".join(str(item.get(k, "")) for k in ["problem", "risk_description", "impact_analysis"])
    if any(token in text for token in ["商业", "估值", "价格", "控制权", "董事会", "回购", "领售", "预算", "经营"]):
        return "商业决策"
    return "起草技术"


def add_section(lines: list, title: str):
    lines.append("")
    lines.append(f"## {title}")


def fmt_list_value(value):
    if isinstance(value, list):
        return "、".join(str(v) for v in value if v)
    return str(value or "")


def render(data: dict) -> str:
    agents = agent_map(data)
    tiao = parsed(agents.get("tiao-kuan-fen-xi"))
    feng = parsed(agents.get("feng-xian-ping-gu"))
    hegui = parsed(agents.get("he-gui-jian-cha"))
    yiwu = parsed(agents.get("yi-wu-jie-xi"))
    jianyi = parsed(agents.get("jian-yi-yin-qing"))

    lines = [
        "# 法律审查意见要点（草稿）",
        "",
        f"- 合同类型：{data.get('contract_type', '')}",
        f"- 审查立场：{data.get('party_stance', '')}",
        f"- 审查模式：{data.get('review_mode', '')}",
        f"- 综合评分：{data.get('overall_score', '未评分')}",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
    ]

    skipped = data.get("skipped_agents", [])
    if skipped:
        lines.append(f"- 未完成 Agent：{fmt_list_value(skipped)}")

    add_section(lines, "一、合同基本信息")
    basic = tiao.get("basic_info", {})
    if basic:
        for key, label in [
            ("contract_type", "合同性质"),
            ("party_a", "甲方/主要一方"),
            ("party_b", "乙方/主要相对方"),
            ("amount", "交易金额"),
            ("duration", "期限"),
            ("signing_place", "签署地"),
        ]:
            if basic.get(key):
                lines.append(f"- {label}：{basic.get(key)}")
    else:
        lines.append("- 未取得结构化基本信息。")
    if tiao.get("total_clauses") is not None:
        lines.append(f"- 已识别条款数量：{tiao.get('total_clauses')}")

    add_section(lines, "二、主要法律问题")
    risks = feng.get("risk_assessment", [])
    if not isinstance(risks, list):
        risks = []
    risks = sorted(risks, key=lambda x: x.get("risk_score", 0) if isinstance(x, dict) else 0, reverse=True)
    if not risks:
        lines.append("未识别到结构化风险事项。")
    for idx, item in enumerate(risks, 1):
        if not isinstance(item, dict):
            continue
        degree = risk_degree(item.get("risk_score"))
        source = issue_source_tag(item)
        lines.extend([
            "",
            f"### 问题 {idx}：{item.get('risk_description') or item.get('clause_id') or '待补充问题标题'}",
            f"- 风险等级：{degree}",
            f"- 问题类型：{source}",
            f"- 涉及条款：{item.get('clause_id', '')}",
            f"- 影响对象：{item.get('affected_party', '')}",
            f"- 法律依据：{item.get('legal_basis', '')}",
            f"- 风险敞口：{item.get('financial_exposure', '')}",
            f"- 触发概率：{item.get('trigger_probability', '')}",
        ])

    add_section(lines, "三、合规核查")
    check = hegui.get("compliance_check", {})
    if isinstance(check, dict) and check:
        lines.append(f"- 总体状态：{check.get('overall_status', '')}")
        laws = check.get("applicable_laws", [])
        if laws:
            lines.append(f"- 适用法律：{fmt_list_value(laws)}")
        failed = check.get("failed", [])
        invalid = check.get("invalid_clauses", [])
        if failed:
            lines.append("")
            lines.append("需补充或调整事项：")
            for item in failed:
                lines.append(f"- {item.get('item', '')}；严重程度：{item.get('severity', '')}；依据：{item.get('basis', '')}")
        if invalid:
            lines.append("")
            lines.append("疑似无效或效力风险条款：")
            for item in invalid:
                lines.append(f"- {item.get('clause_id', '')}：{item.get('reason', '')}；依据：{item.get('basis', '')}")
    else:
        lines.append("未取得结构化合规核查结果。")

    add_section(lines, "四、关键权利义务")
    if yiwu.get("key_deadlines_summary"):
        lines.append(f"- 关键时限：{yiwu.get('key_deadlines_summary')}")
    for key, label in [
        ("party_a_obligations", "甲方义务"),
        ("party_b_obligations", "乙方义务"),
        ("imbalance_flags", "权利义务失衡提示"),
    ]:
        items = yiwu.get(key, [])
        if isinstance(items, list) and items:
            lines.append("")
            lines.append(f"{label}：")
            for item in items[:12]:
                if isinstance(item, dict):
                    desc = item.get("description") or item.get("event") or item.get("type") or str(item)
                    lines.append(f"- {desc}")
                else:
                    lines.append(f"- {item}")

    add_section(lines, "五、修改建议")
    recs = jianyi.get("recommendations", [])
    if not isinstance(recs, list):
        recs = []
    if not recs:
        lines.append("未取得结构化修改建议。")
    for idx, item in enumerate(recs, 1):
        if not isinstance(item, dict):
            continue
        tag = issue_source_tag(item)
        lines.extend([
            "",
            f"### 建议 {idx}：{item.get('problem') or item.get('clause_id') or '待补充建议标题'}",
            f"- 优先级：{item.get('priority', '')}",
            f"- 问题类型：{tag}",
            f"- 涉及条款：{item.get('clause_id', '')}",
            f"- 法律依据：{item.get('legal_basis', '')}",
        ])
        if item.get("original_text"):
            lines.append("- 原文摘录：")
            lines.append(f"> {item.get('original_text')}")
        if item.get("suggested_text"):
            lines.append("- 建议修改：")
            lines.append("")
            lines.append("```text")
            lines.append(str(item.get("suggested_text")))
            lines.append("```")

    add_confidentiality_section(lines, data, hegui)

    warnings = data.get("citation_warnings", [])
    if warnings:
        add_section(lines, "七、法条引用校验提示")
        for item in warnings:
            lines.append(f"- {item.get('agent', '')}：{item.get('warning', '')}")

    add_section(lines, "八、审查说明")
    lines.extend([
        "本报告为基于所提供文本生成的法律审查意见要点草稿，仅用于内部讨论和律师复核。",
        "涉及交易价格、控制权安排、商业谈判底线或风险接受度的事项，应由业务方结合交易目标作出商业决策。",
    ])
    return "\n".join(lines).strip() + "\n"


def add_confidentiality_section(lines: list, data: dict, hegui: dict):
    preflight = data.get("security_preflight", {})
    check = hegui.get("compliance_check", {}) if isinstance(hegui, dict) else {}
    special = check.get("confidentiality_and_data_review", {}) if isinstance(check, dict) else {}

    if not preflight and not special:
        return

    add_section(lines, "六、保密与数据合规专项提示")

    if preflight:
        lines.append("### （一）文件处理层面的敏感信息提示")
        lines.append(f"- 敏感等级：{preflight.get('confidentiality_level', '')}")
        if preflight.get("recommended_mode"):
            lines.append(f"- 建议处理模式：{preflight.get('recommended_mode')}")
        sensitive_items = preflight.get("sensitive_items", [])
        if sensitive_items:
            lines.append("- 识别到的敏感信息：")
            for item in sensitive_items:
                lines.append(f"  - {item.get('type', '')}：{item.get('count', 0)}处")
        keyword_hits = preflight.get("keyword_hits", [])
        if keyword_hits:
            lines.append("- 敏感类别关键词：")
            for item in keyword_hits:
                lines.append(f"  - {item.get('category', '')}：{fmt_list_value(item.get('keywords', []))}")

    if special:
        lines.append("")
        lines.append("### （二）合同条款层面的保密与数据合规提示")
        for key, label in [
            ("document_sensitivity", "文件敏感等级"),
            ("confidentiality_clause_status", "保密条款状态"),
            ("personal_information_involved", "是否涉及个人信息"),
            ("cross_border_transfer_involved", "是否涉及跨境传输"),
        ]:
            if key in special:
                lines.append(f"- {label}：{special.get(key)}")
        issues = special.get("issues", [])
        if isinstance(issues, list) and issues:
            lines.append("- 专项问题：")
            for issue in issues:
                if isinstance(issue, dict):
                    lines.append(f"  - {issue.get('item', '')}；依据：{issue.get('basis', '')}；建议：{issue.get('suggestion', '')}")
                else:
                    lines.append(f"  - {issue}")


def main():
    parser = argparse.ArgumentParser(description="渲染法律审查 Markdown 报告")
    parser.add_argument("--input", required=True, help="pipeline.py 输出的 JSON 文件")
    parser.add_argument("--output", required=True, help="Markdown 输出路径")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser()
    output_path = Path(args.output).expanduser()
    data = json.loads(input_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render(data), encoding="utf-8")
    print(json.dumps({"status": "ok", "output_file": str(output_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

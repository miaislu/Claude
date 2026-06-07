#!/usr/bin/env python3
"""
交易文件包审查入口（确定性预处理）。

职责：
- 扫描目录或文件列表，抽取 txt/md/docx 文本摘要
- 识别每份文件的交易角色和合同类型
- 输出交易包 manifest、缺失文件提示和跨文件一致性检查点

该脚本不调用 LLM，作为后续单文件 analyze 或整包审查的前置 harness。
"""

import argparse
import json
import re
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

import pipeline


SUPPORTED_SUFFIXES = {".txt", ".md", ".docx"}

ROLE_KEYWORDS = {
    "股东协议/SHA": ["股东协议", "SHA", "Shareholders", "股东会", "董事会", "保护性权利"],
    "投资协议/认购协议": ["投资协议", "认购协议", "增资协议", "投资框架", "Term Sheet", "估值", "交割"],
    "股权转让/收购协议": ["股权转让", "股权收购", "购买协议", "出售方", "受让方", "转让方"],
    "公司章程": ["公司章程", "章程修正案", "Articles of Association"],
    "披露函/披露清单": ["披露函", "披露清单", "Disclosure", "例外事项"],
    "交割条件清单": ["交割条件", "先决条件", "CP", "交割文件", "长停日"],
    "员工激励/期权文件": ["员工激励", "期权", "股权激励", "ESOP", "vesting"],
    "数据处理/隐私文件": ["个人信息", "隐私政策", "数据处理", "数据共享", "跨境"],
}

EXPECTED_BY_TRANSACTION = {
    "投资交易包": [
        "股东协议/SHA",
        "投资协议/认购协议",
        "公司章程",
        "披露函/披露清单",
        "交割条件清单",
    ]
}

CONSISTENCY_CHECKS = [
    {
        "id": "governance_vs_articles",
        "name": "治理权利与公司章程衔接",
        "required_roles": ["股东协议/SHA", "公司章程"],
        "keywords": ["董事委派", "一票否决", "保护性权利", "表决权", "重大事项"],
        "message": "股东协议中的董事委派、否决权、表决权等治理安排，需要检查是否同步写入公司章程或章程修正案。",
    },
    {
        "id": "closing_conditions_vs_main_agreement",
        "name": "交割条件与主协议一致性",
        "required_roles": ["投资协议/认购协议", "交割条件清单"],
        "keywords": ["交割条件", "先决条件", "长停日", "反垄断申报", "经营者集中"],
        "message": "主协议、交割条件清单和附件中的先决条件、长停日、监管审批应保持一致。",
    },
    {
        "id": "disclosure_vs_reps",
        "name": "披露函与陈述保证例外",
        "required_roles": ["投资协议/认购协议", "披露函/披露清单"],
        "keywords": ["陈述与保证", "披露", "例外", "重大不利变化", "合规"],
        "message": "披露函例外事项应逐项对应主协议陈述保证，否则可能导致违约责任边界不清。",
    },
    {
        "id": "data_due_diligence",
        "name": "尽调资料中的个人信息和跨境数据",
        "required_roles": [],
        "keywords": ["个人信息", "客户信息", "员工信息", "用户信息", "数据室", "跨境", "境外"],
        "message": "如交易包包含个人信息或数据室资料，应检查披露依据、接收方安全义务、删除/返还和跨境传输机制。",
    },
]


@dataclass
class BundleDocument:
    path: str
    filename: str
    suffix: str
    role: str
    contract_type: str
    confidence: str
    title_hint: str
    matched_keywords: list[str] = field(default_factory=list)
    role_keywords: list[str] = field(default_factory=list)
    text_excerpt: str = ""


def extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    texts = [node.text for node in root.findall(".//w:t", ns) if node.text]
    return "\n".join(texts)


def read_text(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        return extract_docx_text(path)
    return path.read_text(encoding="utf-8", errors="ignore")


def iter_files(paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        expanded = path.expanduser()
        if expanded.is_dir():
            for candidate in expanded.rglob("*"):
                if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_SUFFIXES:
                    files.append(candidate)
        elif expanded.is_file() and expanded.suffix.lower() in SUPPORTED_SUFFIXES:
            files.append(expanded)
    return sorted(set(files), key=lambda item: str(item))


def detect_role(filename: str, text: str) -> tuple[str, list[str]]:
    haystack = f"{filename}\n{text[:8000]}"
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    title_area = f"{filename}\n{first_line}"
    best_role = "其他交易文件"
    best_hits: list[str] = []
    best_score = 0
    for role, keywords in ROLE_KEYWORDS.items():
        hits = [kw for kw in keywords if kw and kw in haystack]
        title_hits = [kw for kw in hits if kw in title_area]
        score = len(hits) + len(title_hits) * 3
        if score > best_score:
            best_role = role
            best_hits = hits
            best_score = score
    return best_role, best_hits


def classify_transaction(documents: list[BundleDocument]) -> str:
    roles = {doc.role for doc in documents}
    if {"股东协议/SHA", "投资协议/认购协议"} & roles or {"股权转让/收购协议", "公司章程"} & roles:
        return "投资交易包"
    return "通用交易包"


def build_document(path: Path) -> BundleDocument:
    text = read_text(path)
    role, role_keywords = detect_role(path.name, text)
    det = pipeline.detect_type(text)
    return BundleDocument(
        path=str(path),
        filename=path.name,
        suffix=path.suffix.lower(),
        role=role,
        contract_type=det.contract_type,
        confidence=det.confidence,
        title_hint=det.title_hint,
        matched_keywords=det.matched_keywords,
        role_keywords=role_keywords,
        text_excerpt=re.sub(r"\s+", " ", text[:300]).strip(),
    )


def bundle_gaps(transaction_type: str, documents: list[BundleDocument]) -> list[dict]:
    expected = EXPECTED_BY_TRANSACTION.get(transaction_type, [])
    roles = {doc.role for doc in documents}
    return [
        {
            "role": role,
            "message": f"交易包中未识别到【{role}】，建议确认是否不存在、尚未提供或文件名无法识别。",
        }
        for role in expected
        if role not in roles
    ]


def cross_file_checks(documents: list[BundleDocument]) -> list[dict]:
    roles = {doc.role for doc in documents}
    combined = "\n".join(f"{doc.filename}\n{doc.title_hint}\n{' '.join(doc.role_keywords)}\n{doc.text_excerpt}" for doc in documents)
    checks = []
    for check in CONSISTENCY_CHECKS:
        required_roles = set(check["required_roles"])
        role_ready = required_roles.issubset(roles) if required_roles else True
        hits = [kw for kw in check["keywords"] if kw in combined]
        status = "triggered" if role_ready and hits else "needs_documents" if required_roles and not role_ready else "not_triggered"
        checks.append({
            "id": check["id"],
            "name": check["name"],
            "status": status,
            "matched_keywords": hits,
            "required_roles": check["required_roles"],
            "message": check["message"],
        })
    return checks


def build_bundle(paths: list[Path]) -> dict:
    files = iter_files(paths)
    documents = [build_document(path) for path in files]
    transaction_type = classify_transaction(documents)
    return {
        "schema_version": "1.0",
        "transaction_type": transaction_type,
        "document_count": len(documents),
        "documents": [asdict(doc) for doc in documents],
        "missing_expected_documents": bundle_gaps(transaction_type, documents),
        "cross_file_checks": cross_file_checks(documents),
        "next_step": "先补齐 missing_expected_documents；再按 documents[].contract_type 逐文件审查；最后对 triggered 的 cross_file_checks 做整包一致性审查。",
    }


def main():
    parser = argparse.ArgumentParser(description="生成交易文件包审查 manifest")
    parser.add_argument("paths", nargs="+", help="交易文件或目录路径，支持 txt/md/docx")
    parser.add_argument("--output", help="输出 JSON 路径；省略则打印到 stdout")
    args = parser.parse_args()

    payload = build_bundle([Path(item) for item in args.paths])
    raw = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(raw + "\n", encoding="utf-8")
    else:
        print(raw)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
中国法律 AI Agent — 核心分析管道
Plan C: Python 控制流 + Claude Code UI 界面
Plan A 扩展路: 去掉 Claude Code 包装，直接调 run() 即可

子命令:
  detect   --contract <文件>              → 识别合同类型，返回 JSON
  analyze  --contract <文件> --type <类型> --party <立场> --output <文件>
                                          → 并发调 5 个 Agent，结果写入 JSON

依赖: pip install anthropic
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

try:
    from anthropic import AsyncAnthropic
except ImportError:
    AsyncAnthropic = None

try:
    from legal_citation_check import check_text as check_legal_citations
except ImportError:
    print("⚠️  legal_citation_check 模块未找到，法条引用校验功能已禁用。", file=sys.stderr)
    check_legal_citations = None

try:
    from usage_log import append_event as append_usage_event
    from usage_log import build_event as build_usage_event
    from usage_log import DEFAULT_LOG as DEFAULT_USAGE_LOG
except ImportError:
    print("⚠️  usage_log 模块未找到，使用日志功能已禁用。", file=sys.stderr)
    append_usage_event = None
    build_usage_event = None
    DEFAULT_USAGE_LOG = None


# ── 路由表（从 SKILL.md 迁移到 Python，这是唯一的权威来源）────────────────
ROUTING: dict[str, dict] = {
    "投资协议": {
        "keywords": ["认购", "优先股", "对赌", "估值", "回购", "反稀释", "领售", "Term Sheet",
                     "股权转让协议", "股东协议", "可转债", "投资框架"],
        "context":  "investment.md",
        "parties":  ["投资方", "创始人（被投方）", "平衡分析"],
    },
    "劳动合同": {
        "keywords": ["劳动合同", "劳务", "试用期", "社会保险", "竞业限制", "工作地点", "劳动者"],
        "context":  "labor.md",
        "parties":  ["用人单位", "劳动者", "平衡分析"],
    },
    "数据处理协议": {
        "keywords": ["个人信息", "数据处理", "数据共享", "PIPL", "数据安全", "隐私政策",
                     "处理目的", "数据主体", "跨境传输", "境外接收方", "标准合同"],
        "context":  "data.md",
        "parties":  ["委托方（数据控制者）", "受托方（处理者）", "平衡分析"],
    },
    "电商平台服务协议": {
        "keywords": ["平台", "入驻", "店铺", "保证金", "佣金", "技术服务费", "商家", "运营规则"],
        "context":  "ecommerce-service.md",
        "parties":  ["商家（入驻方）", "平台方", "平衡分析"],
    },
    "平台技术服务协议": {
        "keywords": ["平台技术服务", "技术服务费", "接口", "API", "SLA", "服务等级", "系统对接",
                     "商家技术服务", "数据接口", "技术支持", "平台规则"],
        "context":  "ecommerce-service.md",
        "parties":  ["平台方", "商家/服务使用方", "平衡分析"],
    },
    "广告协议": {
        "keywords": ["广告", "投放", "媒体", "代言", "KOL", "MCN", "CPM", "CPC", "曝光量"],
        "context":  "advertising.md",
        "parties":  ["广告主", "媒体（代理商）", "平衡分析"],
    },
    "采购合同": {
        "keywords": ["采购", "供货", "供应商", "货物", "原材料", "MOQ", "验收", "交货"],
        "context":  "procurement.md",
        "parties":  ["采购方（甲方）", "供应商（乙方）", "平衡分析"],
    },
    "商业租赁合同": {
        "keywords": ["租赁", "租用", "出租", "租金", "押金", "免租期", "承租", "房东"],
        "context":  "lease.md",
        "parties":  ["租客（承租方）", "房东（出租方）", "平衡分析"],
    },
    "技术开发合同": {
        "keywords": ["技术开发", "软件开发", "定制开发", "系统集成", "验收", "源代码",
                     "知识产权归属", "开发方"],
        "context":  "tech-dev.md",
        "parties":  ["委托方（甲方）", "开发方（乙方）", "平衡分析"],
    },
    "借款合同": {
        "keywords": ["借款", "借贷", "贷款", "利息", "还款", "抵押", "质押", "担保"],
        "context":  "loan.md",
        "parties":  ["借款人", "出借人", "平衡分析"],
    },
    "知识产权许可合同": {
        "keywords": ["许可", "授权", "商标", "专利", "版权", "著作权", "Royalty", "独占", "排他"],
        "context":  "ip-license.md",
        "parties":  ["被许可方", "许可方", "平衡分析"],
    },
    "分销代理合同": {
        "keywords": ["经销", "代理", "分销", "独家", "渠道", "佣金", "转售", "品牌授权"],
        "context":  "distribution.md",
        "parties":  ["经销商（代理商）", "品牌方", "平衡分析"],
    },
    "SaaS云服务协议": {
        "keywords": ["SaaS", "云服务", "订阅", "API", "平台服务", "可用性", "SLA", "服务商"],
        "context":  "saas.md",
        "parties":  ["企业用户", "服务商", "平衡分析"],
    },
}
ROUTING_FALLBACK = {
    "context": "general.md",
    "parties": ["甲方", "乙方", "平衡分析"],
}

TITLE_HINTS = {
    "投资协议": ["股东协议", "投资协议", "增资协议", "认购协议", "股权收购协议", "融资协议", "投资框架协议", "SHA"],
    "劳动合同": ["劳动合同", "劳务合同", "聘用协议", "竞业限制协议"],
    "数据处理协议": ["数据处理协议", "个人信息处理协议", "数据共享协议", "隐私协议"],
    "电商平台服务协议": ["平台服务协议", "入驻协议", "技术服务协议", "商家服务协议"],
    "平台技术服务协议": ["平台技术服务协议", "商家技术服务协议", "接口服务协议", "平台API服务协议"],
    "广告协议": ["广告协议", "广告投放协议", "营销服务协议", "推广服务协议"],
    "采购合同": ["采购合同", "供货合同", "采购协议", "供应协议"],
    "商业租赁合同": ["租赁合同", "房屋租赁合同", "商铺租赁合同"],
    "技术开发合同": ["技术开发合同", "软件开发合同", "定制开发协议", "系统集成协议"],
    "借款合同": ["借款合同", "贷款合同", "借款协议"],
    "知识产权许可合同": ["知识产权许可协议", "商标许可协议", "专利许可协议", "著作权许可协议"],
    "分销代理合同": ["分销协议", "经销协议", "代理协议", "渠道合作协议"],
    "SaaS云服务协议": ["SaaS服务协议", "云服务协议", "订阅服务协议"],
}

DEPRECATED_LAWS = [
    "合同法", "担保法", "物权法", "民法总则", "民法通则", "侵权责任法",
    "婚姻法", "继承法", "收养法",
]

AGENT_SCHEMAS = {
    "tiao-kuan-fen-xi": ["basic_info", "clauses"],
    "feng-xian-ping-gu": ["risk_assessment", "overall_risk_score"],
    "he-gui-jian-cha": ["compliance_check"],
    "yi-wu-jie-xi": ["timeline", "party_a_obligations", "party_b_obligations"],
    "jian-yi-yin-qing": ["recommendations"],
}

GENERIC_PARTY_TERMS = {
    "甲方", "乙方", "丙方", "丁方", "戊方", "对方", "我方", "贵方",
    "投资方", "投资人", "创始人", "创始人（被投方）", "被投方", "公司", "目标公司",
    "平台方", "商家", "委托方", "受托方", "平衡",
}

AGENT_WEIGHTS = {
    "tiao-kuan-fen-xi": 0.20,
    "feng-xian-ping-gu": 0.25,
    "he-gui-jian-cha":   0.20,
    "yi-wu-jie-xi":      0.15,
    "jian-yi-yin-qing":  0.20,
}

# ── Agent 依赖 DAG（决定执行顺序和上下文传递）─────────────────────────────
#
#  Phase 1: tiao-kuan-fen-xi（条款分析师）
#    └─ 独立运行，输出条款分类 JSON
#    └─ 依据：是其他 Agent 的输入基础
#
#  Phase 2: feng-xian-ping-gu | he-gui-jian-cha | yi-wu-jie-xi （真并发）
#    └─ 全部接收 Phase 1 输出作为额外上下文
#    └─ feng 明确声明依赖（"基于条款分析师的分类结果"）
#    └─ he / yi 不强依赖但受益于条款分类（clause_id 交叉引用）
#
#  Phase 3: jian-yi-yin-qing（修改建议引擎）
#    └─ 明确依赖 feng（高危条款列表）和 he（合规缺失项）
#    └─ 依据 agent 文件："读取风险评估师和合规检查员的结果"
#
AGENT_PHASES = [
    {
        "phase": 1,
        "label": "条款识别",
        "agents": ["tiao-kuan-fen-xi"],
        "upstream": [],                                  # 无依赖
    },
    {
        "phase": 2,
        "label": "并发分析",
        "agents": ["feng-xian-ping-gu", "he-gui-jian-cha", "yi-wu-jie-xi"],
        "upstream": ["tiao-kuan-fen-xi"],                # 接收 Phase 1 输出
    },
    {
        "phase": 3,
        "label": "修改建议",
        "agents": ["jian-yi-yin-qing"],
        "upstream": ["feng-xian-ping-gu", "he-gui-jian-cha"],  # 接收 Phase 2 核心输出
    },
]

DEFAULT_AGENTS_DIR = Path("~/.claude/agents").expanduser()
DEFAULT_MODEL       = "claude-opus-4-8"
PROJECT_ROOT        = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR       = PROJECT_ROOT / "legal_knowledge"


# ── 数据结构 ──────────────────────────────────────────────────────────────
@dataclass
class DetectResult:
    contract_type: str
    confidence: str           # "HIGH" | "MEDIUM" | "LOW"
    matched_keywords: list
    available_parties: list
    context_file: str
    identified_parties: list = field(default_factory=list)
    is_multipartite: bool = False
    title_hint: str = ""


@dataclass
class AgentResult:
    agent_name: str
    success: bool
    content: str              # 原始文本（JSON 或自然语言）
    parsed: Optional[dict]    # 尝试 JSON 解析后的结果
    elapsed_seconds: float
    error: Optional[str] = None
    validation_errors: list = field(default_factory=list)
    citation_warnings: list = field(default_factory=list)


@dataclass
class AnalysisResults:
    project_name: str
    contract_type: str
    party_stance: str
    review_mode: str
    overall_score: Optional[int]
    risk_calibration: dict    # 风险评级校准结果
    agent_results: list       # List[AgentResult as dict]
    skipped_agents: list      # 失败的 Agent 名称
    citation_warnings: list   # 法条引用警告
    legal_coverage: dict      # 合同类型法条覆盖矩阵
    security_preflight: dict  # 审查前本地保密预检结果
    usage_log: dict           # 使用日志写入结果
    guidelines: str           # _guidelines.md 内容（提供给 Claude 格式化用）
    context_content: str      # 专项 context 文件内容
    elapsed_total: float


# ── 核心函数 ──────────────────────────────────────────────────────────────

def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip(" ，,；;。.\n\t")


def extract_title_hint(text: str) -> str:
    for line in text.splitlines()[:20]:
        clean = normalize_space(line)
        if not clean:
            continue
        if len(clean) <= 80 and any(token in clean for token in ["协议", "合同", "契约", "条款", "Terms", "SHA"]):
            return clean
    return normalize_space(text[:80])


def extract_party_block(text: str) -> str:
    sample = text[:6000]
    starters = [
        "由以下各方", "由下列各方", "本协议由以下各方", "本协议由下列各方", "本协议各方", "本合同由以下各方",
        "甲方", "签署方", "各方如下",
    ]
    start_positions = [sample.find(s) for s in starters if sample.find(s) >= 0]
    start = min(start_positions) if start_positions else 0
    block = sample[start:start + 3000]
    end_markers = ["鉴于", "第一条", "第1条", "一、", "定义", "WHEREAS"]
    end_positions = [block.find(m) for m in end_markers if block.find(m) > 80]
    if end_positions:
        block = block[:min(end_positions)]
    return block


def add_party(parties: list, name: str, role: str = ""):
    name = normalize_space(name)
    role = normalize_space(role)
    if not name or len(name) > 90:
        return
    if name in ["甲方", "乙方", "丙方", "丁方", "各方", "一方", "另一方", "本协议"]:
        return
    label = f"{name}（{role}）" if role and role not in name else name
    if label not in parties:
        parties.append(label)


def extract_parties(text: str) -> tuple[list, bool]:
    """
    从合同开头的签署方/定义区提取具体当事方。
    目标不是做实体识别全覆盖，而是避免多方协议只返回“甲方/乙方”的流程风险。
    """
    block = extract_party_block(text)
    parties: list[str] = []

    labeled_patterns = [
        r"(甲方|乙方|丙方|丁方|戊方)[：:]\s*([^\n，,；;。]{1,80})",
        r"(投资人股东|投资方|创始人股东|创始人|公司|目标公司|购买方|出售方|转让方|受让方)[：:]\s*([^\n，,；;。]{1,80})",
        r"\(([A-Z])\)\s*([^\n，,；;。]{1,80})",
        r"^([A-Z])\s*$\n([^\n，,；;。]{1,80})",
    ]
    for pattern in labeled_patterns:
        for m in re.finditer(pattern, block, re.M):
            role, name = m.group(1), m.group(2)
            add_party(parties, name, role)

    alias_patterns = [
        r"([A-Za-z][A-Za-z0-9 ._-]{0,30}|[\u4e00-\u9fa5A-Za-z0-9（）()·.\-]{2,60})[，,]?\s*[（(]?以下简称[“\"]([^”\"]{1,30})[”\"][）)]?",
        r"([A-Za-z][A-Za-z0-9 ._-]{0,30}|[\u4e00-\u9fa5A-Za-z0-9（）()·.\-]{2,60})[（(][“\"]([^”\"]{1,30})[”\"](?:方)?[）)]",
    ]
    for pattern in alias_patterns:
        for m in re.finditer(pattern, block):
            raw, alias = m.group(1), m.group(2)
            raw = normalize_space(raw)
            if any(skip in raw for skip in ["协议", "合同", "以下简称", "鉴于", "身份证号", "统一社会信用代码", "一家依照", "一名中国籍"]):
                continue
            add_party(parties, raw, alias)

    # 对 SHA/投资协议常见的自然人创始人缩写做兜底。
    for m in re.finditer(r"(创始人|Founder|创始股东)[^\n。；;]{0,40}?([A-Z])(?:[，,；;\s]|$)", block, re.I):
        add_party(parties, m.group(2), "创始人")
    for m in re.finditer(r"(上海[\u4e00-\u9fa5]{2,30}(?:企业管理|投资|合伙企业)[^\n，,；;。]{0,30})", block):
        add_party(parties, m.group(1), "投资方")

    # 去重：同一名称带不同角色时保留较长标签；避免把条款标题误认为主体。
    filtered = []
    seen_core = set()
    for p in parties:
        core = re.sub(r"（.*?）", "", p)
        if core in seen_core:
            continue
        if any(bad in core for bad in ["陈述", "保证", "条款", "定义", "目录", "一家依照", "一名中国籍"]):
            continue
        seen_core.add(core)
        filtered.append(p)

    is_multipartite = len(filtered) > 2 or any(token in block for token in ["丙方", "丁方", "各方", "创始人股东", "投资人股东"])
    if filtered:
        filtered.append("平衡分析")
    return filtered, is_multipartite


def detect_type(text: str) -> DetectResult:
    """
    纯代码的合同类型识别。
    计算每种类型的关键词命中数，返回置信度分级结果。
    这是从 SKILL.md 迁移到 Python 的第一步（Factor 8）。
    """
    title_hint = extract_title_hint(text)
    text_sample = text[:8000]
    title_sample = text[:800]
    scores = {}
    matched = {}
    for ctype, cfg in ROUTING.items():
        hits = [kw for kw in cfg["keywords"] if kw in text_sample]
        title_hits = [kw for kw in TITLE_HINTS.get(ctype, []) if kw in title_hint or kw in title_sample]
        scores[ctype] = len(hits) + len(title_hits) * 3
        matched[ctype] = hits
        for kw in title_hits:
            if kw not in matched[ctype]:
                matched[ctype].insert(0, kw)

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]

    if best_score >= 5:
        confidence = "HIGH"
    elif best_score >= 2:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"
        best_type = "通用"

    if best_type == "通用" or best_type not in ROUTING:
        context_file = ROUTING_FALLBACK["context"]
        parties      = ROUTING_FALLBACK["parties"]
    else:
        context_file = ROUTING[best_type]["context"]
        parties      = ROUTING[best_type]["parties"]

    identified_parties, is_multipartite = extract_parties(text)
    if identified_parties:
        parties = identified_parties

    return DetectResult(
        contract_type     = best_type,
        confidence        = confidence,
        matched_keywords  = matched.get(best_type, []),
        available_parties = parties,
        context_file      = context_file,
        identified_parties = identified_parties,
        is_multipartite   = is_multipartite,
        title_hint        = title_hint,
    )


def load_file(path: Path, label: str = "") -> str:
    """安全读文件，失败返回空字符串 + 警告（Factor 9）"""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"⚠️  找不到文件：{path}（{label}）", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"⚠️  读取失败：{path}（{e}）", file=sys.stderr)
        return ""


def extract_json_object(content: str) -> Optional[dict]:
    """从模型回复中提取第一个完整 JSON object，避免贪婪正则吞掉多余文本。"""
    start = content.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(content)):
        ch = content[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(content[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def validate_agent_output(agent_name: str, parsed: Optional[dict]) -> list:
    errors = []
    if not isinstance(parsed, dict):
        return ["未返回可解析的 JSON object"]
    for key in AGENT_SCHEMAS.get(agent_name, []):
        if key not in parsed:
            errors.append(f"缺少顶层字段：{key}")
    errors.extend(validate_agent_deep_schema(agent_name, parsed))
    return errors


def validate_agent_deep_schema(agent_name: str, parsed: dict) -> list:
    errors = []
    if agent_name == "tiao-kuan-fen-xi":
        clauses = parsed.get("clauses", [])
        if not isinstance(clauses, list):
            return ["clauses 必须为数组"]
        for idx, item in enumerate(clauses[:80]):
            if not isinstance(item, dict):
                errors.append(f"clauses[{idx}] 必须为 object")
                continue
            for key in ["id", "category", "location", "summary"]:
                if not item.get(key):
                    errors.append(f"clauses[{idx}] 缺少字段：{key}")
    elif agent_name == "feng-xian-ping-gu":
        risks = parsed.get("risk_assessment", [])
        if not isinstance(risks, list):
            return ["risk_assessment 必须为数组"]
        for idx, item in enumerate(risks[:50]):
            if not isinstance(item, dict):
                errors.append(f"risk_assessment[{idx}] 必须为 object")
                continue
            for key in ["clause_id", "risk_score", "risk_description", "legal_basis", "affected_party"]:
                if item.get(key) in [None, ""]:
                    errors.append(f"risk_assessment[{idx}] 缺少字段：{key}")
            score = item.get("risk_score")
            if not isinstance(score, (int, float)) or score < 0 or score > 10:
                errors.append(f"risk_assessment[{idx}].risk_score 必须为 0-10 数字")
    elif agent_name == "he-gui-jian-cha":
        check = parsed.get("compliance_check", {})
        if not isinstance(check, dict):
            return ["compliance_check 必须为 object"]
        for key in ["overall_status", "applicable_laws", "passed", "failed", "invalid_clauses"]:
            if key not in check:
                errors.append(f"compliance_check 缺少字段：{key}")
    elif agent_name == "yi-wu-jie-xi":
        for key in ["timeline", "party_a_obligations", "party_b_obligations"]:
            if not isinstance(parsed.get(key), list):
                errors.append(f"{key} 必须为数组")
    elif agent_name == "jian-yi-yin-qing":
        recs = parsed.get("recommendations", [])
        if not isinstance(recs, list):
            return ["recommendations 必须为数组"]
        for idx, item in enumerate(recs[:50]):
            if not isinstance(item, dict):
                errors.append(f"recommendations[{idx}] 必须为 object")
                continue
            for key in ["priority", "clause_id", "problem", "legal_basis"]:
                if item.get(key) in [None, ""]:
                    errors.append(f"recommendations[{idx}] 缺少字段：{key}")
            if not item.get("suggested_text") and not item.get("no_text_reason"):
                errors.append(f"recommendations[{idx}] 需提供 suggested_text 或 no_text_reason")
    return errors


def party_core(label: str) -> str:
    return re.sub(r"（.*?）|\(.*?\)|\[|\]|【|】|\s+", "", label or "")


def validate_party_stance(text: str, party: str) -> dict:
    det = detect_type(text)
    party_clean = normalize_space(party)
    if party_clean == "平衡分析":
        return {"valid": True, "detected": asdict(det), "message": "平衡分析无需具体当事方。"}

    identified = [p for p in det.identified_parties if p != "平衡分析"]
    concrete_cores = [party_core(p) for p in identified]
    party_norm = party_core(party_clean)

    if identified:
        # 先做模糊匹配：当用户输入的缩称（如"投资方"）包含在某个已识别当事方的括注中时也应视为有效。
        # 例如："投资方" 可以匹配 "上海云玡企业管理咨询有限公司（投资方）"。
        matched = any(party_norm and (party_norm in core or core in party_norm) for core in concrete_cores)
        if matched:
            return {"valid": True, "detected": asdict(det), "message": "审查立场已通过校验。"}

        # 模糊匹配失败时，再判断是否属于无法定位的泛称。
        if party_clean in GENERIC_PARTY_TERMS:
            return {
                "valid": False,
                "detected": asdict(det),
                "message": "已识别到具体当事方，不得使用泛称作为审查立场。",
                "available_parties": det.available_parties,
            }

        # 模糊匹配失败且不是泛称（可能是手工输入的名称不完整）。
        return {
            "valid": False,
            "detected": asdict(det),
            "message": "审查立场未匹配到合同中的具体当事方。",
            "available_parties": det.available_parties,
        }

    # 合同未提取到具体当事方：只对明显泛称做最低限度拦截。
    if party_clean in GENERIC_PARTY_TERMS:
        return {
            "valid": False,
            "detected": asdict(det),
            "message": "未能从合同中提取具体当事方，请提供更明确的立场名称（如公司全称或协议中使用的缩称）。",
            "available_parties": det.available_parties,
        }

    return {"valid": True, "detected": asdict(det), "message": "审查立场已通过校验。"}


def validate_citations(text: str, pkulaw_policy: str = "local") -> list:
    if check_legal_citations is not None:
        result = check_legal_citations(text, pkulaw_policy=pkulaw_policy)
        return [
            item for item in result.get("findings", [])
            if item.get("status") in ["deprecated", "stale", "unknown", "topic_mismatch"]
        ]

    warnings = []
    for law in DEPRECATED_LAWS:
        if f"《{law}》" in text:
            warnings.append(f"引用已废止或已被民法典整合的法律：{law}")

    citation_pattern = re.compile(r"《([^》]{2,30})》([^第\n。；;]{0,12})(?!第)")
    for m in citation_pattern.finditer(text):
        law = m.group(1)
        tail = m.group(2)
        if "法" in law and "第" not in tail:
            warnings.append(f"疑似缺少具体条文号：{law}")
    return sorted(set(warnings))


def keyword_hits(keywords: list[str], text: str) -> list[str]:
    return [kw for kw in keywords if kw and kw in text]


def summarize_review_topics(entry: dict, contract_text: str = "") -> dict:
    """
    根据触发词/排除词激活议题驱动审查清单。
    该判断只负责提示深入审查，不直接生成法律结论。
    """
    topics = entry.get("review_topics", [])
    if not topics:
        return {
            "active_topics": [],
            "suppressed_topics": [],
            "confirmation_questions": [],
        }

    text_sample = contract_text[:50000] if contract_text else ""
    active_topics = []
    suppressed_topics = []
    confirmation_questions: list[str] = []

    for topic in topics:
        triggers = keyword_hits(topic.get("trigger_keywords", []), text_sample)
        exclusions = keyword_hits(topic.get("exclusion_keywords", []), text_sample)
        if not text_sample:
            status = "baseline"
        elif triggers and exclusions:
            status = "triggered_with_exclusion"
        elif triggers:
            status = "triggered"
        else:
            status = "not_triggered"

        topic_summary = {
            "id": topic.get("id", ""),
            "name": topic.get("name", ""),
            "category": topic.get("category", ""),
            "status": status,
            "law_ids": topic.get("law_ids", []),
            "matched_keywords": triggers,
            "matched_exclusion_keywords": exclusions,
            "review_questions": topic.get("review_questions", []),
            "confirmation_questions": topic.get("confirmation_questions", []),
            "output_guidance": topic.get("output_guidance", ""),
        }

        if status in ["baseline", "triggered", "triggered_with_exclusion"]:
            active_topics.append(topic_summary)
            for question in topic_summary["confirmation_questions"]:
                if question not in confirmation_questions:
                    confirmation_questions.append(question)
        elif exclusions:
            suppressed_topics.append(topic_summary)

    return {
        "active_topics": active_topics,
        "suppressed_topics": suppressed_topics,
        "confirmation_questions": confirmation_questions,
    }


def load_legal_coverage(contract_type: str, contract_text: str = "") -> dict:
    """
    读取合同类型法条覆盖矩阵，作为 Agent 分析前的法律依据基线。
    失败时只返回 error，不阻断审查主流程。
    """
    matrix_path = KNOWLEDGE_DIR / "coverage_matrix.json"
    citations_path = KNOWLEDGE_DIR / "citations.json"
    try:
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
        citations_data = json.loads(citations_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        return {"status": "missing", "error": f"法条覆盖矩阵或法条库不存在：{exc}"}
    except json.JSONDecodeError as exc:
        return {"status": "invalid", "error": f"法条覆盖矩阵或法条库 JSON 无法解析：{exc}"}

    contract_types = matrix.get("contract_types", {})
    selected_type = contract_type if contract_type in contract_types else "通用"
    entry = contract_types.get(selected_type)
    if not entry:
        return {"status": "missing", "error": "未找到通用法条覆盖基线。"}

    citation_index = {item.get("id"): item for item in citations_data.get("citations", [])}
    required_ids = entry.get("required_citation_ids", [])
    missing_ids = [item_id for item_id in required_ids if item_id not in citation_index]
    required_citations = []
    for item_id in required_ids:
        item = citation_index.get(item_id)
        if not item:
            continue
        required_citations.append({
            "id": item.get("id", ""),
            "law": item.get("law", ""),
            "article": item.get("article", ""),
            "title": item.get("title", ""),
        })

    topic_summary = summarize_review_topics(entry, contract_text)

    return {
        "status": "matched" if selected_type == contract_type else "fallback",
        "contract_type": selected_type,
        "core_laws": entry.get("core_laws", []),
        "required_citation_ids": required_ids,
        "required_citations": required_citations,
        "conditional_topics": entry.get("conditional_topics", {}),
        "review_topics": entry.get("review_topics", []),
        "active_review_topics": topic_summary["active_topics"],
        "suppressed_review_topics": topic_summary["suppressed_topics"],
        "confirmation_questions": topic_summary["confirmation_questions"],
        "missing_required_ids": missing_ids,
        "instruction": "审查该类型合同时，应优先检查基础法条覆盖；条件议题和审查议题仅在合同文本或交易背景触发时适用。触发词只提示深入审查，不直接构成违法或重大风险结论；confirmation_questions 应作为需向业务确认事项输出。",
    }


def load_risk_calibration_policy() -> dict:
    path = KNOWLEDGE_DIR / "risk_calibration.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "score_bands": [],
            "major_risk_factors": [],
            "downgrade_signals": [],
            "rules": [],
        }


def text_from_agent_results(agent_results: list[AgentResult]) -> str:
    parts = []
    for result in agent_results:
        if result.content:
            parts.append(result.content)
        elif result.parsed:
            parts.append(json.dumps(result.parsed, ensure_ascii=False))
    return "\n".join(parts)


def base_risk_level(score: Optional[int], policy: dict) -> dict:
    if score is None:
        return {
            "level": "需人工判断",
            "band": "unknown",
            "description": "部分 Agent 未能输出可计算分数，需人工复核。",
        }
    bands = sorted(policy.get("score_bands", []), key=lambda item: item.get("min_score", 0), reverse=True)
    for band in bands:
        if score >= int(band.get("min_score", 0)):
            return {
                "level": band.get("level", "需人工判断"),
                "band": band.get("level", ""),
                "description": band.get("description", ""),
            }
    return {"level": "需人工判断", "band": "unknown", "description": ""}


def calibrate_risk_level(score: Optional[int], legal_coverage: dict, agent_results: list[AgentResult]) -> dict:
    """
    将模型分数校准为律师报告用风险等级。
    重点防止将普通争议、对方可能挑战、对委托方有利保护性条款误判为重大风险。
    """
    policy = load_risk_calibration_policy()
    base = base_risk_level(score, policy)
    result_text = text_from_agent_results(agent_results)
    active_topics = legal_coverage.get("active_review_topics", [])
    active_topic_text = json.dumps(active_topics, ensure_ascii=False)
    combined_text = "\n".join([result_text, active_topic_text])

    major_factors = []
    for factor in policy.get("major_risk_factors", []):
        hits = [kw for kw in factor.get("keywords", []) if kw and kw in combined_text]
        if hits:
            major_factors.append({
                "id": factor.get("id", ""),
                "name": factor.get("name", ""),
                "matched_keywords": hits[:8],
            })

    downgrade_hits = [kw for kw in policy.get("downgrade_signals", []) if kw and kw in combined_text]
    confirmation_questions = legal_coverage.get("confirmation_questions", [])

    final_level = base["level"]
    adjustment = "none"
    if base["level"] == "重大风险候选":
        if major_factors:
            final_level = "重大风险"
            adjustment = "confirmed_major_factor"
        else:
            final_level = "中等风险"
            adjustment = "downgraded_no_major_factor"
    elif base["level"] == "高度风险" and not major_factors:
        final_level = "重大风险"
        adjustment = "downgraded_from_high_without_major_factor"

    return {
        "score": score,
        "base_level": base["level"],
        "final_level": final_level,
        "adjustment": adjustment,
        "major_factors": major_factors,
        "downgrade_signals": downgrade_hits[:10],
        "confirmation_question_count": len(confirmation_questions),
        "rules": policy.get("rules", []),
        "instruction": "报告风险评级应优先使用 final_level。重大风险必须能对应 major_factors；若仅有 downgrade_signals，应避免直接写成重大风险。",
    }


def compact_agent_result(result: AgentResult) -> dict:
    parsed = result.parsed or {}
    if result.agent_name == "tiao-kuan-fen-xi":
        clauses = parsed.get("clauses", [])
        return {
            "basic_info": parsed.get("basic_info", {}),
            "total_clauses": parsed.get("total_clauses", len(clauses) if isinstance(clauses, list) else 0),
            "clauses": clauses[:80] if isinstance(clauses, list) else [],
        }
    if result.agent_name == "feng-xian-ping-gu":
        risks = parsed.get("risk_assessment", [])
        if isinstance(risks, list):
            risks = sorted(risks, key=lambda x: x.get("risk_score", 0) if isinstance(x, dict) else 0, reverse=True)[:20]
        return {
            "overall_risk_score": parsed.get("overall_risk_score"),
            "high_risk_count": parsed.get("high_risk_count"),
            "medium_risk_count": parsed.get("medium_risk_count"),
            "top_risks": risks,
        }
    if result.agent_name == "he-gui-jian-cha":
        check = parsed.get("compliance_check", {})
        if isinstance(check, dict):
            return {
                "overall_status": check.get("overall_status"),
                "applicable_laws": check.get("applicable_laws", []),
                "failed": check.get("failed", []),
                "invalid_clauses": check.get("invalid_clauses", []),
            }
    if result.agent_name == "yi-wu-jie-xi":
        return {
            "timeline": parsed.get("timeline", [])[:30] if isinstance(parsed.get("timeline"), list) else [],
            "party_a_obligations": parsed.get("party_a_obligations", [])[:30] if isinstance(parsed.get("party_a_obligations"), list) else [],
            "party_b_obligations": parsed.get("party_b_obligations", [])[:30] if isinstance(parsed.get("party_b_obligations"), list) else [],
            "imbalance_flags": parsed.get("imbalance_flags", []),
            "key_deadlines_summary": parsed.get("key_deadlines_summary", ""),
        }
    if result.agent_name == "jian-yi-yin-qing":
        return {
            "must_fix_count": parsed.get("must_fix_count"),
            "strongly_recommended_count": parsed.get("strongly_recommended_count"),
            "optional_count": parsed.get("optional_count"),
            "recommendations": parsed.get("recommendations", [])[:30] if isinstance(parsed.get("recommendations"), list) else [],
        }
    return parsed


def build_upstream_context(
    completed: dict,           # {agent_name: AgentResult} 已完成的结果
    dependencies: list,        # 需要注入的上游 agent 名称列表
) -> str:
    """
    将上游 Agent 的输出格式化为下游 Agent 的上下文片段。
    只注入成功的结果；失败的 Agent 跳过并附加说明。
    """
    if not dependencies:
        return ""

    sections = []
    for dep in dependencies:
        result = completed.get(dep)
        if result is None:
            sections.append(f"### {dep}\n[未执行，跳过]")
        elif not result.success:
            sections.append(f"### {dep}\n[执行失败：{result.error}，跳过]")
        else:
            content = json.dumps(compact_agent_result(result), ensure_ascii=False, indent=2)
            sections.append(f"### {dep} 的分析输出\n```json\n{content}\n```")

    return "## 上游 Agent 输出\n\n" + "\n\n".join(sections)


async def call_agent(
    client: AsyncAnthropic,
    agent_name: str,
    agents_dir: Path,
    contract_text: str,
    session_ctx: dict,
    context_content: str,
    guidelines: str,
    upstream_results: Optional[dict] = None,   # {agent_name: AgentResult}
    upstream_deps: Optional[list]   = None,    # 需要注入的依赖名称
) -> AgentResult:
    """
    每个 Agent 是一次独立的 API 调用，有独立的系统提示和上下文。

    上下文注入顺序（系统提示）：
      公共指南 → 专项 context → Agent 自身 prompt

    用户消息：
      session_context → 上游 Agent 输出（如有）→ 合同全文

    失败时返回 AgentResult(success=False)，不抛出异常（Factor 9）。
    """
    agent_file = agents_dir / f"{agent_name}.md"
    agent_prompt = load_file(agent_file, label=agent_name)
    if not agent_prompt:
        return AgentResult(
            agent_name=agent_name, success=False, content="", parsed=None,
            elapsed_seconds=0, error=f"Agent 文件不存在：{agent_file}"
        )

    # 系统提示：公共规范 + 领域知识 + Agent 专属指令
    system = "\n\n---\n\n".join(filter(None, [
        guidelines,
        context_content,
        agent_prompt,
    ]))

    # 构建上游输出注入（如有依赖）
    upstream_section = ""
    if upstream_results and upstream_deps:
        upstream_section = build_upstream_context(upstream_results, upstream_deps)

    # 用户消息：分析上下文 + 上游输出 + 合同全文
    user_msg = "\n\n".join(filter(None, [
        f"## 分析上下文\n```json\n{json.dumps(session_ctx, ensure_ascii=False, indent=2)}\n```",
        upstream_section,
        f"## 合同全文\n{contract_text}",
        "请严格按照你的输出格式（JSON schema）返回结果。",
    ]))

    t0 = time.time()
    try:
        messages = [{"role": "user", "content": user_msg}]
        content = ""
        parsed = None
        validation_errors = []

        for attempt in range(2):
            resp = await client.messages.create(
                model=DEFAULT_MODEL,
                max_tokens=4096,
                system=system,
                messages=messages,
            )
            content = resp.content[0].text
            parsed = extract_json_object(content)
            validation_errors = validate_agent_output(agent_name, parsed)
            if not validation_errors:
                break
            if attempt == 0:
                messages.extend([
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": (
                            "你的上一次输出未通过结构校验："
                            + "；".join(validation_errors)
                            + "。请只返回一个合法 JSON object，并补齐指定顶层字段；不要输出解释文字。"
                        ),
                    },
                ])

        citation_warnings = validate_citations(content, session_ctx.get("pkulaw_policy", "local"))
        success = not validation_errors and parsed is not None
        return AgentResult(
            agent_name=agent_name,
            success=success,
            content=content,
            parsed=parsed,
            elapsed_seconds=round(time.time() - t0, 2),
            error=None if success else "；".join(validation_errors),
            validation_errors=validation_errors,
            citation_warnings=citation_warnings,
        )
    except Exception as e:
        return AgentResult(
            agent_name=agent_name, success=False, content="", parsed=None,
            elapsed_seconds=round(time.time() - t0, 2), error=str(e),
        )


def safe_len(value) -> int:
    return len(value) if isinstance(value, list) else 0


def score_agent_component(result: AgentResult) -> Optional[int]:
    if not result.success or not result.parsed:
        return None
    p = result.parsed
    if result.agent_name == "feng-xian-ping-gu":
        raw = p.get("overall_risk_score")
        if isinstance(raw, (int, float)):
            return max(0, min(100, int(100 - raw * 10)))
        high = p.get("high_risk_count", 0) or 0
        medium = p.get("medium_risk_count", 0) or 0
        return max(0, min(100, 90 - int(high) * 18 - int(medium) * 8))
    if result.agent_name == "he-gui-jian-cha":
        check = p.get("compliance_check", {})
        if not isinstance(check, dict):
            return 70
        failed = safe_len(check.get("failed"))
        invalid = safe_len(check.get("invalid_clauses"))
        # 用枚举映射，不再依赖"不"字出现与否
        _STATUS_SCORES = {
            "合规": 92, "compliant": 92,
            "部分合规": 78, "partial": 78, "partial_compliant": 78,
            "不合规": 60, "non_compliant": 60, "noncompliant": 60,
        }
        status_raw = str(check.get("overall_status", "")).strip()
        base = _STATUS_SCORES.get(status_raw, 76)  # 未知状态默认 76
        return max(0, min(100, base - failed * 8 - invalid * 15))
    if result.agent_name == "jian-yi-yin-qing":
        must = p.get("must_fix_count", 0) or 0
        strong = p.get("strongly_recommended_count", 0) or 0
        optional = p.get("optional_count", 0) or 0
        return max(0, min(100, 92 - int(must) * 12 - int(strong) * 6 - int(optional) * 2))
    if result.agent_name == "tiao-kuan-fen-xi":
        clauses = p.get("clauses", [])
        return 90 if isinstance(clauses, list) and clauses else 72
    if result.agent_name == "yi-wu-jie-xi":
        imbalance = safe_len(p.get("imbalance_flags"))
        return max(0, min(100, 88 - imbalance * 5))
    return None


def extract_risk_score(agent_results: list[AgentResult]) -> Optional[int]:
    """
    综合五个 Agent 的分数，按 AGENT_WEIGHTS 加权。
    失败 Agent 不参与权重归一，但每个失败 Agent 额外扣 3 分，避免“少分析反而高分”。
    """
    weighted_total = 0.0
    weight_sum = 0.0
    failed = 0
    for r in agent_results:
        component = score_agent_component(r)
        weight = AGENT_WEIGHTS.get(r.agent_name, 0)
        if component is None:
            failed += 1
            continue
        weighted_total += component * weight
        weight_sum += weight
    if weight_sum == 0:
        return None
    score = int(round(weighted_total / weight_sum)) - failed * 3
    return max(0, min(100, score))


# ── 子命令：detect ────────────────────────────────────────────────────────

def cmd_detect(args):
    """
    纯代码的合同类型识别，无 LLM 调用。
    输出 JSON 供 SKILL.md 读取，决定是否需要用户确认。
    """
    contract_path = Path(args.contract).expanduser()
    if not contract_path.exists():
        result = {"error": f"文件不存在：{contract_path}"}
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    text = load_file(contract_path)
    det  = detect_type(text)

    output = {
        "contract_type":     det.contract_type,
        "confidence":        det.confidence,
        "matched_keywords":  det.matched_keywords,
        "available_parties": det.available_parties,
        "identified_parties": det.identified_parties,
        "is_multipartite":   det.is_multipartite,
        "title_hint":        det.title_hint,
        "context_file":      det.context_file,
        # 给 SKILL.md 用的展示消息
        "message": (
            f"已识别为【{det.contract_type}】（依据：{', '.join(det.matched_keywords[:3])}）"
            if det.confidence == "HIGH"
            else f"推断为【{det.contract_type}】（置信度：{det.confidence}），请确认"
            if det.confidence == "MEDIUM"
            else "未能自动识别合同类型，请手动选择"
        ),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


def cmd_validate_party(args):
    contract_path = Path(args.contract).expanduser()
    if not contract_path.exists():
        print(json.dumps({"valid": False, "error": f"文件不存在：{contract_path}"}, ensure_ascii=False))
        sys.exit(1)
    result = validate_party_stance(load_file(contract_path), args.party)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("valid"):
        sys.exit(1)


# ── 子命令：analyze ────────────────────────────────────────────────────────

def cmd_analyze(args):
    """
    运行五个 Agent 的并发分析，结果写入 JSON 文件。
    Claude Code 的 SKILL.md 读取此 JSON 来格式化报告。
    """
    asyncio.run(_run_analyze(args))


async def _run_analyze(args):
    if AsyncAnthropic is None:
        print(json.dumps({"error": "未安装 anthropic，无法运行 analyze。请先执行：pip3 install anthropic"}, ensure_ascii=False))
        sys.exit(1)

    agents_dir    = Path(args.agents_dir).expanduser()
    contract_path = Path(args.contract).expanduser()
    output_path   = Path(args.output).expanduser()

    # ── 读合同 ──────────────────────────────────────────────────────────
    if not contract_path.exists():
        print(json.dumps({"error": f"合同文件不存在：{contract_path}"}, ensure_ascii=False))
        sys.exit(1)

    contract_text = load_file(contract_path, label="合同文件")
    if not contract_text:
        print(json.dumps({"error": "合同文件为空或无法读取"}, ensure_ascii=False))
        sys.exit(1)

    party_validation = validate_party_stance(contract_text, args.party)
    if not party_validation.get("valid"):
        print(json.dumps({
            "error": "审查立场未通过校验",
            "message": party_validation.get("message"),
            "available_parties": party_validation.get("available_parties", []),
        }, ensure_ascii=False))
        sys.exit(1)

    # ── 加载公共资源 ──────────────────────────────────────────────────────
    guidelines      = load_file(agents_dir / "_guidelines.md",             "公共指南")
    context_content = load_file(agents_dir / "context" / args.context_file, "专项上下文")

    # ── 构建 session_context ─────────────────────────────────────────────
    review_mode = "平衡分析" if args.party == "平衡分析" else "单方委托"
    legal_coverage = load_legal_coverage(args.type, contract_text)
    risk_calibration_policy = load_risk_calibration_policy()
    session_ctx = {
        "contract_type":  args.type,
        "party_stance":   args.party,
        "review_mode":    review_mode,
        "context_file":   args.context_file,
        "legal_coverage": legal_coverage,
        "risk_calibration_policy": risk_calibration_policy,
        "pkulaw_policy": args.pkulaw_policy,
        "strictness": {
            "for_client_party": "严格" if review_mode == "单方委托" else "一般",
            "for_counterparty": "一般",
        },
    }

    # ── 按 DAG 分阶段执行 ─────────────────────────────────────────────────────
    #
    #  Phase 1 (单独): tiao-kuan-fen-xi
    #  Phase 2 (并发): feng-xian-ping-gu | he-gui-jian-cha | yi-wu-jie-xi
    #                  ← 均接收 Phase 1 输出
    #  Phase 3 (单独): jian-yi-yin-qing
    #                  ← 接收 Phase 2 的 feng + he 输出
    #
    client    = AsyncAnthropic()
    t0        = time.time()
    completed = {}   # {agent_name: AgentResult}，跨 Phase 累积

    print(f"🔍 开始分析：{args.type}（{args.party}）", file=sys.stderr)

    for phase_cfg in AGENT_PHASES:
        phase_num   = phase_cfg["phase"]
        phase_label = phase_cfg["label"]
        agents      = phase_cfg["agents"]
        deps        = phase_cfg["upstream"]

        # 上游有失败时给出警告，但继续执行（Factor 9）
        failed_deps = [d for d in deps if d in completed and not completed[d].success]
        if failed_deps:
            print(f"  ⚠️  Phase {phase_num} 的上游 {failed_deps} 失败，将缺少依赖上下文",
                  file=sys.stderr)

        print(f"\n  ▶ Phase {phase_num}：{phase_label}（{len(agents)} 个）", file=sys.stderr)
        phase_t0 = time.time()

        tasks = [
            call_agent(
                client, name, agents_dir,
                contract_text, session_ctx, context_content, guidelines,
                upstream_results = completed if deps else None,
                upstream_deps    = deps      if deps else None,
            )
            for name in agents
        ]
        # Phase 内真并发，Phase 间有序（保证依赖）
        phase_results = await asyncio.gather(*tasks)

        for r in phase_results:
            completed[r.agent_name] = r
            status   = "✓" if r.success else "✗"
            dep_note = f"<- [{', '.join(deps)}]" if deps else ""
            print(f"    {status} {r.agent_name} {dep_note} ({r.elapsed_seconds}s)", file=sys.stderr)

        phase_elapsed = round(time.time() - phase_t0, 2)
        print(f"    Phase {phase_num} 完成（{phase_elapsed}s）", file=sys.stderr)

    results = list(completed.values())
    elapsed = round(time.time() - t0, 2)

    # ── 汇总结果 ───────────────────────────────────────────────────────────────
    passed  = [r for r in results if r.success]
    skipped = [r.agent_name for r in results if not r.success]

    if skipped:
        print(f"\n⚠️  跳过的 Agent：{skipped}", file=sys.stderr)

    overall_score = extract_risk_score(results)
    risk_calibration = calibrate_risk_level(overall_score, legal_coverage, results)
    citation_warnings = []
    for r in results:
        for warning in r.citation_warnings:
            citation_warnings.append({"agent": r.agent_name, "warning": warning})
    security_preflight = {}
    if args.security_preflight:
        preflight_path = Path(args.security_preflight).expanduser()
        if preflight_path.exists():
            try:
                security_preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                security_preflight = {"error": f"无法解析预检结果：{preflight_path}"}

    usage_log_result = {"status": "disabled"}

    # 提取项目名称（供报告命名用）
    project_name = re.sub(
        r'(有限公司|股份有限公司|INC\.|LLC|LTD\.?)', '',
        args.type
    ).strip() or args.type

    analysis = AnalysisResults(
        project_name    = project_name,
        contract_type   = args.type,
        party_stance    = args.party,
        review_mode     = review_mode,
        overall_score   = overall_score,
        risk_calibration = risk_calibration,
        agent_results   = [asdict(r) for r in results],
        skipped_agents  = skipped,
        citation_warnings = citation_warnings,
        legal_coverage  = legal_coverage,
        security_preflight = security_preflight,
        usage_log       = usage_log_result,
        guidelines      = guidelines,
        context_content = context_content,
        elapsed_total   = elapsed,
    )

    if append_usage_event is not None and build_usage_event is not None:
        try:
            event = build_usage_event(asdict(analysis), contract_text)
            log_path = DEFAULT_USAGE_LOG or (KNOWLEDGE_DIR.parent / "logs" / "usage_events.jsonl")
            append_usage_event(event, Path(log_path))
            usage_log_result = {
                "status": "recorded",
                "event_id": event.get("event_id", ""),
                "log_path": str(log_path),
            }
            analysis.usage_log = usage_log_result
        except Exception as exc:
            usage_log_result = {"status": "error", "message": str(exc)}
            analysis.usage_log = usage_log_result

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(asdict(analysis), f, ensure_ascii=False, indent=2)

    print(f"\n✅ 分析完成（{elapsed}s）→ {output_path}", file=sys.stderr)
    # 向 stdout 输出摘要供 SKILL.md 展示
    print(json.dumps({
        "status":        "ok",
        "overall_score": overall_score,
        "risk_level":    risk_calibration.get("final_level", ""),
        "risk_adjustment": risk_calibration.get("adjustment", ""),
        "passed":        len(passed),
        "skipped":       skipped,
        "output_file":   str(output_path),
        "elapsed":       elapsed,
    }, ensure_ascii=False))


# ── CLI ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="中国法律 AI Agent — 核心分析管道",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", metavar="<子命令>")

    # detect
    p_det = sub.add_parser("detect", help="识别合同类型（无 LLM，纯代码）")
    p_det.add_argument("--contract", required=True, help="合同文件路径（TXT/MD）")

    # validate-party
    p_party = sub.add_parser("validate-party", help="校验审查立场是否为合同具体当事方（无 LLM）")
    p_party.add_argument("--contract", required=True, help="合同文件路径（TXT/MD）")
    p_party.add_argument("--party", required=True, help="审查立场")

    # analyze
    p_ana = sub.add_parser("analyze", help="并发调用 5 个 Agent 完成审查")
    p_ana.add_argument("--contract",     required=True, help="合同文件路径")
    p_ana.add_argument("--type",         required=True, help="合同类型（如：投资协议）")
    p_ana.add_argument("--party",        required=True, help="审查立场（如：投资方）")
    p_ana.add_argument("--context-file", default="general.md",
                       help="专项 context 文件名（如：investment.md）")
    p_ana.add_argument("--agents-dir",   default=str(DEFAULT_AGENTS_DIR),
                       help="agents 目录路径")
    p_ana.add_argument("--output",       default="/tmp/falv_results.json",
                       help="分析结果 JSON 输出路径")
    p_ana.add_argument("--security-preflight", default="",
                       help="security_preflight.py 输出的 JSON 文件路径（可选）")
    p_ana.add_argument("--pkulaw-policy", choices=["local", "on-demand", "always"], default="local",
                       help="法条上游校验策略：local=只查本地；on-demand=必要时调用北大法宝；always=所有引用均调用北大法宝")

    args = parser.parse_args()

    if args.command == "detect":
        cmd_detect(args)
    elif args.command == "validate-party":
        cmd_validate_party(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

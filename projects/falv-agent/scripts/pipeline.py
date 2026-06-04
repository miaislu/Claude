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

from anthropic import AsyncAnthropic


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
                     "处理目的", "数据主体"],
        "context":  "data.md",
        "parties":  ["委托方（数据控制者）", "受托方（处理者）", "平衡分析"],
    },
    "电商平台服务协议": {
        "keywords": ["平台", "入驻", "店铺", "保证金", "佣金", "技术服务费", "商家", "运营规则"],
        "context":  "ecommerce-service.md",
        "parties":  ["商家（入驻方）", "平台方", "平衡分析"],
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

AGENT_NAMES = [
    "tiao-kuan-fen-xi",
    "feng-xian-ping-gu",
    "he-gui-jian-cha",
    "yi-wu-jie-xi",
    "jian-yi-yin-qing",
]

AGENT_WEIGHTS = {
    "tiao-kuan-fen-xi": 0.20,
    "feng-xian-ping-gu": 0.25,
    "he-gui-jian-cha":   0.20,
    "yi-wu-jie-xi":      0.15,
    "jian-yi-yin-qing":  0.20,
}

DEFAULT_AGENTS_DIR = Path("~/.claude/agents").expanduser()
DEFAULT_MODEL       = "claude-opus-4-5"


# ── 数据结构 ──────────────────────────────────────────────────────────────
@dataclass
class DetectResult:
    contract_type: str
    confidence: str           # "HIGH" | "MEDIUM" | "LOW"
    matched_keywords: list
    available_parties: list
    context_file: str


@dataclass
class AgentResult:
    agent_name: str
    success: bool
    content: str              # 原始文本（JSON 或自然语言）
    parsed: Optional[dict]    # 尝试 JSON 解析后的结果
    elapsed_seconds: float
    error: Optional[str] = None


@dataclass
class AnalysisResults:
    project_name: str
    contract_type: str
    party_stance: str
    review_mode: str
    overall_score: Optional[int]
    agent_results: list       # List[AgentResult as dict]
    skipped_agents: list      # 失败的 Agent 名称
    guidelines: str           # _guidelines.md 内容（提供给 Claude 格式化用）
    context_content: str      # 专项 context 文件内容
    elapsed_total: float


# ── 核心函数 ──────────────────────────────────────────────────────────────

def detect_type(text: str) -> DetectResult:
    """
    纯代码的合同类型识别。
    计算每种类型的关键词命中数，返回置信度分级结果。
    这是从 SKILL.md 迁移到 Python 的第一步（Factor 8）。
    """
    text_sample = text[:5000]  # 只扫开头 5000 字，足够识别类型
    scores = {}
    matched = {}
    for ctype, cfg in ROUTING.items():
        hits = [kw for kw in cfg["keywords"] if kw in text_sample]
        scores[ctype] = len(hits)
        matched[ctype] = hits

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]

    if best_score >= 3:
        confidence = "HIGH"
    elif best_score >= 1:
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

    return DetectResult(
        contract_type     = best_type,
        confidence        = confidence,
        matched_keywords  = matched.get(best_type, []),
        available_parties = parties,
        context_file      = context_file,
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


async def call_agent(
    client: AsyncAnthropic,
    agent_name: str,
    agents_dir: Path,
    contract_text: str,
    session_ctx: dict,
    context_content: str,
    guidelines: str,
) -> AgentResult:
    """
    每个 Agent 是一次独立的 API 调用，有独立的系统提示和上下文。
    失败时返回 AgentResult(success=False)，不抛出异常（Factor 9）。
    """
    agent_file = agents_dir / f"{agent_name}.md"
    agent_prompt = load_file(agent_file, label=agent_name)
    if not agent_prompt:
        return AgentResult(
            agent_name=agent_name, success=False, content="", parsed=None,
            elapsed_seconds=0, error=f"Agent 文件不存在：{agent_file}"
        )

    system = "\n\n---\n\n".join(filter(None, [
        guidelines,
        context_content,
        agent_prompt,
    ]))

    user_msg = (
        f"## 分析上下文\n```json\n{json.dumps(session_ctx, ensure_ascii=False, indent=2)}\n```\n\n"
        f"## 合同全文\n{contract_text}\n\n"
        f"请严格按照你的输出格式（JSON schema）返回结果。"
    )

    t0 = time.time()
    try:
        resp = await client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
        content = resp.content[0].text
        # 尝试解析 JSON（提取第一个 {...} 块）
        parsed = None
        m = re.search(r'\{[\s\S]+\}', content)
        if m:
            try:
                parsed = json.loads(m.group())
            except json.JSONDecodeError:
                pass  # 解析失败没关系，保留原始文本

        return AgentResult(
            agent_name=agent_name, success=True, content=content, parsed=parsed,
            elapsed_seconds=round(time.time() - t0, 2),
        )
    except Exception as e:
        return AgentResult(
            agent_name=agent_name, success=False, content="", parsed=None,
            elapsed_seconds=round(time.time() - t0, 2), error=str(e),
        )


def extract_risk_score(agent_results: list[AgentResult]) -> Optional[int]:
    """
    从风险评估师的输出中提取 overall_risk_score，
    换算为 0-100 的合同安全评分（风险越高，评分越低）。
    """
    for r in agent_results:
        if r.agent_name == "feng-xian-ping-gu" and r.parsed:
            raw = r.parsed.get("overall_risk_score")
            if isinstance(raw, (int, float)):
                # risk_score 是 0-10（10=最高风险），转为 0-100 安全评分
                return max(0, min(100, int(100 - raw * 10)))
    return None


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


# ── 子命令：analyze ────────────────────────────────────────────────────────

def cmd_analyze(args):
    """
    运行五个 Agent 的并发分析，结果写入 JSON 文件。
    Claude Code 的 SKILL.md 读取此 JSON 来格式化报告。
    """
    asyncio.run(_run_analyze(args))


async def _run_analyze(args):
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

    # ── 加载公共资源 ──────────────────────────────────────────────────────
    guidelines      = load_file(agents_dir / "_guidelines.md",             "公共指南")
    context_content = load_file(agents_dir / "context" / args.context_file, "专项上下文")

    # ── 构建 session_context ─────────────────────────────────────────────
    review_mode = "平衡分析" if args.party == "平衡分析" else "单方委托"
    session_ctx = {
        "contract_type":  args.type,
        "party_stance":   args.party,
        "review_mode":    review_mode,
        "context_file":   args.context_file,
        "strictness": {
            "for_client_party": "严格" if review_mode == "单方委托" else "一般",
            "for_counterparty": "一般",
        },
    }

    # ── 并发调用五个 Agent ────────────────────────────────────────────────
    client = AsyncAnthropic()  # 从 ANTHROPIC_API_KEY 环境变量读取
    t0     = time.time()

    print(f"🔍 开始分析：{args.type}（{args.party}）", file=sys.stderr)
    print(f"📋 并发调用 {len(AGENT_NAMES)} 个 Agent...", file=sys.stderr)

    tasks = [
        call_agent(client, name, agents_dir, contract_text, session_ctx,
                   context_content, guidelines)
        for name in AGENT_NAMES
    ]
    results: list[AgentResult] = await asyncio.gather(*tasks)

    elapsed = round(time.time() - t0, 2)

    # ── 汇总结果 ──────────────────────────────────────────────────────────
    passed  = [r for r in results if r.success]
    skipped = [r.agent_name for r in results if not r.success]

    if skipped:
        print(f"⚠️  {len(skipped)} 个 Agent 未返回结果：{skipped}", file=sys.stderr)
    for r in results:
        status = "✓" if r.success else "✗"
        print(f"  {status} {r.agent_name} ({r.elapsed_seconds}s)", file=sys.stderr)

    overall_score = extract_risk_score(results)

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
        agent_results   = [asdict(r) for r in results],
        skipped_agents  = skipped,
        guidelines      = guidelines,
        context_content = context_content,
        elapsed_total   = elapsed,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(asdict(analysis), f, ensure_ascii=False, indent=2)

    print(f"\n✅ 分析完成（{elapsed}s）→ {output_path}", file=sys.stderr)
    # 向 stdout 输出摘要供 SKILL.md 展示
    print(json.dumps({
        "status":        "ok",
        "overall_score": overall_score,
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

    args = parser.parse_args()

    if args.command == "detect":
        cmd_detect(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

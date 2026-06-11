"""
Meeting Preparer Agent。

会前情报打包，≤800 字 Markdown 简报 + 结构化问题清单。

支持会议类型：
  company_visit / earnings_call / roadshow / expert_call / investment_committee

两个 MCP 入口：
  prepare(code, meeting_type, ...)        — 公司级会议
  prepare_expert_call(sector, ...)        — 行业专家访谈（不需要 stock_code）
"""

from __future__ import annotations

import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore")

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from agents.base import AgentBase
from models import MeetingPrepResult, MeetingQuestion

# 问题模板
_STRATEGY_QS = [
    ("COUNTER", "如果核心增长假设不成立，downside 是多少？"),
    ("COUNTER", "为什么是现在买，而不是等下一个催化剂确认后？"),
    ("COUNTER", "最大 bear case 是什么？"),
]

_ATTENDEE_CEO_QS = [
    ("P1", "公司中长期战略方向有何调整？"),
    ("P1", "面对竞争格局变化，差异化优势如何保持？"),
]

_ATTENDEE_CFO_QS = [
    ("P1", "资本开支计划及未来 2 年的 FCF 预期？"),
    ("P1", "分红政策是否会调整？"),
    ("P1", "有息负债规模和再融资计划？"),
]

# 风险类型 → 固定自然语言问题（不内嵌 akshare 字段名或截断句子）
_FLAG_QUESTION: dict[str, str] = {
    "商誉减值":    "本期商誉减值测试结果如何？收购标的业绩承诺完成情况？",
    "现金流质量":  "经营现金流与净利润差距扩大，主要原因是什么？预计何时改善？",
    "政府补贴依赖": "剔除政府补贴后，主业盈利能力的可持续性如何？",
    "关联交易":    "关联交易的定价依据是什么？是否进行过第三方比价？",
}
_FLAG_DEFAULT = "该财务异常指标的具体原因是什么？是否已有改善计划？"


class MeetingPreparer(AgentBase):
    """会前情报打包 Agent。"""

    def prepare(
        self,
        code: str,
        meeting_type: str = "company_visit",
        meeting_time: str | None = None,
        attendees: list[str] | None = None,
        thesis: list[str] | None = None,
        fresh_window_h: float = 2,
    ) -> MeetingPrepResult:
        """
        为公司级会议生成简报。

        attendees: ["CEO", "CFO", "IR"] 等
        thesis: 覆盖 watchlist 中的默认 thesis
        """
        attendees = attendees or []
        thesis    = thesis or self._load_thesis(code)

        # 1. 读取存档
        earnings = self._load_latest(code, "earnings_review")
        model_r  = self._load_latest(code, "model_build")
        val_r    = self._load_latest(code, "valuation_review")
        market_d = self._load_latest_market()

        # 2. 实时数据
        price_data = self._get_realtime(code)

        # 3. 数据时效警告
        age_warnings = self._check_data_age(earnings, model_r)

        # 4. 生成问题清单
        questions = self._generate_questions(
            meeting_type, attendees, thesis,
            earnings, model_r, val_r, market_d, code
        )

        # 5. 生成 Markdown 简报
        brief_path = self._write_brief(
            code, meeting_type, meeting_time,
            price_data, earnings, model_r, val_r,
            questions, age_warnings
        )
        q_path = self._write_question_list(code, questions)

        # 会议时间计算
        hours_until = None
        if meeting_time:
            try:
                mt = datetime.fromisoformat(meeting_time)
                diff = (mt - datetime.now()).total_seconds() / 3600
                hours_until = round(diff, 1)
            except ValueError:
                pass

        company_name = (model_r or {}).get("company_name", code)
        return MeetingPrepResult(
            stock_code=code,
            company_name=company_name,
            meeting_type=meeting_type,
            prep_timestamp=datetime.now(timezone.utc).isoformat(),
            meeting_time=meeting_time,
            hours_until_meeting=hours_until,
            current_price=price_data.get("price"),
            price_change_1d_pct=price_data.get("1d_pct"),
            price_vs_csi300_1m_pct=price_data.get("vs_csi300_1m"),
            recent_announcements=price_data.get("announcements", []),
            thesis_health=(market_d or {}).get("thesis_status", {}).get(code, {}).get("health", "INTACT"),
            latest_verdict=(earnings or {}).get("overall_verdict", ""),
            valuation_verdict=(val_r or {}).get("verdict", ""),
            target_price=_f(model_r, "blended_target_price"),
            upside_pct=_f(model_r, "upside_pct"),
            data_age_warnings=age_warnings,
            questions=questions,
            brief_md_path=brief_path,
            question_list_md_path=q_path,
        )

    def prepare_expert_call(
        self,
        sector: str,
        focus_topics: list[str] | None = None,
        meeting_time: str | None = None,
    ) -> MeetingPrepResult:
        """
        行业专家访谈专用入口，不需要 stock_code。
        """
        focus_topics = focus_topics or []
        questions = self._generate_expert_questions(sector, focus_topics)

        brief_path = self._write_expert_brief(sector, focus_topics, questions, meeting_time)
        q_path = self._write_question_list(f"{sector}_expert", questions)

        return MeetingPrepResult(
            stock_code="",
            company_name=f"{sector}行业专家",
            meeting_type="expert_call",
            prep_timestamp=datetime.now(timezone.utc).isoformat(),
            meeting_time=meeting_time,
            questions=questions,
            brief_md_path=brief_path,
            question_list_md_path=q_path,
        )

    # ──────────────────────────────────────────
    # 问题生成（Module 2）
    # ──────────────────────────────────────────

    def _generate_questions(
        self,
        meeting_type: str,
        attendees: list[str],
        thesis: list[str],
        earnings: dict | None,
        model_r: dict | None,
        val_r: dict | None,
        market_d: dict | None,
        code: str,
    ) -> list[MeetingQuestion]:
        questions: list[MeetingQuestion] = []

        # P0：Thesis 风险必问（使用自然语言模板，不截断 evidence 字段）
        if earnings:
            for tv in (earnings.get("thesis_verdicts") or []):
                if tv.get("verdict") == "RISK":
                    kw = tv["thesis_keyword"]
                    questions.append(MeetingQuestion(
                        priority="P0",
                        question=f"「{kw}」论点出现负面信号，管理层如何解释？是否有改善预期？",
                        source="thesis_risk",
                        follow_up=f"（数据依据：{tv.get('evidence','')[:50]}）",
                    ))

        # P1：财务异常（使用固定自然语言模板，不内嵌 explanation 原文）
        if earnings:
            for rf in (earnings.get("risk_flags") or []):
                if rf.get("verdict") in ("HIGH_RISK", "MEDIUM_RISK"):
                    flag_type = rf["flag_type"]
                    q_text = _FLAG_QUESTION.get(flag_type, _FLAG_DEFAULT)
                    questions.append(MeetingQuestion(
                        priority="P1",
                        question=q_text,
                        source="risk_flag",
                    ))

        # P2：预期差追问
        if earnings:
            for gap in (earnings.get("expectation_gaps") or []):
                if gap.get("verdict") in ("MISS_STRONG", "BEAT_STRONG"):
                    direction = "低于" if "MISS" in gap["verdict"] else "超过"
                    questions.append(MeetingQuestion(
                        priority="P2",
                        question=f"{gap['metric']}{direction}预期，核心原因？下期能否恢复/持续？",
                        source="expectation_gap",
                    ))

        # P3：近期公告异动
        if market_d:
            for sig in (market_d.get("p0_immediate") or []):
                if sig.get("stock_code") == code and sig.get("signal_type") == "RISK_FLAG":
                    questions.append(MeetingQuestion(
                        priority="P3",
                        question=f"近期公告：{sig.get('headline','')[:40]}，目前进展？",
                        source="market_signal",
                    ))

        # Attendees 侧重
        if any("CEO" in a or "实控" in a for a in attendees):
            for pri, q in _ATTENDEE_CEO_QS:
                questions.append(MeetingQuestion(priority=pri, question=q, source="attendee_ceo"))
        if any("CFO" in a or "财务" in a for a in attendees):
            for pri, q in _ATTENDEE_CFO_QS:
                questions.append(MeetingQuestion(priority=pri, question=q, source="attendee_cfo"))

        # 投委会：反方问题
        if meeting_type == "investment_committee":
            for pri, q in _STRATEGY_QS:
                questions.append(MeetingQuestion(priority=pri, question=q, source="counter_argument"))

        # 截断：P0 全保留，P1~P4 合计 ≤ 8
        p0 = [q for q in questions if q.priority == "P0"]
        rest = [q for q in questions if q.priority != "P0"]
        return (p0 + rest)[:len(p0) + 8]

    def _generate_expert_questions(
        self, sector: str, focus_topics: list[str]
    ) -> list[MeetingQuestion]:
        base = [
            MeetingQuestion("P1", f"{sector}行业未来 12 个月最大的结构性变化是什么？", "expert"),
            MeetingQuestion("P1", f"哪些公司在{sector}行业中竞争优势最明显？", "expert"),
            MeetingQuestion("P1", "渠道/供应链层面的隐形成本或壁垒？公开信息未披露的部分？", "expert"),
        ]
        for topic in focus_topics[:3]:
            base.append(MeetingQuestion("P0", f"关于{topic}：您的判断与市场共识有何不同？", "expert"))
        return base

    # ──────────────────────────────────────────
    # Markdown 生成（Module 4）
    # ──────────────────────────────────────────

    def _write_brief(
        self,
        code: str,
        meeting_type: str,
        meeting_time: str | None,
        price_data: dict,
        earnings: dict | None,
        model_r: dict | None,
        val_r: dict | None,
        questions: list[MeetingQuestion],
        age_warnings: list[str],
    ) -> str:
        name = (model_r or {}).get("company_name", code)
        lines = [
            f"# {name}（{code}）会前简报",
            f"**会议类型**：{meeting_type}  |  **生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
            meeting_time and f"**会议时间**：{meeting_time}" or "",
            "",
        ]

        # 实时快照
        if price_data.get("price"):
            lines += [
                "## 实时快照",
                f"当前股价：¥{price_data['price']:.2f}  |  "
                f"今日涨跌：{(price_data.get('1d_pct') or 0):+.2f}%  |  "
                f"相对沪深300（1月）：{(price_data.get('vs_csi300_1m') or 0):+.2f}%",
                "",
            ]
        if price_data.get("announcements"):
            lines.append("**近7日公告**：")
            for ann in price_data["announcements"][:3]:
                lines.append(f"- {ann}")
            lines.append("")

        # 分析快照
        if earnings:
            lines += [
                "## 最新业绩",
                earnings.get("summary", ""),
                "",
            ]
        tp = _f(model_r, "blended_target_price") if model_r else None
        up = _f(model_r, "upside_pct") if model_r else None
        if tp is not None:
            lines += [
                "## 估值",
                f"综合目标价：¥{tp:.2f}  |  上行空间：{up:+.1f}%  |  "
                f"估值裁定：{(val_r or {}).get('verdict','N/A')}"
                if up is not None else
                f"综合目标价：¥{tp:.2f}  |  估值裁定：{(val_r or {}).get('verdict','N/A')}",
                "",
            ]

        # 数据时效警告
        if age_warnings:
            lines += ["## ⚠ 数据时效警告"] + [f"- {w}" for w in age_warnings] + [""]

        # 问题清单（P0 + 前 5 条）
        lines += ["## 关键问题清单"]
        p0_qs = [q for q in questions if q.priority == "P0"]
        other_qs = [q for q in questions if q.priority != "P0"][:5]
        for q in (p0_qs + other_qs):
            lines.append(f"- [{q.priority}] {q.question}")
        lines.append("")

        content = "\n".join(l for l in lines if l is not None)
        # 硬截断 800 字
        if len(content) > 800:
            content = content[:800] + "\n\n*（内容已截断至 800 字）*"

        storage = _ROOT / "storage"
        storage.mkdir(exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d")
        path = storage / f"{code}_brief_{date_str}.md"
        path.write_text(content, encoding="utf-8")
        return str(path)

    def _write_expert_brief(
        self,
        sector: str,
        focus_topics: list[str],
        questions: list[MeetingQuestion],
        meeting_time: str | None,
    ) -> str:
        lines = [
            f"# {sector}行业专家访谈简报",
            meeting_time and f"**会议时间**：{meeting_time}" or "",
            f"**生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## 访谈重点",
        ] + [f"- {t}" for t in focus_topics] + [
            "",
            "## 问题清单",
        ] + [f"- [{q.priority}] {q.question}" for q in questions]

        storage = _ROOT / "storage"
        storage.mkdir(exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d")
        path = storage / f"{sector}_expert_brief_{date_str}.md"
        path.write_text("\n".join(l for l in lines if l is not None), encoding="utf-8")
        return str(path)

    def _write_question_list(self, code: str, questions: list[MeetingQuestion]) -> str:
        lines = [f"# 问题清单：{code}  ({datetime.now().strftime('%Y-%m-%d')})", ""]
        for q in questions:
            lines.append(f"- **[{q.priority}]** {q.question}")
            if q.source:
                lines.append(f"  *(来源：{q.source})*")
        storage = _ROOT / "storage"
        storage.mkdir(exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d")
        path = storage / f"{code}_questions_{date_str}.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path)

    # ──────────────────────────────────────────
    # 实时数据
    # ──────────────────────────────────────────

    @staticmethod
    def _get_realtime(code: str) -> dict:
        result: dict[str, Any] = {}
        try:
            from connectors.market import get_current_price, get_price_performance
            result["price"] = get_current_price(code)
            perf = get_price_performance(code)
            if perf:
                result["1d_pct"] = perf.get("1d")
                result["vs_csi300_1m"] = perf.get("1m")
        except Exception:
            pass
        try:
            from connectors.news import get_announcements
            anns = get_announcements(code, days=7)
            result["announcements"] = [a["title"] for a in anns[:5]]
        except Exception:
            result["announcements"] = []
        return result

    # ──────────────────────────────────────────
    # 数据时效检查
    # ──────────────────────────────────────────

    @staticmethod
    def _check_data_age(
        earnings: dict | None, model_r: dict | None
    ) -> list[str]:
        warnings_: list[str] = []
        now = datetime.now()

        def age_days(ts: str) -> float | None:
            if not ts:
                return None
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return (now - dt.replace(tzinfo=None)).days
            except ValueError:
                return None

        if earnings:
            days = age_days(earnings.get("timestamp", ""))
            if days and days > 90:
                warnings_.append(f"EarningsReview 已 {days} 天未更新，建议重新触发")
        else:
            warnings_.append("未找到 EarningsReview 存档，建议先运行财报审阅")

        if model_r:
            days = age_days(model_r.get("timestamp", ""))
            if days and days > 90:
                warnings_.append(f"ModelBuild 已 {days} 天未更新")
        return warnings_

    # ──────────────────────────────────────────
    # 存档读取
    # ──────────────────────────────────────────

    @staticmethod
    def _load_latest(code: str, agent_key: str) -> dict | None:
        storage = _ROOT / "storage"
        files = sorted(storage.glob(f"{code}_{agent_key}_*.json"), reverse=True)
        if not files:
            return None
        try:
            return json.loads(files[0].read_text(encoding="utf-8"))
        except Exception:
            return None

    @staticmethod
    def _load_latest_market() -> dict | None:
        storage = _ROOT / "storage"
        files = sorted(storage.glob("market_digest_*.json"), reverse=True)
        if not files:
            return None
        try:
            return json.loads(files[0].read_text(encoding="utf-8"))
        except Exception:
            return None

    @staticmethod
    def _load_thesis(code: str) -> list[str]:
        path = _ROOT / "config" / "watchlist.yaml"
        if not path.exists():
            return []
        try:
            import yaml
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            for s in (data.get("stocks") or []):
                if s.get("code") == code:
                    return s.get("thesis", [])
        except Exception:
            pass
        return []


# ──────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────

def _f(d: dict | None, key: str) -> float | None:
    if d is None:
        return None
    v = d.get(key)
    if v is None:
        return None
    try:
        import math
        x = float(v)
        return None if math.isnan(x) else x
    except (ValueError, TypeError):
        return None

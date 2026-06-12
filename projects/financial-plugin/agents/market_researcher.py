"""
Market Researcher Agent。

功能：
  - 监控 watchlist 中所有股票的近期公告，分 P0/P1/P2 优先级
  - 问询函专项评估（发函主体分级 → InquiryRiskScore）
  - Thesis 关键词跟踪（读取 config/watchlist.yaml）
  - 输出 MarketResearchDigest（日报或临时查询）

MVP 跳过：policy_monitor、research_monitor 集成（后期迭代）
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
from models import MarketResearchDigest, ResearchSignal, ThesisStatus

# ──────────────────────────────────────────
# 公告分类关键词
# ──────────────────────────────────────────
_P0_EARNINGS = ["业绩预告", "业绩快报", "业绩修正", "业绩大幅下降", "盈利预警"]
_P0_INQUIRY  = ["问询函", "关注函", "监管函", "立案", "调查", "处罚"]
_P0_REDUCE   = ["减持计划", "股份减持"]

_P1_CONTRACT = ["中标", "重大合同", "战略合作", "合同金额"]
_P1_PLEDGE   = ["股权质押", "补充质押", "解除质押"]
_P1_MGMT     = ["高管辞职", "董事长", "总经理", "实控人变更"]
_P1_FINANCE  = ["定向增发", "非公开发行", "可转债", "配股", "股权激励"]
_P1_MA       = ["收购", "重大资产重组", "出售资产"]

# 问询函风险评分表（发函主体 → 基础分）
_INQUIRY_SCORE_MAP = {
    "证监会": 9,
    "上交所": 6,
    "深交所": 6,
    "关注函": 4,
    "监管函": 5,
}


class MarketResearcher(AgentBase):
    """A 股市场信号监控 Agent。"""

    def run_daily_scan(
        self,
        codes: list[str] | None = None,
    ) -> MarketResearchDigest:
        """
        每日批量扫描监控列表中所有股票的公告和信号。
        codes: 覆盖默认 watchlist（为 None 时读取 config/watchlist.yaml）
        """
        watchlist = self._load_watchlist()
        if codes:
            # 补充用户传入的代码
            existing = {s["code"] for s in watchlist}
            for c in codes:
                if c not in existing:
                    watchlist.append({"code": c, "name": c, "sector": "", "thesis": []})

        digest = MarketResearchDigest(
            digest_date=datetime.now().strftime("%Y-%m-%d"),
            digest_type="daily",
            stocks_monitored=[s["code"] for s in watchlist],
        )

        triggered: list[str] = []

        for stock in watchlist:
            code    = stock["code"]
            thesis  = stock.get("thesis", [])
            sector  = stock.get("sector", "")

            signals = self._scan_stock(code, thesis, sector, days=3)
            for sig in signals:
                self._route_signal(sig, digest)
                if sig.auto_action_taken == "triggered_earnings_reviewer":
                    triggered.append(code)
            # Thesis 状态更新
            digest.thesis_status[code] = self._compute_thesis_status(
                code, signals, digest.thesis_status.get(code)
            )

        digest.earnings_reviews_triggered = list(set(triggered))
        self._save_result(digest)
        return digest

    def query(self, code: str, days: int = 30, thesis: list[str] | None = None) -> MarketResearchDigest:
        """
        临时查询单只股票近 days 天的公告信号。
        """
        thesis = thesis or []
        digest = MarketResearchDigest(
            digest_date=datetime.now().strftime("%Y-%m-%d"),
            digest_type="adhoc",
            stocks_monitored=[code],
        )
        signals = self._scan_stock(code, thesis, sector="", days=days)
        for sig in signals:
            self._route_signal(sig, digest)
        digest.thesis_status[code] = self._compute_thesis_status(code, signals, None)
        return digest

    # ──────────────────────────────────────────
    # 核心扫描逻辑
    # ──────────────────────────────────────────

    def _scan_stock(
        self,
        code: str,
        thesis: list[str],
        sector: str,
        days: int,
    ) -> list[ResearchSignal]:
        from connectors.news import get_announcements, get_inquiry_letters

        signals: list[ResearchSignal] = []
        announcements = get_announcements(code, days=days)

        for ann in announcements:
            title = ann.get("title", "")
            date  = ann.get("date", "")
            url   = ann.get("url", "")

            sig = self._classify_announcement(title, date, url, code, sector, thesis)
            if sig:
                signals.append(sig)

        # 问询函专项
        letters = get_inquiry_letters(code, days=max(days, 90))
        for letter in letters:
            score = self._inquiry_risk_score(letter.get("title", ""))
            sig = ResearchSignal(
                signal_type="RISK_FLAG",
                severity="HIGH" if score >= 7 else "MEDIUM",
                stock_code=code,
                sector=sector,
                source_type="公告",
                headline=f"问询函：{letter.get('title','')[:40]}",
                detail=f"InquiryRiskScore={score}/10。{letter.get('title','')}",
                thesis_impact="NEUTRAL",
                publish_date=letter.get("date", ""),
                source_url=letter.get("url", ""),
            )
            # 避免重复（已被 classify_announcement 处理）
            if not any(s.source_url == sig.source_url for s in signals):
                signals.append(sig)

        return signals

    def _classify_announcement(
        self,
        title: str,
        date: str,
        url: str,
        code: str,
        sector: str,
        thesis: list[str],
    ) -> ResearchSignal | None:
        """将单条公告分类为对应的 ResearchSignal，无法分类返回 None。"""
        # P0 级别
        if any(kw in title for kw in _P0_EARNINGS):
            return ResearchSignal(
                signal_type="EARNINGS_TRIGGER",
                severity="HIGH",
                stock_code=code, sector=sector,
                source_type="公告",
                headline=title[:50],
                detail=title,
                thesis_impact=self._thesis_impact(title, thesis),
                thesis_keywords_hit=self._matching_thesis(title, thesis),
                auto_action_taken="triggered_earnings_reviewer",
                publish_date=date, source_url=url,
            )
        if any(kw in title for kw in _P0_INQUIRY):
            score = self._inquiry_risk_score(title)
            return ResearchSignal(
                signal_type="RISK_FLAG",
                severity="HIGH" if score >= 7 else "MEDIUM",
                stock_code=code, sector=sector,
                source_type="公告",
                headline=f"监管信号：{title[:40]}",
                detail=f"InquiryRiskScore={score}/10",
                thesis_impact="NEUTRAL",
                publish_date=date, source_url=url,
            )
        if any(kw in title for kw in _P0_REDUCE):
            return ResearchSignal(
                signal_type="RISK_FLAG",
                severity="HIGH",
                stock_code=code, sector=sector,
                source_type="公告",
                headline=f"减持：{title[:40]}",
                detail=title,
                thesis_impact="RISK",
                thesis_keywords_hit=self._matching_thesis(title, thesis),
                publish_date=date, source_url=url,
            )

        # P1 级别
        p1_groups = [_P1_CONTRACT, _P1_PLEDGE, _P1_MGMT, _P1_FINANCE, _P1_MA]
        for group in p1_groups:
            if any(kw in title for kw in group):
                impact = self._thesis_impact(title, thesis)
                return ResearchSignal(
                    signal_type="THESIS_UPDATE",
                    severity="MEDIUM",
                    stock_code=code, sector=sector,
                    source_type="公告",
                    headline=title[:50],
                    detail=title,
                    thesis_impact=impact,
                    thesis_keywords_hit=self._matching_thesis(title, thesis),
                    publish_date=date, source_url=url,
                )

        return None  # P2 或无关公告，暂不生成信号

    def _route_signal(self, sig: ResearchSignal, digest: MarketResearchDigest) -> None:
        """将信号路由到 p0/p1/p2 分桶。"""
        if sig.severity == "HIGH" or sig.signal_type == "EARNINGS_TRIGGER":
            digest.p0_immediate.append(sig)
        else:
            digest.p1_daily.append(sig)

    # ──────────────────────────────────────────
    # Thesis 跟踪
    # ──────────────────────────────────────────

    def _compute_thesis_status(
        self,
        code: str,
        signals: list[ResearchSignal],
        prev: ThesisStatus | None,
    ) -> ThesisStatus:
        confirms = sum(1 for s in signals if s.thesis_impact == "CONFIRM")
        risks    = sum(1 for s in signals if s.thesis_impact == "RISK")

        base_confirm = prev.confirm_count if prev else 0
        base_risk    = prev.risk_count if prev else 0
        total_confirm = base_confirm + confirms
        total_risk    = base_risk + risks

        # 连续 3 条 RISK 且无 CONFIRM → REVIEW_NEEDED
        if risks >= 3 and confirms == 0:
            health = "REVIEW_NEEDED"
        elif risks > confirms:
            health = "WEAKENING"
        else:
            health = "INTACT"

        return ThesisStatus(
            stock_code=code,
            confirm_count=total_confirm,
            risk_count=total_risk,
            last_updated=datetime.now().strftime("%Y-%m-%d"),
            health=health,
        )

    # ──────────────────────────────────────────
    # 问询函风险评分
    # ──────────────────────────────────────────

    def _inquiry_risk_score(self, title: str) -> int:
        """基础评分 + 内容风险加分，返回 0-10。"""
        base = 4  # 默认
        for keyword, score in _INQUIRY_SCORE_MAP.items():
            if keyword in title:
                base = max(base, score)
                break
        # 内容风险加分
        risk_words = {"立案": 3, "调查": 2, "处罚": 3, "财务造假": 4, "会计": 1}
        bonus = sum(v for k, v in risk_words.items() if k in title)
        return min(10, base + bonus)

    # ──────────────────────────────────────────
    # 辅助工具
    # ──────────────────────────────────────────

    @staticmethod
    def _thesis_impact(text: str, thesis: list[str]) -> str:
        hits = [kw for kw in thesis if kw in text]
        if not hits:
            return "NEUTRAL"
        # 简单启发式：负面词 → RISK
        neg = ["下降", "减少", "压力", "亏损", "处罚", "减持"]
        if any(w in text for w in neg):
            return "RISK"
        return "CONFIRM"

    @staticmethod
    def _matching_thesis(text: str, thesis: list[str]) -> list[str]:
        return [kw for kw in thesis if kw in text]

    @staticmethod
    def _load_watchlist() -> list[dict[str, Any]]:
        path = _ROOT / "config" / "watchlist.yaml"
        if not path.exists():
            return []
        try:
            import yaml
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return data.get("stocks", []) if data else []
        except Exception:
            return []

    @staticmethod
    def _save_result(digest: MarketResearchDigest) -> str:
        storage = _ROOT / "storage"
        storage.mkdir(exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = storage / f"market_digest_{date_str}.json"
        path.write_text(
            json.dumps(digest.to_dict(), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return str(path)

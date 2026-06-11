"""
Earnings Reviewer Agent。

工作流：
  1. 拉取财务数据（三表 + 指标历史 + 公告 + 分析师预期）
  2. 尝试提取 MD&A 文本（PDF 公告）
  3. Module 1-2：读取顺序 + A 股风险旗帜
  4. Module 3：预期差计算（vs 一致预期 / 同比 / 环比）
  5. Module 4：Thesis 关键词相关性分析（启发式）
  6. 调用 comps_selector subagent
  7. Module 5：生成模型更新指令
  8. 可选：methodology_check（当有 LOW 置信度指令时）
  9. 汇总 overall_verdict + summary，存档 JSON
"""

from __future__ import annotations

import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore")

# 项目根目录
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from models import (
    EarningsReviewResult,
    ExpectationGap,
    ModelUpdateInstruction,
    RiskFlag,
    ThesisVerdict,
)

# ──────────────────────────────────────────
# A 股风险阈值（Module 2）
# ──────────────────────────────────────────
GOODWILL_RISK_THRESHOLD = 0.30          # 商誉/净资产 > 30%
RELATED_PARTY_THRESHOLD = 0.15          # 关联交易/营收 > 15%
SUBSIDY_DEPENDENCY_THRESHOLD = 0.20     # 政府补贴/净利 > 20%
CF_QUALITY_THRESHOLD = 0.20             # |经营CF − 净利| / |净利| > 20%

# ──────────────────────────────────────────
# Thesis 关键词 → 财务指标字段映射（Module 4）
# ──────────────────────────────────────────
THESIS_METRIC_MAP: dict[str, list[str]] = {
    "毛利率":    ["销售毛利率(%)", "主营业务利润率(%)"],
    "毛利":      ["销售毛利率(%)", "主营业务利润率(%)"],
    "营收增长":  ["主营业务收入增长率(%)"],
    "营收":      ["主营业务收入增长率(%)"],
    "净利润":    ["净利润增长率(%)"],
    "盈利":      ["净利润增长率(%)", "销售净利率(%)"],
    "ROE":       ["净资产收益率(%)", "加权净资产收益率(%)"],
    "现金流":    ["经营现金净流量与净利润的比率(%)"],
    "三费":      ["三项费用比重"],
    "费用":      ["三项费用比重"],
    "提价":      ["销售毛利率(%)", "主营业务利润率(%)"],
    "高端化":    ["销售毛利率(%)", "销售净利率(%)"],
    "国产替代":  ["主营业务收入增长率(%)"],
    "海外扩张":  ["主营业务收入增长率(%)"],
    "扩张":      ["主营业务收入增长率(%)"],
    "降本":      ["三项费用比重", "主营业务成本率(%)"],
    "增效":      ["净资产收益率(%)", "总资产净利润率(%)"],
    "储能":      ["主营业务收入增长率(%)"],
    "渗透":      ["主营业务收入增长率(%)"],
}


class EarningsReviewer:
    """A 股财报审阅 Agent。"""

    def review(
        self,
        code: str,
        period: str,
        thesis: list[str] | None = None,
    ) -> EarningsReviewResult:
        """
        对指定股票/报告期执行完整财报审阅。

        code: 6 位股票代码，如 "600519"
        period: 报告期 ISO 格式，如 "2024-12-31"
        thesis: 投资论点关键词列表，如 ["高端化", "提价"]
        """
        thesis = thesis or []
        report_type = self._determine_report_type(period)

        # ── 1. 拉取财务数据 ──────────────────────────────
        income   = self._get_income(code, period)
        balance  = self._get_balance(code, period)
        cashflow = self._get_cashflow(code, period)
        metrics  = self._get_metrics(code)
        metrics_hist = self._get_metrics_hist(code)
        forecast = self._get_forecast(code)

        # 找上一报告期（用于环比）
        prev_period = self._get_prev_period(code, period)
        prev_income = self._get_income(code, prev_period) if prev_period else None

        # 找同比报告期（上年同期）
        yoy_period = self._get_yoy_period(period)
        yoy_income = self._get_income(code, yoy_period) if yoy_period else None

        # ── 2. 提取 MD&A ──────────────────────────────
        mda_text = self._extract_mda(code, period)

        # ── 3. 风险旗帜（Module 2） ─────────────────────
        risk_flags = self._check_risk_flags(income, balance, cashflow, metrics)

        # ── 4. 预期差（Module 3） ──────────────────────
        expectation_gaps = self._compute_expectation_gaps(
            income, yoy_income, prev_income, forecast, metrics, metrics_hist
        )

        # ── 5. Thesis 分析（Module 4） ─────────────────
        thesis_verdicts = self._analyze_thesis(
            thesis, income, metrics, metrics_hist, mda_text
        )

        # ── 6. 可比公司 subagent ───────────────────────
        comps_codes = self._run_comps_selector(code)

        # ── 7. 模型更新指令（Module 5） ────────────────
        model_updates = self._generate_model_updates(
            expectation_gaps, risk_flags, period
        )

        # ── 8. 方法论校验（LOW 置信度时触发） ──────────
        low_confidence = [u for u in model_updates if u.confidence == "LOW"]
        methodology_result = "SKIPPED"
        if low_confidence:
            from subagents.methodology_check import check_methodology
            methodology_result = check_methodology(
                low_confidence,
                report_type=report_type,
                industry=self._get_industry(code),
            )
            # 若 BLOCK，将 LOW 指令降级为需人工处理
            if methodology_result.startswith("BLOCK"):
                for u in low_confidence:
                    u.confidence = "LOW"   # 保持 LOW，确保触发 human_review

        # ── 9. 汇总 ────────────────────────────────────
        overall_verdict = self._compute_overall_verdict(expectation_gaps)
        human_review = any(u.confidence in ("LOW", "MEDIUM") for u in model_updates)
        summary = self._build_summary(
            code, period, report_type,
            expectation_gaps, risk_flags, thesis_verdicts,
            overall_verdict, income
        )

        result = EarningsReviewResult(
            stock_code=code,
            period=period,
            report_type=report_type,
            expectation_gaps=expectation_gaps,
            thesis_verdicts=thesis_verdicts,
            risk_flags=risk_flags,
            model_updates=model_updates,
            overall_verdict=overall_verdict,
            summary=summary,
            human_review_required=human_review,
            timestamp=datetime.now(timezone.utc).isoformat(),
            comps_codes=comps_codes,
            methodology_check_result=methodology_result,
        )

        self._save_result(result)
        return result

    # ──────────────────────────────────────────
    # Module 1-2：数据拉取 + 风险旗帜
    # ──────────────────────────────────────────

    def _check_risk_flags(
        self,
        income: dict | None,
        balance: dict | None,
        cashflow: dict | None,
        metrics: dict | None,
    ) -> list[RiskFlag]:
        flags: list[RiskFlag] = []

        if income is None:
            return flags

        net_profit = _to_float(income.get("净利润"))

        # ① 商誉减值风险
        if balance is not None:
            goodwill = _to_float(balance.get("商誉"))
            equity   = _to_float(balance.get("股东权益合计") or balance.get("所有者权益合计"))
            if goodwill is not None and equity and equity > 0:
                ratio = goodwill / equity
                flags.append(RiskFlag(
                    flag_type="商誉减值",
                    threshold_metric="商誉/净资产",
                    actual_value=round(ratio, 4),
                    threshold=GOODWILL_RISK_THRESHOLD,
                    verdict="HIGH_RISK" if ratio > GOODWILL_RISK_THRESHOLD else "OK",
                    explanation=(
                        f"商誉占净资产 {ratio:.1%}，"
                        + ("超过 30% 阈值，需关注收购标的业绩承诺完成情况。"
                           if ratio > GOODWILL_RISK_THRESHOLD else "在合理范围内。")
                    ),
                ))

        # ② 政府补贴依赖度
        revenue = _to_float(income.get("营业收入"))
        subsidy = _to_float(income.get("其中:政府补助") or income.get("政府补贴"))
        if subsidy and net_profit and net_profit > 0:
            ratio = subsidy / net_profit
            flags.append(RiskFlag(
                flag_type="政府补贴依赖",
                threshold_metric="政府补贴/净利润",
                actual_value=round(ratio, 4),
                threshold=SUBSIDY_DEPENDENCY_THRESHOLD,
                verdict="MEDIUM_RISK" if ratio > SUBSIDY_DEPENDENCY_THRESHOLD else "OK",
                explanation=(
                    f"政府补贴占净利润 {ratio:.1%}，"
                    + ("超过 20%，主业盈利质量存疑。"
                       if ratio > SUBSIDY_DEPENDENCY_THRESHOLD else "影响有限。")
                ),
            ))

        # ③ 现金流质量
        if cashflow is not None and net_profit and abs(net_profit) > 0:
            cf_ops = _to_float(
                cashflow.get("经营活动产生的现金流量净额")
                or cashflow.get("经营活动现金流量净额")
            )
            if cf_ops is not None:
                ratio = abs(cf_ops - net_profit) / abs(net_profit)
                flags.append(RiskFlag(
                    flag_type="现金流质量",
                    threshold_metric="|经营CF − 净利| / |净利|",
                    actual_value=round(ratio, 4),
                    threshold=CF_QUALITY_THRESHOLD,
                    verdict="MEDIUM_RISK" if ratio > CF_QUALITY_THRESHOLD else "OK",
                    explanation=(
                        f"经营现金流与净利润偏差 {ratio:.1%}，"
                        + ("偏差超 20%，利润含金量待核实。"
                           if ratio > CF_QUALITY_THRESHOLD else "利润含金量良好。")
                    ),
                ))

        return flags

    # ──────────────────────────────────────────
    # Module 3：预期差计算
    # ──────────────────────────────────────────

    def _compute_expectation_gaps(
        self,
        income: dict | None,
        yoy_income: dict | None,
        prev_income: dict | None,
        forecast: dict | None,
        metrics: dict | None,
        metrics_hist: list[dict] | None,
    ) -> list[ExpectationGap]:
        if income is None:
            return []

        gaps: list[ExpectationGap] = []

        # 关键指标清单：(名称, 利润表字段, 单位)
        key_metrics = [
            ("营业收入",   "营业收入",     "元"),
            ("净利润",     "净利润",       "元"),
            ("扣非净利润", "扣除非经常性损益后的净利润", "元"),
            ("毛利润",     "毛利润",       "元"),
        ]

        for label, field, _ in key_metrics:
            actual = _to_float(income.get(field))
            if actual is None:
                continue

            # 同比（上年同期）
            yoy_pct = None
            if yoy_income:
                yoy_val = _to_float(yoy_income.get(field))
                if yoy_val and yoy_val != 0:
                    yoy_pct = round((actual - yoy_val) / abs(yoy_val) * 100, 2)

            # 环比（上一报告期）
            qoq_pct = None
            if prev_income:
                prev_val = _to_float(prev_income.get(field))
                if prev_val and prev_val != 0:
                    qoq_pct = round((actual - prev_val) / abs(prev_val) * 100, 2)

            # 分析师一致预期
            consensus, deviation, verdict = self._match_forecast(
                label, actual, forecast
            )
            if consensus is None and yoy_pct is not None:
                # 无预期时用同比判断相对表现（仅供参考）
                verdict = _gap_verdict_by_yoy(yoy_pct)

            gaps.append(ExpectationGap(
                metric=label,
                actual=actual,
                consensus=consensus,
                deviation_pct=deviation,
                verdict=verdict,
                yoy_change_pct=yoy_pct,
                qoq_change_pct=qoq_pct,
            ))

        # 毛利率（来自 metrics）
        if metrics:
            gm = _to_float(metrics.get("销售毛利率(%)"))
            gm_prev = _to_float(metrics_hist[1].get("销售毛利率(%)")) if metrics_hist and len(metrics_hist) > 1 else None
            if gm is not None:
                yoy_pct = round(gm - gm_prev, 2) if gm_prev is not None else None
                gaps.append(ExpectationGap(
                    metric="毛利率",
                    actual=gm,
                    consensus=None,
                    deviation_pct=None,
                    verdict="NO_CONSENSUS",
                    yoy_change_pct=yoy_pct,
                ))

        return gaps

    def _match_forecast(
        self,
        label: str,
        actual: float,
        forecast: dict | None,
    ) -> tuple[float | None, float | None, str]:
        """
        尝试从 forecast dict 里找到对应指标的一致预期。
        返回 (consensus, deviation_pct, verdict)
        """
        if forecast is None:
            return None, None, "NO_CONSENSUS"

        records = forecast.get("records", [])
        if not records:
            return None, None, "NO_CONSENSUS"

        # 简单匹配：找包含关键词的列
        for record in records[:3]:
            for k, v in record.items():
                if any(kw in k for kw in ["净利润", "营收", "收入"]) and label in k:
                    consensus = _to_float(str(v))
                    if consensus and consensus != 0:
                        dev = round((actual - consensus) / abs(consensus) * 100, 2)
                        return consensus, dev, _gap_verdict(dev)

        return None, None, "NO_CONSENSUS"

    # ──────────────────────────────────────────
    # Module 4：Thesis 分析（启发式）
    # ──────────────────────────────────────────

    def _analyze_thesis(
        self,
        keywords: list[str],
        income: dict | None,
        metrics: dict | None,
        metrics_hist: list[dict] | None,
        mda_text: str | None,
    ) -> list[ThesisVerdict]:
        verdicts: list[ThesisVerdict] = []
        if not keywords:
            return verdicts

        current = metrics or {}
        prev = metrics_hist[1] if metrics_hist and len(metrics_hist) > 1 else {}

        for kw in keywords:
            verdict, evidence, source, confidence = self._check_thesis_keyword(
                kw, current, prev, income, mda_text
            )
            verdicts.append(ThesisVerdict(
                thesis_keyword=kw,
                verdict=verdict,
                evidence=evidence,
                source=source,
                confidence=confidence,
            ))
        return verdicts

    def _check_thesis_keyword(
        self,
        keyword: str,
        current: dict,
        prev: dict,
        income: dict | None,
        mda_text: str | None,
    ) -> tuple[str, str, str, str]:
        """
        对单个 thesis 关键词进行启发式验证。
        返回 (verdict, evidence, source, confidence)
        """
        # 1. 找对应的财务指标
        metric_fields = THESIS_METRIC_MAP.get(keyword, [])
        for field in metric_fields:
            cur_val = _to_float(current.get(field))
            prev_val = _to_float(prev.get(field))
            if cur_val is not None:
                if prev_val is not None:
                    delta = cur_val - prev_val
                    direction = "改善" if delta > 0 else "恶化"
                    evidence = (
                        f"{field} 当期 {cur_val:.2f}，上期 {prev_val:.2f}，"
                        f"变化 {delta:+.2f}pct"
                    )
                    # 关键词暗示正向则 delta>0 = CONFIRM，否则 RISK
                    pos_keywords = {"提价", "高端化", "增长", "扩张", "渗透", "替代", "提升", "增效"}
                    expects_increase = any(pk in keyword for pk in pos_keywords)
                    if expects_increase:
                        verdict = "CONFIRM" if delta > 0 else "RISK"
                    else:
                        # 降本/优化等 → 指标下降是 CONFIRM
                        verdict = "CONFIRM" if delta < 0 else "NEUTRAL"

                    confidence = "HIGH" if abs(delta) > 1 else "MEDIUM"
                    return verdict, evidence, "财务指标", confidence
                else:
                    return "NEUTRAL", f"{field} 当期 {cur_val:.2f}，无上期对比数据", "财务指标", "LOW"

        # 2. 在 MD&A 文本中搜索关键词（兜底）
        if mda_text:
            if keyword in mda_text:
                # 找关键词周围的上下文
                idx = mda_text.find(keyword)
                snippet = mda_text[max(0, idx - 30): idx + 60].replace("\n", " ")
                # 检测负面信号词
                neg_signals = ["下降", "减少", "压力", "挑战", "不及预期", "低于"]
                pos_signals = ["增长", "提升", "超预期", "加速", "突破"]
                has_neg = any(s in snippet for s in neg_signals)
                has_pos = any(s in snippet for s in pos_signals)
                if has_pos and not has_neg:
                    return "CONFIRM", f"MD&A 提及：「{snippet.strip()}」", "MD&A文本", "MEDIUM"
                elif has_neg:
                    return "RISK", f"MD&A 提及：「{snippet.strip()}」", "MD&A文本", "MEDIUM"
                else:
                    return "NEUTRAL", f"MD&A 出现关键词但语义不明确", "MD&A文本", "LOW"

        return "NEUTRAL", f"财务数据和 MD&A 均无直接相关信息", "N/A", "LOW"

    # ──────────────────────────────────────────
    # Module 5：模型更新指令
    # ──────────────────────────────────────────

    def _generate_model_updates(
        self,
        gaps: list[ExpectationGap],
        risk_flags: list[RiskFlag],
        period: str,
    ) -> list[ModelUpdateInstruction]:
        instructions: list[ModelUpdateInstruction] = []
        next_year = str(int(period[:4]) + 1)

        for gap in gaps:
            verdict = gap.verdict
            if verdict not in ("BEAT_STRONG", "BEAT_MILD", "MISS_STRONG", "MISS_MILD"):
                continue
            if gap.yoy_change_pct is None:
                continue

            confidence = "HIGH" if verdict in ("BEAT_STRONG", "MISS_STRONG") else "MEDIUM"
            direction = "上调" if gap.yoy_change_pct > 0 else "下调"

            if gap.metric in ("营业收入",):
                instructions.append(ModelUpdateInstruction(
                    action="UPDATE_CELL",
                    target_model="DCF_模型.xlsx",
                    sheet="假设",
                    row_label=f"FY{next_year}E 营业收入增速",
                    old_value=None,
                    new_value=round(gap.yoy_change_pct / 100, 4),
                    reason=f"实际营收同比 {gap.yoy_change_pct:+.1f}%，{direction}增速假设",
                    confidence=confidence,
                ))

            elif gap.metric == "毛利率" and gap.yoy_change_pct is not None:
                instructions.append(ModelUpdateInstruction(
                    action="UPDATE_CELL",
                    target_model="DCF_模型.xlsx",
                    sheet="假设",
                    row_label=f"FY{next_year}E 毛利率",
                    old_value=None,
                    new_value=round((gap.actual or 0) / 100, 4),
                    reason=f"实际毛利率 {gap.actual:.1f}%，同比变化 {gap.yoy_change_pct:+.1f}pct，更新预测基准",
                    confidence=confidence,
                ))

        return instructions

    # ──────────────────────────────────────────
    # 汇总逻辑
    # ──────────────────────────────────────────

    def _compute_overall_verdict(self, gaps: list[ExpectationGap]) -> str:
        """
        从所有预期差中综合判断整体表现。
        逻辑：优先看净利润/扣非净利润，再看收入。
        """
        priority_order = ["扣非净利润", "净利润", "营业收入"]
        verdicts = {g.metric: g.verdict for g in gaps}

        for metric in priority_order:
            v = verdicts.get(metric)
            if v and v != "NO_CONSENSUS":
                return _normalize_overall_verdict(v)

        # 如果都是 NO_CONSENSUS，用同比增速判断
        for gap in gaps:
            if gap.metric in priority_order and gap.yoy_change_pct is not None:
                return _normalize_overall_verdict(_gap_verdict_by_yoy(gap.yoy_change_pct))

        return "IN_LINE"

    def _build_summary(
        self,
        code: str,
        period: str,
        report_type: str,
        gaps: list[ExpectationGap],
        flags: list[RiskFlag],
        thesis: list[ThesisVerdict],
        overall: str,
        income: dict | None,
    ) -> str:
        """生成 ≤200 字的中文摘要。"""
        parts: list[str] = []

        # 整体表现
        verdict_map = {
            "STRONG_BEAT": "大幅超预期",
            "BEAT": "小幅超预期",
            "IN_LINE": "符合预期",
            "MISS": "小幅低于预期",
            "STRONG_MISS": "大幅低于预期",
        }
        parts.append(f"{report_type}{verdict_map.get(overall, overall)}。")

        # 关键指标
        for gap in gaps[:2]:
            if gap.yoy_change_pct is not None:
                parts.append(f"{gap.metric}同比 {gap.yoy_change_pct:+.1f}%。")

        # 高风险项
        high_risks = [f for f in flags if f.verdict == "HIGH_RISK"]
        for r in high_risks[:1]:
            parts.append(f"⚠️ {r.flag_type}风险：{r.explanation[:30]}。")

        # Thesis 状态
        risk_thesis = [t for t in thesis if t.verdict == "RISK"]
        confirm_thesis = [t for t in thesis if t.verdict == "CONFIRM"]
        if confirm_thesis:
            parts.append(f"论点确认：{'、'.join(t.thesis_keyword for t in confirm_thesis[:2])}。")
        if risk_thesis:
            parts.append(f"论点挑战：{'、'.join(t.thesis_keyword for t in risk_thesis[:2])}。")

        return "".join(parts)[:200]

    # ──────────────────────────────────────────
    # Subagent 调用
    # ──────────────────────────────────────────

    def _run_comps_selector(self, code: str) -> list[str]:
        try:
            from subagents.comps_selector import select_comps
            comps = select_comps(code, n=6)
            return [c["code"] for c in comps]
        except Exception:
            return []

    # ──────────────────────────────────────────
    # 工具方法
    # ──────────────────────────────────────────

    @staticmethod
    def _determine_report_type(period: str) -> str:
        return {
            "03-31": "一季报",
            "06-30": "中报",
            "09-30": "三季报",
            "12-31": "年报",
        }.get(period[5:], "未知")

    @staticmethod
    def _get_income(code: str, period: str) -> dict | None:
        from connectors.fundamental import get_income_statement
        return get_income_statement(code, period)

    @staticmethod
    def _get_balance(code: str, period: str) -> dict | None:
        from connectors.fundamental import get_balance_sheet
        return get_balance_sheet(code, period)

    @staticmethod
    def _get_cashflow(code: str, period: str) -> dict | None:
        from connectors.fundamental import get_cashflow
        return get_cashflow(code, period)

    @staticmethod
    def _get_metrics(code: str) -> dict | None:
        from connectors.fundamental import get_key_metrics
        return get_key_metrics(code)

    @staticmethod
    def _get_metrics_hist(code: str) -> list[dict] | None:
        from connectors.fundamental import get_key_metrics_history
        from connectors.cache import LOOKBACK_PERIODS
        return get_key_metrics_history(code, n=LOOKBACK_PERIODS)

    @staticmethod
    def _get_forecast(code: str) -> dict | None:
        from connectors.news import get_analyst_forecast
        return get_analyst_forecast(code)

    @staticmethod
    def _get_prev_period(code: str, period: str) -> str | None:
        """返回上一个报告期。"""
        from connectors.fundamental import get_historical_periods
        periods = get_historical_periods(code, n=4)
        if period in periods:
            idx = periods.index(period)
            return periods[idx + 1] if idx + 1 < len(periods) else None
        # period 不在列表中，找时间上最近的
        for p in periods:
            if p < period:
                return p
        return None

    @staticmethod
    def _get_yoy_period(period: str) -> str | None:
        """返回上年同期：YYYY-MM-DD → (YYYY-1)-MM-DD"""
        try:
            year = int(period[:4]) - 1
            return f"{year}{period[4:]}"
        except ValueError:
            return None

    @staticmethod
    def _extract_mda(code: str, period: str) -> str | None:
        """尝试从业绩公告 PDF 中提取 MD&A 文本。"""
        try:
            from connectors.news import get_earnings_transcript
            from connectors.pdf_parser import extract_mda_from_pdf
            transcripts = get_earnings_transcript(code, period)
            for ann in transcripts:
                url = ann.get("url", "")
                if url and url.endswith(".pdf"):
                    text = extract_mda_from_pdf(url)
                    if text:
                        return text
        except Exception:
            pass
        return None

    @staticmethod
    def _get_industry(code: str) -> str:
        try:
            import akshare as ak
            df = ak.stock_individual_info_em(symbol=code)
            if df is None or df.empty:
                return ""
            info = dict(zip(df["item"], df["value"]))
            return str(info.get("所属行业", ""))
        except Exception:
            return ""

    @staticmethod
    def _save_result(result: EarningsReviewResult) -> str:
        """将结果存为 JSON 文件，返回路径。"""
        storage = _ROOT / "storage"
        storage.mkdir(exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"{result.stock_code}_earnings_review_{date_str}.json"
        path = storage / filename
        path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return str(path)


# ──────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────

def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        import math
        v = float(str(value).replace(",", "").strip())
        return None if math.isnan(v) else v
    except (ValueError, TypeError):
        return None


def _gap_verdict(deviation_pct: float) -> str:
    if deviation_pct > 10:
        return "BEAT_STRONG"
    if deviation_pct > 3:
        return "BEAT_MILD"
    if deviation_pct >= -3:
        return "IN_LINE"
    if deviation_pct >= -10:
        return "MISS_MILD"
    return "MISS_STRONG"


def _gap_verdict_by_yoy(yoy_pct: float) -> str:
    """无一致预期时，用同比增速粗略判断。"""
    if yoy_pct > 20:
        return "BEAT_STRONG"
    if yoy_pct > 5:
        return "BEAT_MILD"
    if yoy_pct >= -5:
        return "IN_LINE"
    if yoy_pct >= -15:
        return "MISS_MILD"
    return "MISS_STRONG"


def _normalize_overall_verdict(verdict: str) -> str:
    return {
        "BEAT_STRONG": "STRONG_BEAT",
        "BEAT_MILD":   "BEAT",
        "IN_LINE":     "IN_LINE",
        "MISS_MILD":   "MISS",
        "MISS_STRONG": "STRONG_MISS",
        "NO_CONSENSUS": "IN_LINE",
    }.get(verdict, verdict)

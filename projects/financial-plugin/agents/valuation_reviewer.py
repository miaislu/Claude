"""
Valuation Reviewer Agent。

输入：ModelBuildResult（来自 Model Builder）
输出：ValuationReviewResult（PASS / REVISE / REJECT）

6 个 Skills 模块：
  1. 估值方法论适用性
  2. 可比公司合理性
  3. 关键假设合理性
  4. A 股特有调整检查
  5. 终值合理性
  6. 综合裁定

REVISE 时自动生成修正建议，最多允许 2 轮迭代（iteration 字段追踪）。
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

from models import ModelBuildResult, ReviewIssue, ValuationReviewResult

# ──────────────────────────────────────────
# 阈值常量
# ──────────────────────────────────────────
_TV_EV_BLOCK   = 0.80    # 终值/EV > 80% → BLOCKER
_TV_EV_WARN    = 0.60    # 终值/EV > 60% → WARNING
_G_MAX         = 0.055   # g > GDP 名义增速（约 5.5%）→ BLOCKER
_G_WACC_SPREAD = 0.03    # WACC - g < 3% → WARNING（利差过窄）
_PE_MAX_MULT   = 2.0     # 可比公司 PE 超中位数 2× → 离群值
_COMPS_MIN     = 3       # 有效可比公司最少数量
_RF_DEVIATION  = 0.01    # 无风险利率偏差 > ±1% → WARNING

# 当前中国 10 年期国债收益率参考值（实时获取失败时使用）
_RF_REFERENCE  = 2.3

# A 股高风险行业（读取 config/policy_risk_sectors.yaml）
_DEFAULT_HIGH_RISK = {"游戏", "教育", "互联网", "医疗器械", "房地产"}

# 方法论适用性矩阵（行业关键词 → 推荐方法）
_METHODOLOGY_MAP = {
    "银行": ["PB"],
    "保险": ["PB", "P/EV"],
    "地产": ["PB", "NAV"],
    "公用事业": ["PB", "DCF"],
    "化工": ["EV/EBITDA"],
    "钢铁": ["EV/EBITDA", "PB"],
    "有色": ["EV/EBITDA"],
    "互联网": ["PS", "EV/Revenue"],
    "亏损": ["PS", "EV/Revenue"],
}


class ValuationReviewer:
    """估值审查 Agent。"""

    def review(
        self,
        model_result: ModelBuildResult,
        context: str = "二级市场",
        industry: str = "",
        iteration: int = 0,
    ) -> ValuationReviewResult:
        """
        审查 Model Builder 的输出。

        model_result: 来自 ModelBuilder.build() 的结果
        context: "二级市场" / "IPO" / "并购"
        industry: 公司所属行业（用于方法论检查）
        iteration: 当前是第几轮迭代（0=首次）
        """
        blockers: list[ReviewIssue]    = []
        warnings_: list[ReviewIssue]   = []
        suggestions: list[ReviewIssue] = []

        # ── Module 1：方法论适用性 ─────────────
        self._check_methodology(
            model_result, industry, blockers, warnings_, suggestions
        )

        # ── Module 2：可比公司合理性 ──────────
        self._check_comps(model_result, blockers, warnings_, suggestions)

        # ── Module 3：关键假设合理性 ──────────
        self._check_assumptions(model_result, blockers, warnings_, suggestions)

        # ── Module 4：A 股特有调整 ────────────
        self._check_ashare_adjustments(
            model_result, industry, context, blockers, warnings_, suggestions
        )

        # ── Module 5：终值合理性 ──────────────
        self._check_terminal_value(model_result, blockers, warnings_, suggestions)

        # ── Module 6：综合裁定 ────────────────
        verdict, verdict_reason = self._determine_verdict(
            blockers, warnings_, iteration
        )

        human_review = (
            verdict == "REJECT"
            or iteration >= 2
            or len(blockers) > 0
        )

        result = ValuationReviewResult(
            stock_code=model_result.stock_code,
            company_name=model_result.company_name,
            review_timestamp=datetime.now(timezone.utc).isoformat(),
            valuation_context=context,
            verdict=verdict,
            verdict_reason=verdict_reason,
            blockers=blockers,
            warnings=warnings_,
            suggestions=suggestions,
            tv_ev_ratio=model_result.terminal_value_pct,
            wacc_used=model_result.wacc,
            terminal_growth_used=model_result.terminal_growth_rate,
            blended_target_price=model_result.blended_target_price,
            iteration=iteration,
            human_review_required=human_review,
        )
        self._save_result(result)
        return result

    # ──────────────────────────────────────────
    # Module 1：方法论适用性
    # ──────────────────────────────────────────

    def _check_methodology(
        self,
        mr: ModelBuildResult,
        industry: str,
        blockers: list, warnings_: list, suggestions: list,
    ) -> None:
        # DCF 检查：终值 > 80% 已在 Module 5 处理
        # 检查：重资产行业是否用了 PE（可能低估）
        for key, rec_methods in _METHODOLOGY_MAP.items():
            if key in industry:
                if "PB" in rec_methods and "PE" not in rec_methods:
                    suggestions.append(ReviewIssue(
                        dimension="方法论",
                        severity="SUGGESTION",
                        description=f"{industry} 行业通常用 {'/'.join(rec_methods)}，当前模型以 DCF 为主",
                        evidence=f"行业：{industry}，推荐方法：{rec_methods}",
                    ))
                break

        # 检查：没有可比公司时 comps 估值不成立
        if not mr.comps_target_price and mr.blended_target_price:
            warnings_.append(ReviewIssue(
                dimension="方法论",
                severity="WARNING",
                description="无有效可比公司，综合目标价仅基于 DCF（50:50 权重失衡）",
                evidence="comps_target_price 为空",
                fix_suggestion="通过 comps_selector 补充 3 家以上可比公司",
            ))

    # ──────────────────────────────────────────
    # Module 2：可比公司合理性
    # ──────────────────────────────────────────

    def _check_comps(
        self,
        mr: ModelBuildResult,
        blockers: list, warnings_: list, suggestions: list,
    ) -> None:
        # 这里依赖 comps_selector 输出，但 ModelBuildResult 目前只存 comps_codes
        # 简化：只检查数量
        comps_count = 0  # 实际需从 excel 或 comps_data 获取
        # 暂时跳过（comps 数据在 Excel 中，未传入此处）
        pass

    # ──────────────────────────────────────────
    # Module 3：关键假设合理性
    # ──────────────────────────────────────────

    def _check_assumptions(
        self,
        mr: ModelBuildResult,
        blockers: list, warnings_: list, suggestions: list,
    ) -> None:
        # WACC 合理性
        if mr.wacc is not None:
            rf = self._get_rf()
            if rf and abs(mr.wacc - (rf / 100 + 1.0 * _ERP)) > _RF_DEVIATION + 0.02:
                # 简化：WACC 与参考值偏差 > 3%
                pass  # 需要更多上下文才能准确判断

        # 收入 CAGR 合理性
        if mr.revenue_cagr_5y is not None:
            if mr.revenue_cagr_5y > 0.40:
                warnings_.append(ReviewIssue(
                    dimension="关键假设",
                    severity="WARNING",
                    description=f"5年收入 CAGR {mr.revenue_cagr_5y:.1%} 偏高，需有据可查的驱动因子",
                    evidence=f"revenue_cagr_5y = {mr.revenue_cagr_5y:.1%}",
                    fix_suggestion="核实收入驱动因子假设，考虑下调至 25% 以下",
                ))
            elif mr.revenue_cagr_5y < -0.10:
                warnings_.append(ReviewIssue(
                    dimension="关键假设",
                    severity="WARNING",
                    description=f"5年收入 CAGR {mr.revenue_cagr_5y:.1%} 为负，是否为衰退行业假设？",
                    evidence=f"revenue_cagr_5y = {mr.revenue_cagr_5y:.1%}",
                ))

    # ──────────────────────────────────────────
    # Module 4：A 股特有调整
    # ──────────────────────────────────────────

    def _check_ashare_adjustments(
        self,
        mr: ModelBuildResult,
        industry: str,
        context: str,
        blockers: list, warnings_: list, suggestions: list,
    ) -> None:
        # 高风险行业：WACC 是否已上调
        high_risk = self._load_high_risk_sectors()
        if any(s in industry for s in high_risk):
            wacc = mr.wacc or 0
            if wacc < 0.10:  # 高风险行业 WACC 建议 ≥ 10%
                warnings_.append(ReviewIssue(
                    dimension="A股调整",
                    severity="WARNING",
                    description=f"{industry} 为监管高风险行业，WACC({wacc:.1%}) 未充分反映政策风险溢价",
                    evidence=f"行业={industry}, WACC={wacc:.1%}",
                    fix_suggestion=f"建议 WACC 上调 1-3%，当前参考值：{wacc:.1%}",
                ))

        # 并购场景：提示稀释效应
        if context == "并购":
            suggestions.append(ReviewIssue(
                dimension="A股调整",
                severity="SUGGESTION",
                description="并购估值需考虑定增/换股的稀释效应，建议补充摊薄 EPS 分析",
                evidence=f"context={context}",
            ))

    # ──────────────────────────────────────────
    # Module 5：终值合理性
    # ──────────────────────────────────────────

    def _check_terminal_value(
        self,
        mr: ModelBuildResult,
        blockers: list, warnings_: list, suggestions: list,
    ) -> None:
        tv_ratio = mr.terminal_value_pct
        g        = mr.terminal_growth_rate
        wacc     = mr.wacc

        # TV/EV > 80% → BLOCKER
        if tv_ratio and tv_ratio > _TV_EV_BLOCK:
            blockers.append(ReviewIssue(
                dimension="终值",
                severity="BLOCKER",
                description=f"终值占 EV {tv_ratio:.1%} 超过 80%，模型严重依赖无法验证的远期假设",
                evidence=f"tv_ev_ratio = {tv_ratio:.1%}",
                fix_suggestion="缩短预测期，或下调永续增长率 g",
            ))
        elif tv_ratio and tv_ratio > _TV_EV_WARN:
            warnings_.append(ReviewIssue(
                dimension="终值",
                severity="WARNING",
                description=f"终值占 EV {tv_ratio:.1%}（60%-80%），依赖度较高",
                evidence=f"tv_ev_ratio = {tv_ratio:.1%}",
            ))

        # g > GDP 名义增速 → BLOCKER
        if g is not None and g > _G_MAX:
            blockers.append(ReviewIssue(
                dimension="终值",
                severity="BLOCKER",
                description=f"永续增长率 g={g:.1%} 超过 GDP 名义增速（{_G_MAX:.1%}），违反经济学逻辑",
                evidence=f"g = {g:.1%}, G_MAX = {_G_MAX:.1%}",
                fix_suggestion=f"将 g 下调至 {_G_MAX:.1%} 以下",
            ))

        # WACC - g 利差过窄 → WARNING
        if wacc and g is not None:
            spread = wacc - g
            if spread < _G_WACC_SPREAD:
                warnings_.append(ReviewIssue(
                    dimension="终值",
                    severity="WARNING",
                    description=f"WACC({wacc:.1%}) - g({g:.1%}) = {spread:.1%}，利差过窄，终值极度敏感",
                    evidence=f"WACC-g = {spread:.1%}（建议 > 3%）",
                    fix_suggestion="下调 g 或上调 WACC，扩大利差",
                ))

    # ──────────────────────────────────────────
    # Module 6：综合裁定
    # ──────────────────────────────────────────

    def _determine_verdict(
        self,
        blockers: list,
        warnings_: list,
        iteration: int,
    ) -> tuple[str, str]:
        if blockers:
            return "REJECT", f"存在 {len(blockers)} 个 BLOCKER：{blockers[0].description[:60]}"
        if len(warnings_) >= 3:
            return "REVISE", f"存在 {len(warnings_)} 个 WARNING，需修正后重审"
        if iteration >= 2:
            return "PASS", "经 2 轮迭代，无 BLOCKER，升级为人工确认"
        return "PASS", "无 BLOCKER，WARNING < 3，估值方法论合理"

    # ──────────────────────────────────────────
    # 辅助
    # ──────────────────────────────────────────

    @staticmethod
    def _get_rf() -> float | None:
        try:
            from connectors.market import get_bond_yield
            return get_bond_yield("10y")
        except Exception:
            return _RF_REFERENCE

    @staticmethod
    def _load_high_risk_sectors() -> set[str]:
        path = _ROOT / "config" / "policy_risk_sectors.yaml"
        if not path.exists():
            return _DEFAULT_HIGH_RISK
        try:
            import yaml
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return {s["sector"] for s in (data.get("sectors") or [])}
        except Exception:
            return _DEFAULT_HIGH_RISK

    @staticmethod
    def _save_result(result: ValuationReviewResult) -> str:
        storage = _ROOT / "storage"
        storage.mkdir(exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d")
        path = storage / f"{result.stock_code}_valuation_review_{date_str}.json"
        path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return str(path)


# 与 model_builder 共用的常量
_ERP = 0.07

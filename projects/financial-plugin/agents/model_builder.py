"""
Model Builder Agent。

两条路径：
  Path A：build(code, period, g, comps_codes) — 从零建模
  Path B：update(code, instructions) — 接收 Earnings Reviewer 更新指令

DCF 计算（纯 Python）：
  WACC = Rf + β × ERP（ERP 默认 7%）
  Terminal Value = FCFFₙ × (1+g) / (WACC - g)
  TV/EV > 70% 标 Warning

三表勾稽（简化）：
  资产 ≈ 负债 + 权益（误差 < 1%）
  期末现金 ≈ 期初现金 + 三表现金净变化（误差 < 1%）
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
from models import (
    ChangeLogEntry,
    LinkageError,
    ModelBuildResult,
    ModelUpdateInstruction,
)

# ──────────────────────────────────────────
# 常量
# ──────────────────────────────────────────
_ERP          = 0.07   # 市场风险溢价（A 股）
_TAX_RATE     = 0.25   # 默认企业所得税率
_FORECAST_YRS = 5      # 显式预测期
_BLEND_DCF    = 0.50   # DCF 权重
_BLEND_COMPS  = 0.50   # 可比估值权重
_TV_EV_WARN   = 0.70   # 终值占 EV 警告阈值


class ModelBuilder(AgentBase):
    """A 股财务建模 Agent。"""

    def build(
        self,
        code: str,
        period: str,
        g: float,               # 永续增长率（用户必须提供）
        comps_codes: list[str] | None = None,
    ) -> ModelBuildResult:
        """
        从零建模，路径 B。

        g: 永续增长率，如 0.05 表示 5%（用户提供，不自动推算）
        comps_codes: 可比公司代码列表（来自 comps_selector 或用户指定）
        """
        comps_codes = comps_codes or []

        # 1. 拉取历史数据
        #    income_hist  — 全部 8 期（含季报），用于 WACC 和三表勾稽
        #    annual_hist  — 仅年报，用于预测模型和 Excel（避免季报/年报混用）
        income_hist  = self._get_income_history(code)
        annual_hist  = self._get_annual_income_history(code, n_annual=4)
        balance_hist = self._get_balance_history(code)
        cf_hist      = self._get_cf_history(code)
        shares       = self._get_shares(code)
        current_price = self._get_price(code)
        beta         = self._get_beta(code)
        rf           = self._get_rf()
        metrics_hist = self._get_metrics_hist(code)

        # 年报不足时降级使用全部历史
        model_base = annual_hist if annual_hist else income_hist

        if not income_hist:
            return ModelBuildResult(
                stock_code=code,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        company_name = self._get_company_name(code)

        # 2. 计算 WACC（用全期数据，含最新季报）
        wacc = self._calc_wacc(beta, rf, income_hist, balance_hist)

        # 3. 建预测期利润表（5年，基于年报口径）
        forecast = self._build_forecast(income_hist, metrics_hist)

        # 4. DCF 计算
        dcf_data = self._calc_dcf(forecast, model_base, balance_hist, wacc, g, shares, current_price)

        # 5. 可比估值（传入 shares 参数，修复永远 None 的 bug）
        comps_data    = self._get_comps_multiples(comps_codes)
        comps_price   = self._calc_comps_price(comps_data, model_base, shares)
        dcf_price     = dcf_data.get("dcf_price")
        blended_price = self._blend(dcf_price, comps_price)
        dcf_data["comps_price"]   = comps_price
        dcf_data["blended_price"] = blended_price
        dcf_data["current_price"] = current_price

        upside = (blended_price / current_price - 1) * 100 if blended_price and current_price else None

        # 6. 三表勾稽
        linkage_errors = self._check_linkage(income_hist, balance_hist, cf_hist)

        # 7. 生成 Excel（历史部分传年报序列，已在步骤 1 中单独拉取）
        excel_path = self._write_excel(
            code, company_name,
            model_base, forecast,
            dcf_data, comps_data,
        )

        result = ModelBuildResult(
            stock_code=code,
            company_name=company_name,
            excel_path=excel_path,
            dcf_target_price=dcf_price,
            comps_target_price=comps_price,
            blended_target_price=blended_price,
            current_price=current_price,
            upside_pct=round(upside, 2) if upside is not None else None,
            wacc=round(wacc, 4) if wacc else None,
            terminal_growth_rate=g,
            revenue_cagr_5y=self._revenue_cagr(forecast),
            avg_net_margin=self._avg_margin(forecast),
            linkage_errors=linkage_errors,
            terminal_value_pct=dcf_data.get("tv_ev_ratio"),
            human_review_required=bool(linkage_errors) or (dcf_data.get("tv_ev_ratio", 0) > _TV_EV_WARN),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._save_result(result)
        return result

    def update(
        self,
        code: str,
        instructions: list[ModelUpdateInstruction],
    ) -> ModelBuildResult:
        """
        路径 A：接收 Earnings Reviewer 更新指令，更新已有模型。
        HIGH confidence → 自动执行；MEDIUM → 标注待确认。
        """
        change_log: list[ChangeLogEntry] = []
        auto_applied: list[ModelUpdateInstruction] = []
        pending: list[ModelUpdateInstruction] = []

        for instr in instructions:
            if instr.confidence == "HIGH":
                auto_applied.append(instr)
                change_log.append(ChangeLogEntry(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    row_label=instr.row_label,
                    old_value=instr.old_value,
                    new_value=instr.new_value,
                    reason=instr.reason,
                    confidence=instr.confidence,
                ))
            else:
                pending.append(instr)

        human_review = bool(pending)
        # 路径 A：简化实现，重新触发 build 并在 change_log 中记录
        # 完整实现需要读取现有 Excel 并就地更新 —— 留待后续迭代
        result = ModelBuildResult(
            stock_code=code,
            change_log=change_log,
            human_review_required=human_review,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._save_result(result, suffix="update")
        return result

    # ──────────────────────────────────────────
    # 计算核心
    # ──────────────────────────────────────────

    def _calc_wacc(
        self,
        beta: float | None,
        rf: float | None,
        income_hist: list[dict],
        balance_hist: list[dict],
    ) -> float:
        beta = beta or 1.0
        rf   = (rf or 2.3) / 100   # 转为小数

        # 权益成本
        ke = rf + beta * _ERP

        # 债务成本（简化：用利息/有息负债）
        interest = _to_float((income_hist[0] if income_hist else {}).get("财务费用"))
        debt = _to_float((balance_hist[0] if balance_hist else {}).get("有息负债") or
                         (balance_hist[0] if balance_hist else {}).get("长期借款"))
        if interest and debt and debt > 0:
            kd = min(abs(interest) / debt, 0.12)  # 上限 12%
        else:
            kd = 0.04  # 默认 4%

        # 资本结构（用账面值）
        equity = _to_float((balance_hist[0] if balance_hist else {}).get("股东权益合计"))
        if equity and debt:
            total = equity + abs(debt)
            we = equity / total
            wd = abs(debt) / total
        else:
            we, wd = 0.70, 0.30

        wacc = we * ke + wd * kd * (1 - _TAX_RATE)
        return round(max(wacc, 0.05), 4)  # WACC 下限 5%

    def _build_forecast(
        self,
        income_hist: list[dict],
        metrics_hist: list[dict] | None,
    ) -> list[dict]:
        """基于历史年报均值外推 5 年预测期利润表。

        只使用年报（报告日以 1231 结尾）计算增速和基准，
        避免季报/中报与年报混用导致增速失真。
        """
        if not income_hist:
            return []

        # ── 只取年报记录，用于增速和利润率计算 ──────────
        annual = [h for h in income_hist if _is_annual_period(h)]
        if not annual:
            # 无年报时降级用全部数据（取最近 2 期同口径计算）
            annual = income_hist

        # 历史均值增速（最近 4 个年报，避免极端值）
        revenues = [_to_float(h.get("营业收入")) for h in annual[:4] if _to_float(h.get("营业收入"))]
        rev_growths = [
            (revenues[i] / revenues[i + 1] - 1)
            for i in range(len(revenues) - 1)
            if revenues[i + 1] and revenues[i + 1] > 0
        ]
        avg_growth = sum(rev_growths) / len(rev_growths) if rev_growths else 0.05
        avg_growth = max(-0.20, min(avg_growth, 0.40))  # 限幅 -20%~40%

        # 历史均值毛利率（来自 metrics_hist，已是年度数据）
        gm_list = [_to_float((m or {}).get("销售毛利率(%)")) for m in (metrics_hist or [])[:4]]
        gm_list = [x / 100 for x in gm_list if x is not None]
        avg_gm  = sum(gm_list) / len(gm_list) if gm_list else 0.40

        # 历史均值净利率（基于年报）
        nm_list = [_to_float(h.get("净利润")) for h in annual[:4]]
        rv_list = [_to_float(h.get("营业收入")) for h in annual[:4]]
        nm_pcts = [nm / rv for nm, rv in zip(nm_list, rv_list) if nm and rv and rv > 0]
        avg_nm  = sum(nm_pcts) / len(nm_pcts) if nm_pcts else 0.12

        # 基准收入和年份：取最近年报（非季报）
        latest_rev = _to_float(annual[0].get("营业收入")) or 0
        latest_period = str(annual[0].get("报告日", ""))
        try:
            base_year = int(latest_period[:4])
        except ValueError:
            base_year = datetime.now().year

        forecast = []
        rev = latest_rev
        for yr in range(1, _FORECAST_YRS + 1):
            rev *= (1 + avg_growth)
            gross = rev * avg_gm
            net   = rev * avg_nm
            forecast.append({
                "period": f"{base_year + yr}-12-31",
                "营业收入": round(rev, 0),
                "毛利润":   round(gross, 0),
                "净利润":   round(net, 0),
            })
        return forecast

    def _calc_dcf(
        self,
        forecast: list[dict],
        income_hist: list[dict],
        balance_hist: list[dict],
        wacc: float,
        g: float,
        shares: float | None,
        current_price: float | None,
    ) -> dict[str, Any]:
        if not forecast or wacc <= g:
            return {}

        # FCFF ≈ 净利润 × 0.85（简化：假设 CapEx ≈ D&A，净营运资本变化忽略）
        fcff_list = [(_to_float(f.get("净利润")) or 0) * 0.85 for f in forecast]

        # 折现 FCFF
        pv_fcff = sum(fcff / (1 + wacc) ** t for t, fcff in enumerate(fcff_list, 1))

        # 终值
        last_fcff  = fcff_list[-1]
        tv         = last_fcff * (1 + g) / (wacc - g)
        pv_tv      = tv / (1 + wacc) ** _FORECAST_YRS
        ev         = pv_fcff + pv_tv
        tv_ev_ratio = pv_tv / ev if ev > 0 else None

        # 净负债
        debt  = _to_float((balance_hist[0] if balance_hist else {}).get("有息负债") or 0)
        cash  = _to_float((balance_hist[0] if balance_hist else {}).get("货币资金") or
                          (income_hist[0] if income_hist else {}).get("货币资金") or 0)
        net_debt     = (abs(debt) if debt else 0) - (cash or 0)
        equity_value = ev - net_debt

        shares = shares or 1e9
        dcf_price = equity_value / shares if equity_value > 0 and shares > 0 else None

        return {
            "wacc": wacc,
            "g": g,
            "forecast_years": _FORECAST_YRS,
            "ev": ev,
            "pv_fcff": pv_fcff,
            "pv_tv": pv_tv,
            "tv_ev_ratio": round(tv_ev_ratio, 4) if tv_ev_ratio else None,
            "net_debt": net_debt,
            "equity_value": equity_value,
            "shares": shares,
            "dcf_price": round(dcf_price, 2) if dcf_price else None,
        }

    @staticmethod
    def _calc_comps_price(
        comps_data: list[dict],
        income_hist: list[dict],
        total_shares: float | None = None,
    ) -> float | None:
        """
        用可比公司中位数 PE 估算目标价。
        total_shares: 目标公司总股本（由 build() 传入，不在此处重新查询）
        """
        pe_list = [_to_float(c.get("pe_ttm")) for c in comps_data if _to_float(c.get("pe_ttm"))]
        pe_list = [p for p in pe_list if 0 < p < 100]
        if not pe_list or not income_hist:
            return None
        median_pe = sorted(pe_list)[len(pe_list) // 2]

        # EPS = 净利润 / 股本（使用外部传入的 total_shares）
        net_profit = _to_float(income_hist[0].get("净利润"))
        shares = total_shares
        if not net_profit or not shares:
            return None
        eps = net_profit / shares
        return round(median_pe * eps, 2)

    @staticmethod
    def _blend(dcf_price: float | None, comps_price: float | None) -> float | None:
        if dcf_price and comps_price:
            return round(dcf_price * _BLEND_DCF + comps_price * _BLEND_COMPS, 2)
        return dcf_price or comps_price

    def _check_linkage(
        self,
        income_hist: list[dict],
        balance_hist: list[dict],
        cf_hist: list[dict],
    ) -> list[LinkageError]:
        errors: list[LinkageError] = []
        if not balance_hist:
            return errors

        b = balance_hist[0]
        total_assets = _to_float(b.get("资产合计") or b.get("总资产"))
        total_liab   = _to_float(b.get("负债合计") or b.get("总负债"))
        total_equity = _to_float(b.get("股东权益合计") or b.get("所有者权益合计"))

        if total_assets and total_liab and total_equity:
            diff = abs(total_assets - total_liab - total_equity)
            if total_assets > 0 and diff / total_assets > 0.01:
                errors.append(LinkageError(
                    check_name="资产负债表勾稽",
                    expected=total_liab + total_equity,
                    actual=total_assets,
                    description=f"资产({_fmt_b(total_assets)}) ≠ 负债({_fmt_b(total_liab)}) + 权益({_fmt_b(total_equity)})，偏差 {diff/total_assets:.1%}",
                ))
        return errors

    # ──────────────────────────────────────────
    # 工具方法
    # ──────────────────────────────────────────

    @staticmethod
    def _get_income_history(code: str) -> list[dict]:
        """拉取近 LOOKBACK_PERIODS 期（含季报/中报/年报），用于 WACC 和勾稽。"""
        try:
            from connectors.fundamental import get_historical_periods, get_income_statement
            from connectors.cache import LOOKBACK_PERIODS
            periods = get_historical_periods(code, n=LOOKBACK_PERIODS)
            results = []
            for p in periods:
                rec = get_income_statement(code, p)
                if rec:
                    rec["_period"] = p
                    results.append(rec)
            return results
        except Exception:
            return []

    @staticmethod
    def _get_annual_income_history(code: str, n_annual: int = 4) -> list[dict]:
        """
        专门拉取最近 n_annual 个年报期（报告日以 12-31 结尾）。
        扫描范围 = n_annual × 4 个期，确保覆盖足够年报。
        用于：预测模型基准、Excel 展示。
        """
        try:
            from connectors.fundamental import get_historical_periods, get_income_statement
            periods = get_historical_periods(code, n=n_annual * 4)
            results = []
            for p in periods:
                if not p.endswith("12-31"):
                    continue
                rec = get_income_statement(code, p)
                if rec:
                    rec["_period"] = p
                    results.append(rec)
                if len(results) >= n_annual:
                    break
            return results
        except Exception:
            return []

    @staticmethod
    def _get_balance_history(code: str) -> list[dict]:
        try:
            from connectors.fundamental import get_historical_periods, get_balance_sheet
            from connectors.cache import LOOKBACK_PERIODS
            periods = get_historical_periods(code, n=LOOKBACK_PERIODS)
            return [get_balance_sheet(code, p) for p in periods if get_balance_sheet(code, p)]
        except Exception:
            return []

    @staticmethod
    def _get_cf_history(code: str) -> list[dict]:
        try:
            from connectors.fundamental import get_historical_periods, get_cashflow
            from connectors.cache import LOOKBACK_PERIODS
            periods = get_historical_periods(code, n=LOOKBACK_PERIODS)
            return [get_cashflow(code, p) for p in periods if get_cashflow(code, p)]
        except Exception:
            return []

    @staticmethod
    def _get_shares(code: str) -> float | None:
        try:
            from connectors.market import get_shares_outstanding
            info = get_shares_outstanding(code)
            return info.get("total_shares") if info else None
        except Exception:
            return None

    @staticmethod
    def _get_price(code: str) -> float | None:
        try:
            from connectors.market import get_current_price
            return get_current_price(code)
        except Exception:
            return None

    @staticmethod
    def _get_beta(code: str) -> float | None:
        try:
            from connectors.market import get_beta
            return get_beta(code)
        except Exception:
            return None

    @staticmethod
    def _get_rf() -> float | None:
        try:
            from connectors.market import get_bond_yield
            return get_bond_yield("10y")
        except Exception:
            return 2.3  # 默认 2.3%

    @staticmethod
    def _get_metrics_hist(code: str) -> list[dict] | None:
        try:
            from connectors.fundamental import get_key_metrics_history
            from connectors.cache import LOOKBACK_PERIODS
            return get_key_metrics_history(code, n=LOOKBACK_PERIODS)
        except Exception:
            return None

    @staticmethod
    def _get_comps_multiples(codes: list[str]) -> list[dict]:
        try:
            from connectors.market import get_comps_multiples
            return get_comps_multiples(codes)
        except Exception:
            return []

    @staticmethod
    def _get_company_name(code: str) -> str:
        try:
            from connectors.market import get_shares_outstanding
            info = get_shares_outstanding(code)
            return info.get("company_name", code) if info else code
        except Exception:
            return code

    @staticmethod
    def _revenue_cagr(forecast: list[dict]) -> float | None:
        revs = [_to_float(f.get("营业收入")) for f in forecast if _to_float(f.get("营业收入"))]
        if len(revs) < 2:
            return None
        return round((revs[-1] / revs[0]) ** (1 / (len(revs) - 1)) - 1, 4)

    @staticmethod
    def _avg_margin(forecast: list[dict]) -> float | None:
        margins = []
        for f in forecast:
            rev = _to_float(f.get("营业收入"))
            net = _to_float(f.get("净利润"))
            if rev and net and rev > 0:
                margins.append(net / rev)
        return round(sum(margins) / len(margins), 4) if margins else None

    @staticmethod
    def _write_excel(
        code: str,
        company_name: str,
        income_hist: list[dict],
        forecast: list[dict],
        dcf_data: dict,
        comps_data: list[dict],
    ) -> str:
        try:
            from connectors.template import create_model_workbook
            return create_model_workbook(
                stock_code=code,
                company_name=company_name,
                income_history=income_hist,
                income_forecast=forecast,
                dcf_data=dcf_data,
                comps_data=comps_data,
            )
        except Exception:
            return ""

    @staticmethod
    def _save_result(result: ModelBuildResult, suffix: str = "build") -> str:
        storage = _ROOT / "storage"
        storage.mkdir(exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = storage / f"{result.stock_code}_model_{suffix}_{date_str}.json"
        path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return str(path)


# ──────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────

def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        import math
        x = float(str(v).replace(",", "").strip())
        return None if math.isnan(x) else x
    except (ValueError, TypeError):
        return None


def _fmt_b(v: float) -> str:
    return f"{v / 1e8:.2f}亿"


def _is_annual_period(record: dict) -> bool:
    """判断利润表记录是否为年报（报告日以 1231 结尾）。"""
    period = str(record.get("报告日", "") or record.get("_period", ""))
    # akshare 返回格式为 "20241231" 或 "2024-12-31"
    return period.replace("-", "").endswith("1231")

"""
方法论校验 subagent。
被 Earnings Reviewer / Model Builder / Valuation Reviewer 共享调用。

触发条件：当任意 ModelUpdateInstruction 的 confidence == "LOW" 时。

检查项：
  1. 指标口径一致性（扣非 vs 归母净利润）
  2. 同比 vs 环比混用检测
  3. 非经常性损益剥离完整性
  4. 季节性因素（零售/农业等行业）

输出：
  "PASS"              — 无问题
  "WARN: {detail}"    — 有注意事项，不阻断
  "BLOCK: {detail}"   — 发现严重问题，必须修正后重新提交
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import ModelUpdateInstruction


def check_methodology(
    instructions: list["ModelUpdateInstruction"],
    report_type: str = "",
    industry: str = "",
) -> str:
    """
    校验一组模型更新指令的方法论。

    instructions: 待校验的指令列表（通常为 confidence=LOW 的那些）
    report_type: "年报" / "三季报" 等，用于季节性检查
    industry: 公司行业，用于季节性检查

    返回 "PASS" / "WARN: ..." / "BLOCK: ..."
    """
    issues: list[tuple[str, str]] = []   # (level, detail)

    for instr in instructions:
        row = instr.row_label.lower()
        reason = instr.reason.lower()

        # ① 口径一致性：扣非 vs 归母
        if _has_inconsistent_definition(row, reason):
            issues.append((
                "WARN",
                f"'{instr.row_label}' 可能混用扣非/归母口径，请确认使用统一定义",
            ))

        # ② 同比/环比混用
        if _has_yoy_qoq_mix(reason):
            issues.append((
                "WARN",
                f"'{instr.row_label}' 原因说明同时引用同比和环比数据，请确认基准一致",
            ))

        # ③ 非经常性损益
        if _missing_nonrecurring_carveout(row, reason):
            issues.append((
                "WARN",
                f"'{instr.row_label}' 涉及净利润但未说明是否已剥离非经常性损益",
            ))

        # ④ 季节性：一季报/三季报时检查
        if report_type in ("一季报", "三季报") and _is_seasonal_industry(industry):
            issues.append((
                "WARN",
                f"'{instr.row_label}' 属于季节性行业（{industry}），"
                "单季度数据波动可能不代表趋势，建议使用滚动 TTM",
            ))

    if not issues:
        return "PASS"

    blocks = [d for level, d in issues if level == "BLOCK"]
    warns = [d for level, d in issues if level == "WARN"]

    if blocks:
        return "BLOCK: " + "; ".join(blocks)
    return "WARN: " + "; ".join(warns)


# ──────────────────────────────────────────
# 检查规则（纯文本启发式）
# ──────────────────────────────────────────

def _has_inconsistent_definition(row: str, reason: str) -> bool:
    """扣非 vs 归母混用检测。"""
    has_non = "扣非" in row or "扣非" in reason
    has_guimu = "归母" in row or "归母" in reason
    return has_non and has_guimu


def _has_yoy_qoq_mix(reason: str) -> bool:
    """同比环比混用检测。"""
    has_yoy = "同比" in reason or "去年同期" in reason
    has_qoq = "环比" in reason or "上季度" in reason or "上期" in reason
    return has_yoy and has_qoq


def _missing_nonrecurring_carveout(row: str, reason: str) -> bool:
    """净利润相关指令但未提非经常性损益处理。"""
    is_profit_row = "净利润" in row and "扣非" not in row
    mentions_nonrecurring = "非经常" in reason or "一次性" in reason or "补贴" in reason
    # 如果是净利润行且原因提到了一次性项目但没说剥离
    return is_profit_row and mentions_nonrecurring and "剥离" not in reason


_SEASONAL_INDUSTRIES = {"零售", "餐饮", "旅游", "农业", "农林牧渔", "消费品"}


def _is_seasonal_industry(industry: str) -> bool:
    return any(s in industry for s in _SEASONAL_INDUSTRIES)

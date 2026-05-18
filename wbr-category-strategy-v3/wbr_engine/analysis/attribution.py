#!/usr/bin/env python3
"""WBR 渠道/维度归因分析"""
from __future__ import annotations

import argparse
import sys
from typing import Optional, Dict, Any, List

import numpy as np

from wbr_engine.data.loader import (
    load_wbr_excel, get_metric_series, get_all_parent_metrics,
    get_children_metrics, get_latest_week, get_week_columns,
    get_metric_value, compute_wow,
)

MIN_WEEKS_FOR_ATTRIBUTION = 2
MIN_CHILDREN_FOR_DRILLDOWN = 2


def check_applicability(df: Any, metric_name: str) -> Dict[str, Any]:
    series = get_metric_series(df, metric_name)
    if series is None or len(series) < MIN_WEEKS_FOR_ATTRIBUTION:
        n = len(series) if series is not None else 0
        return {
            'can_run': False,
            'reason': f'指标"{metric_name}"数据不足（{n}周），归因需要至少{MIN_WEEKS_FOR_ATTRIBUTION}周',
        }
    children = get_children_metrics(df, metric_name)
    if len(children) < MIN_CHILDREN_FOR_DRILLDOWN:
        return {
            'can_run': False,
            'reason': f'指标"{metric_name}"子维度不足（{len(children)}个），归因需要至少{MIN_CHILDREN_FOR_DRILLDOWN}个子维度',
        }
    return {'can_run': True, 'reason': None}


def calculate_contribution(df: Any, metric_name: str) -> Dict[str, Any]:
    """计算各子维度对父指标 WoW 变化的贡献率。"""
    week_cols = get_week_columns(df)
    if len(week_cols) < 2:
        return {'metric': metric_name, 'applicable': False, 'reason': '周数据不足2列，无法计算环比变化'}

    latest_week = week_cols[-1]
    prev_week = week_cols[-2]

    parent_latest = get_metric_value(df, metric_name, latest_week)
    parent_prev = get_metric_value(df, metric_name, prev_week)

    if parent_latest is None or parent_prev is None:
        return {
            'metric': metric_name, 'applicable': False,
            'reason': f'父指标"{metric_name}"在 {prev_week} 或 {latest_week} 无数据',
        }

    parent_change = parent_latest - parent_prev
    if abs(parent_change) < 1e-10:
        return {
            'metric': metric_name, 'applicable': True,
            'parent_change': 0, 'conclusion': '父指标环比无变化，无需归因', 'contributions': [],
        }

    children = get_children_metrics(df, metric_name)
    contributions = []
    for child in children:
        child_latest = get_metric_value(df, child, latest_week)
        child_prev = get_metric_value(df, child, prev_week)
        if child_latest is None or child_prev is None:
            contributions.append({'dimension': child, 'data_available': False, 'reason': f'{prev_week}或{latest_week}无数据'})
            continue
        child_change = child_latest - child_prev
        contributions.append({
            'dimension': child, 'data_available': True,
            'prev_value': float(child_prev), 'latest_value': float(child_latest),
            'change': float(child_change), 'contrib_rate': float((child_change / parent_change) * 100),
        })

    valid_contribs = [c for c in contributions if c.get('data_available')]
    contrib_sum = sum(c['contrib_rate'] for c in valid_contribs)
    valid_contribs.sort(key=lambda x: abs(x.get('contrib_rate', 0)), reverse=True)
    parent_wow_pct = (parent_change / abs(parent_prev)) * 100 if parent_prev != 0 else None

    return {
        'metric': metric_name, 'applicable': True,
        'latest_week': latest_week, 'prev_week': prev_week,
        'parent_latest': float(parent_latest), 'parent_prev': float(parent_prev),
        'parent_change': float(parent_change),
        'parent_wow_pct': float(parent_wow_pct) if parent_wow_pct is not None else None,
        'contributions': valid_contribs,
        'unavailable_dimensions': [c for c in contributions if not c.get('data_available')],
        'self_check_passed': abs(contrib_sum - 100.0) < 5.0,
        'contrib_sum': float(contrib_sum),
    }


def perform_drilldown(df: Any, metric_name: str) -> Dict[str, Any]:
    """完整归因流程：检查条件 → 计算贡献 → 返回结果。"""
    check = check_applicability(df, metric_name)
    if not check['can_run']:
        return {'metric': metric_name, 'applicable': False, 'reason': check['reason']}
    return calculate_contribution(df, metric_name)


def scan_all_metrics(file_path: str) -> List[Dict[str, Any]]:
    df = load_wbr_excel(file_path)
    return [
        perform_drilldown(df, m)
        for m in get_all_parent_metrics(df)
        if len(get_children_metrics(df, m)) >= MIN_CHILDREN_FOR_DRILLDOWN
    ]


def format_result_natural_language(result: Dict[str, Any]) -> str:
    metric = result.get('metric', '未知指标')
    if not result.get('applicable'):
        return f"【{metric}】归因分析不可用：{result.get('reason', '原因未知')}"
    if result.get('conclusion'):
        return f"【{metric}】{result['conclusion']}"

    parent_change = result.get('parent_change', 0)
    parent_wow = result.get('parent_wow_pct')
    direction = '上升' if parent_change > 0 else '下降'
    wow_str = f"（WoW {parent_wow:+.1f}%）" if parent_wow else ''
    lines = [
        f"【{metric}】归因分析（{result.get('prev_week', '?')} → {result.get('latest_week', '?')}）",
        f"整体变化：{result.get('parent_prev', 0):.2f} → {result.get('parent_latest', 0):.2f}，{direction} {abs(parent_change):.2f}{wow_str}",
        "", "各渠道贡献：",
    ]
    for i, c in enumerate(result.get('contributions', [])[:5], 1):
        emoji = '📈' if c['change'] > 0 else '📉'
        lines.append(f"  {i}. {c['dimension']}：{emoji} 变化 {c['change']:+.2f}（贡献率 {c['contrib_rate']:+.1f}%）  [{c['prev_value']:.2f} → {c['latest_value']:.2f}]")
    if not result.get('self_check_passed'):
        lines.append(f"\n  ⚠️ 贡献率之和为 {result.get('contrib_sum', 0):.1f}%（偏离100%较大），可能存在遗漏维度")
    unavail = result.get('unavailable_dimensions', [])
    if unavail:
        lines.append(f"\n  ℹ️ 以下维度数据不完整，未参与归因：{', '.join(c['dimension'] for c in unavail)}")
    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description='WBR 渠道归因分析')
    parser.add_argument('excel_file', help='Excel文件路径')
    parser.add_argument('--metric', help='指定分析的指标名')
    parser.add_argument('--all', action='store_true', help='扫描所有有子维度的指标')
    args = parser.parse_args()

    try:
        df = load_wbr_excel(args.excel_file)
    except Exception as e:
        print(f'加载文件失败: {e}', file=sys.stderr)
        sys.exit(1)

    if args.all:
        for r in scan_all_metrics(args.excel_file):
            print(format_result_natural_language(r))
            print()
    elif args.metric:
        print(format_result_natural_language(perform_drilldown(df, args.metric)))
    else:
        parser.print_help()
        sys.exit(1)

#!/usr/bin/env python3
"""WBR 周粒度趋势分析"""
from __future__ import annotations

import argparse
import sys
from typing import Optional, Dict, Any, List

import numpy as np

from wbr_engine.data.loader import (
    load_wbr_excel, get_metric_series, get_all_parent_metrics,
    get_children_metrics, compute_wow_series, get_week_columns,
)

MIN_WEEKS_FOR_DIRECTION_CHANGE = 3
MIN_WEEKS_FOR_CONSECUTIVE = 4
MIN_WEEKS_FOR_INFLECTION = 5
MIN_WEEKS_FOR_POSITION = 5
MIN_CHANGE_PCT = 2.0


def check_applicability(series: Optional[np.ndarray], method: str) -> Dict[str, Any]:
    min_weeks_map = {
        'direction_change': MIN_WEEKS_FOR_DIRECTION_CHANGE,
        'consecutive': MIN_WEEKS_FOR_CONSECUTIVE,
        'inflection': MIN_WEEKS_FOR_INFLECTION,
        'position': MIN_WEEKS_FOR_POSITION,
    }
    if series is None or len(series) == 0:
        return {'can_run': False, 'reason': '无有效数据'}
    min_needed = min_weeks_map.get(method, 3)
    if len(series) < min_needed:
        return {'can_run': False, 'reason': f'数据仅有{len(series)}周，{method}分析至少需要{min_needed}周'}
    return {'can_run': True, 'reason': None}


def detect_direction_change(series: np.ndarray) -> Optional[Dict[str, Any]]:
    if len(series) < 3:
        return None
    changes = np.diff(series)
    if len(changes) < 2:
        return None
    latest_change = changes[-1]
    prev_change = changes[-2]
    if (latest_change > 0 and prev_change < 0) or (latest_change < 0 and prev_change > 0):
        if abs(latest_change) < abs(series[-2]) * MIN_CHANGE_PCT / 100:
            return None
        direction = '从下降转为上升' if latest_change > 0 else '从上升转为下降'
        return {
            'type': direction, 'priority': 1,
            'latest_value': float(series[-1]), 'prev_value': float(series[-2]),
            'change': float(latest_change), 'prev_change': float(prev_change),
        }
    return None


def detect_consecutive_trend(series: np.ndarray, n: int = 3) -> Optional[Dict[str, Any]]:
    if len(series) < n + 1:
        return None
    recent = series[-(n + 1):]
    diffs = np.diff(recent)
    all_up = all(d > 0 for d in diffs)
    all_down = all(d < 0 for d in diffs)
    if not all_up and not all_down:
        return None
    total_change = recent[-1] - recent[0]
    total_change_pct = (total_change / abs(recent[0]) * 100) if recent[0] != 0 else None
    trend_type = f'连续{n}周{"上升" if all_up else "下降"}'
    return {
        'type': trend_type, 'priority': 2,
        'start_value': float(recent[0]), 'end_value': float(recent[-1]),
        'total_change': float(total_change),
        'total_change_pct': float(total_change_pct) if total_change_pct is not None else None,
        'consecutive_weeks': n,
    }


def detect_inflection(series: np.ndarray) -> Optional[Dict[str, Any]]:
    if len(series) < 5:
        return None
    prior = series[-5:-1]
    prior_diffs = np.diff(prior)
    latest_diff = series[-1] - series[-2]
    if all(d > 0 for d in prior_diffs) and latest_diff < 0:
        return {
            'type': '见顶回落', 'priority': 3,
            'peak_value': float(series[-2]), 'current_value': float(series[-1]),
            'drop': float(latest_diff),
        }
    elif all(d < 0 for d in prior_diffs) and latest_diff > 0:
        return {
            'type': '触底反弹', 'priority': 3,
            'trough_value': float(series[-2]), 'current_value': float(series[-1]),
            'bounce': float(latest_diff),
        }
    return None


def detect_position(series: np.ndarray) -> Optional[Dict[str, Any]]:
    if len(series) < 5:
        return None
    today = series[-1]
    sorted_vals = np.sort(series)
    rank_high = len(series) - np.searchsorted(sorted_vals, today, side='right') + 1
    rank_low = np.searchsorted(sorted_vals, today, side='left') + 1
    if rank_high == 1:
        return {'type': '全窗口最高', 'priority': 4, 'value': float(today), 'window_weeks': len(series)}
    elif rank_high == 2:
        return {'type': '全窗口次高', 'priority': 4, 'value': float(today), 'window_weeks': len(series)}
    elif rank_low == 1:
        return {'type': '全窗口最低', 'priority': 4, 'value': float(today), 'window_weeks': len(series)}
    elif rank_low == 2:
        return {'type': '全窗口次低', 'priority': 4, 'value': float(today), 'window_weeks': len(series)}
    return None


def analyze_trend(series: Optional[np.ndarray], metric_name: str = '') -> Dict[str, Any]:
    """综合趋势分析：按优先级顺序检测各类特征。"""
    result: Dict[str, Any] = {'metric': metric_name, 'findings': [], 'not_applicable': []}

    for method, detector in [
        ('direction_change', detect_direction_change),
        ('consecutive', detect_consecutive_trend),
        ('inflection', detect_inflection),
        ('position', detect_position),
    ]:
        check = check_applicability(series, method)
        if check['can_run']:
            finding = detector(series)
            if finding:
                result['findings'].append(finding)
        else:
            result['not_applicable'].append({'method': method, 'reason': check['reason']})

    return result


def scan_all_metrics(file_path: str) -> List[Dict[str, Any]]:
    df = load_wbr_excel(file_path)
    return [analyze_trend(get_metric_series(df, m), m) for m in get_all_parent_metrics(df)]


def format_result_natural_language(result: Dict[str, Any]) -> str:
    metric = result.get('metric', '未知指标')
    findings = result.get('findings', [])
    not_applicable = result.get('not_applicable', [])
    parts = []

    if findings:
        for f in findings:
            trend_type = f.get('type', '')
            if '上升' in trend_type or '反弹' in trend_type:
                emoji = '📈'
            elif '下降' in trend_type or '回落' in trend_type:
                emoji = '📉'
            elif '最高' in trend_type or '次高' in trend_type:
                emoji = '🔝'
            elif '最低' in trend_type or '次低' in trend_type:
                emoji = '🔻'
            else:
                emoji = '🔄'

            if 'consecutive_weeks' in f:
                pct_str = f"（累计变化 {f['total_change_pct']:+.1f}%）" if f.get('total_change_pct') else ''
                parts.append(f"{emoji} {trend_type}：从 {f['start_value']:.2f} 到 {f['end_value']:.2f}{pct_str}")
            elif 'peak_value' in f:
                parts.append(f"{emoji} {trend_type}：峰值 {f['peak_value']:.2f} → 本周 {f['current_value']:.2f}（回落 {abs(f['drop']):.2f}）")
            elif 'trough_value' in f:
                parts.append(f"{emoji} {trend_type}：谷值 {f['trough_value']:.2f} → 本周 {f['current_value']:.2f}（反弹 {f['bounce']:.2f}）")
            elif 'window_weeks' in f:
                parts.append(f"{emoji} {trend_type}：本周值 {f['value']:.2f}（近{f['window_weeks']}周）")
            elif 'latest_value' in f:
                parts.append(f"{emoji} {trend_type}：本周 {f['latest_value']:.2f}（上周 {f['prev_value']:.2f}）")
            else:
                parts.append(f"{emoji} {trend_type}")
    else:
        parts.append("未检测到显著趋势特征")

    if not_applicable:
        parts.append("以下分析因数据不足不可用：")
        parts.extend(f"  - {na['method']}：{na['reason']}" for na in not_applicable)

    return f"【{metric}】趋势分析\n" + '\n'.join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description='WBR 周粒度趋势分析')
    parser.add_argument('excel_file', help='Excel文件路径')
    parser.add_argument('--metric', help='指定分析的指标名')
    parser.add_argument('--all', action='store_true', help='扫描所有指标')
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
        series = get_metric_series(df, args.metric)
        print(format_result_natural_language(analyze_trend(series, args.metric)))
    else:
        parser.print_help()
        sys.exit(1)

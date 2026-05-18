#!/usr/bin/env python3
"""WBR 周粒度异动检测"""
from __future__ import annotations

import argparse
import sys
from typing import Optional, Dict, Any, List

import numpy as np

from wbr_engine.data.loader import (
    load_wbr_excel, get_week_columns, get_metric_series,
    get_all_parent_metrics, get_children_metrics, compute_wow,
)

MIN_WEEKS_FOR_ZSCORE = 6
MIN_WEEKS_FOR_SIMPLE = 3
SIMPLE_THRESHOLD_PCT = 15.0


def check_applicability(series: Optional[np.ndarray]) -> Dict[str, Any]:
    if series is None or len(series) == 0:
        return {'can_run': False, 'method': None, 'reason': '无有效数据，无法执行异动检测'}

    n = len(series)
    if n >= MIN_WEEKS_FOR_ZSCORE:
        return {'can_run': True, 'method': 'zscore_iqr', 'reason': None}
    elif n >= MIN_WEEKS_FOR_SIMPLE:
        return {'can_run': True, 'method': 'simple_threshold', 'reason': None}
    else:
        return {
            'can_run': False, 'method': None,
            'reason': f'数据仅有{n}周，异动检测至少需要{MIN_WEEKS_FOR_SIMPLE}周数据（当前不足）',
        }


def detect_anomaly_zscore_iqr(series: np.ndarray, z_threshold: float = 2.0,
                               iqr_k: float = 1.5) -> Dict[str, Any]:
    baseline = series[:-1]
    today = series[-1]
    mean_val = np.mean(baseline)
    std_val = np.std(baseline)

    if std_val == 0:
        z_anomaly = False
        z_score = 0.0
    else:
        z_score = (today - mean_val) / std_val
        z_anomaly = abs(z_score) >= z_threshold

    q1 = np.percentile(baseline, 25)
    q3 = np.percentile(baseline, 75)
    iqr = q3 - q1
    lower = q1 - iqr_k * iqr
    upper = q3 + iqr_k * iqr
    iqr_anomaly = (today < lower) or (today > upper)

    is_anomaly = z_anomaly and iqr_anomaly
    if not is_anomaly:
        return {'is_anomaly': False, 'method': 'zscore_iqr'}

    severity = '严重异常' if abs(z_score) >= 3.0 else '显著异常'
    return {
        'is_anomaly': True, 'method': 'zscore_iqr', 'severity': severity,
        'z_score': float(z_score), 'today_value': float(today),
        'baseline_mean': float(mean_val), 'baseline_std': float(std_val),
        'iqr_bounds': (float(lower), float(upper)),
    }


def detect_anomaly_simple(series: np.ndarray,
                           threshold_pct: float = SIMPLE_THRESHOLD_PCT) -> Dict[str, Any]:
    if len(series) < 2:
        return {'is_anomaly': False, 'method': 'simple_threshold'}
    prev = series[-2]
    curr = series[-1]
    if prev == 0:
        return {'is_anomaly': False, 'method': 'simple_threshold'}

    wow_pct = (curr - prev) / abs(prev) * 100
    is_anomaly = abs(wow_pct) >= threshold_pct
    if not is_anomaly:
        return {'is_anomaly': False, 'method': 'simple_threshold'}

    severity = '严重异常' if abs(wow_pct) >= 30 else '显著异常'
    return {
        'is_anomaly': True, 'method': 'simple_threshold', 'severity': severity,
        'wow_pct': float(wow_pct), 'today_value': float(curr),
        'prev_value': float(prev), 'threshold_pct': threshold_pct,
    }


def detect_anomaly(series: Optional[np.ndarray], metric_name: str = '') -> Dict[str, Any]:
    """统一入口：检查条件 → 选择方法 → 执行检测。"""
    check = check_applicability(series)
    if not check['can_run']:
        return {'metric': metric_name, 'applicable': False, 'reason': check['reason']}

    if check['method'] == 'zscore_iqr':
        result = detect_anomaly_zscore_iqr(series)
    else:
        result = detect_anomaly_simple(series)

    return {'metric': metric_name, 'applicable': True, **result}


def scan_all_metrics(file_path: str,
                     threshold_pct: float = SIMPLE_THRESHOLD_PCT) -> List[Dict[str, Any]]:
    df = load_wbr_excel(file_path)
    parents = get_all_parent_metrics(df)
    results = []
    for metric in parents:
        series = get_metric_series(df, metric)
        result = detect_anomaly(series, metric)
        results.append(result)
        for child in get_children_metrics(df, metric):
            child_result = detect_anomaly(get_metric_series(df, child), child)
            child_result['parent_metric'] = metric
            results.append(child_result)
    return results


def format_result_natural_language(result: Dict[str, Any]) -> str:
    metric = result.get('metric', '未知指标')
    if not result.get('applicable'):
        return f"【{metric}】异动检测不可用：{result.get('reason', '原因未知')}"
    if not result.get('is_anomaly'):
        return f"【{metric}】未检出异常波动（方法: {result.get('method', 'N/A')}）"

    severity = result.get('severity', '异常')
    method = result.get('method', '')
    if method == 'zscore_iqr':
        z = result.get('z_score', 0)
        today = result.get('today_value', 0)
        mean = result.get('baseline_mean', 0)
        direction = '上涨' if z > 0 else '下跌'
        return (f"【{metric}】⚠️ {severity}（{direction}）—— "
                f"本周值 {today:.2f}，基线均值 {mean:.2f}，Z-Score={z:.2f}，偏离基线显著")
    elif method == 'simple_threshold':
        wow = result.get('wow_pct', 0)
        today = result.get('today_value', 0)
        prev = result.get('prev_value', 0)
        direction = '上涨' if wow > 0 else '下跌'
        return (f"【{metric}】⚠️ {severity}（{direction}）—— "
                f"本周 {today:.2f}，上周 {prev:.2f}，"
                f"WoW {wow:+.1f}%（超过±{result.get('threshold_pct', 15)}%阈值）")
    return f"【{metric}】检测到异常"


def main() -> None:
    parser = argparse.ArgumentParser(description='WBR 周粒度异动检测')
    parser.add_argument('excel_file', help='Excel文件路径')
    parser.add_argument('--metric', help='指定分析的指标名')
    parser.add_argument('--all', action='store_true', help='扫描所有指标')
    parser.add_argument('--threshold', type=float, default=SIMPLE_THRESHOLD_PCT)
    args = parser.parse_args()

    try:
        df = load_wbr_excel(args.excel_file)
    except Exception as e:
        print(f'加载文件失败: {e}', file=sys.stderr)
        sys.exit(1)

    if args.all:
        results = scan_all_metrics(args.excel_file, args.threshold)
        print(f"=== 异动扫描结果 ({args.excel_file}) ===\n")
        for r in results:
            print(format_result_natural_language(r))
        anomalies = [r for r in results if r.get('is_anomaly')]
        not_applicable = [r for r in results if not r.get('applicable')]
        print(f"\n共扫描 {len(results)} 个指标，发现 {len(anomalies)} 个异动，{len(not_applicable)} 个不可用")
    elif args.metric:
        series = get_metric_series(df, args.metric)
        result = detect_anomaly(series, args.metric)
        print(format_result_natural_language(result))
    else:
        parser.print_help()
        sys.exit(1)

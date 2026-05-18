#!/usr/bin/env python3
"""lineage_grade — 用本周指标数据评判上周预测的达成情况"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

from wbr_engine.data.loader import load_wbr_excel, get_metric_value, get_week_columns

THRESHOLD_PATTERN = re.compile(
    r'^(?P<op>>=|<=|>|<|=|≥|≤)?\s*'
    r'(?P<sign>[+\-]?)\s*'
    r'(?P<num>\d+(?:\.\d+)?)\s*'
    r'(?P<unit>%|亿|万|pp|元|个|单|人|分)?$',
    re.UNICODE
)

SEMANTIC_THRESHOLDS = {
    '回升': lambda curr, prev: curr > prev,
    '回落': lambda curr, prev: curr < prev,
    '止跌': lambda curr, prev: curr >= prev,
    '止涨': lambda curr, prev: curr <= prev,
    '保持回升': lambda curr, prev: curr > prev,
    '保持': lambda curr, prev: abs(curr - prev) / abs(prev) < 0.05 if prev else False,
}


def normalize_op(op: str) -> str:
    return {'≥': '>=', '≤': '<=', '': '>='}.get(op, op)


def parse_threshold(threshold: str) -> Optional[dict]:
    threshold = threshold.strip()
    for verb in SEMANTIC_THRESHOLDS:
        if verb in threshold:
            return {'kind': 'semantic', 'verb': verb}
    m = THRESHOLD_PATTERN.match(threshold)
    if not m:
        return None
    op = normalize_op(m.group('op') or '')
    sign = m.group('sign') or ''
    num = float(m.group('num'))
    unit = m.group('unit') or ''
    if unit == 'pp':
        return {'kind': 'relative_pp', 'sign': sign or '+', 'value': num}
    if unit == '%' and sign in ('+', '-'):
        return {'kind': 'relative_pct', 'sign': sign, 'value': num}
    return {'kind': 'absolute', 'op': op, 'value': num, 'unit': unit}


def grade_prediction(pred: dict, df: Any) -> dict:
    """评判单条 prediction。"""
    metric = pred.get('metric', '').strip()
    threshold_raw = pred.get('threshold', '')
    threshold = parse_threshold(threshold_raw)

    if threshold is None:
        return {'id': pred['id'], 'status': '⏸ data_missing', 'actual': None, 'detail': f'阈值无法解析: "{threshold_raw}"'}

    week_cols = get_week_columns(df)
    if not week_cols:
        return {'id': pred['id'], 'status': '⏸ data_missing', 'actual': None, 'detail': 'Excel 中无可识别的周列'}

    latest_week = week_cols[-1]
    prev_week = week_cols[-2] if len(week_cols) >= 2 else None
    actual = get_metric_value(df, metric, latest_week)

    if actual is None:
        return {'id': pred['id'], 'status': '⏸ data_missing', 'actual': None, 'detail': f'指标 "{metric}" 在 {latest_week} 列无数据(可能名称不匹配)'}

    if threshold['kind'] == 'absolute':
        op = threshold['op']
        thr = threshold['value']
        met = {'>=': actual >= thr, '<=': actual <= thr, '>': actual > thr, '<': actual < thr, '=': abs(actual - thr) < 1e-6}.get(op, False)
        return {
            'id': pred['id'], 'status': '✅ achieved' if met else '❌ missed',
            'actual': float(actual),
            'detail': f'实际 {actual:.2f} {threshold["unit"]} vs 阈值 {op} {thr} {threshold["unit"]} (Δ={actual - thr:+.2f})',
        }

    if threshold['kind'] in ('relative_pct', 'relative_pp') and prev_week:
        prev = get_metric_value(df, metric, prev_week)
        if prev is None or prev == 0:
            return {'id': pred['id'], 'status': '⏸ data_missing', 'actual': float(actual), 'detail': '上周值缺失或为 0,无法计算变化'}
        if threshold['kind'] == 'relative_pct':
            actual_pct = (actual - prev) / abs(prev) * 100
        else:
            actual_pct = actual - prev
        sign = threshold['sign']
        target = threshold['value']
        met = actual_pct >= target if sign == '+' else actual_pct <= -target
        suffix = 'pp' if threshold['kind'] == 'relative_pp' else '%'
        return {
            'id': pred['id'], 'status': '✅ achieved' if met else '❌ missed',
            'actual': float(actual),
            'detail': f'实际 {actual_pct:+.2f}{suffix} vs 阈值 {sign}{target}{suffix}',
        }

    if threshold['kind'] == 'semantic' and prev_week:
        prev = get_metric_value(df, metric, prev_week)
        if prev is None:
            return {'id': pred['id'], 'status': '⏸ data_missing', 'actual': float(actual), 'detail': '上周值缺失,无法判断语义阈值'}
        verb = threshold['verb']
        met = SEMANTIC_THRESHOLDS[verb](actual, prev)
        return {
            'id': pred['id'], 'status': '✅ achieved' if met else '❌ missed',
            'actual': float(actual),
            'detail': f'语义阈值 "{verb}":本周 {actual:.2f} vs 上周 {prev:.2f}',
        }

    return {'id': pred['id'], 'status': '⏸ data_missing', 'actual': float(actual) if actual is not None else None, 'detail': '阈值类型不支持'}


def render_grading_md(lineage: dict, results: list) -> str:
    prev_week = lineage.get('week', 'W?')
    by_status: dict = {'✅ achieved': [], '❌ missed': [], '⏸ data_missing': []}
    for r, pred in zip(results, lineage.get('predictions', [])):
        by_status[r['status']].append((r, pred))
    n = len(results)
    lines = [f'# 上周({prev_week})预测复盘', '']
    if not results:
        lines.append('上周 lineage 中无预测项(或首次跑)。无可评判内容。')
        return '\n'.join(lines)
    if by_status['✅ achieved']:
        lines.append(f'## 已达成 ({len(by_status["✅ achieved"])}/{n})')
        for r, pred in by_status['✅ achieved']:
            lines += [f'- ✅ {r["id"]}: {pred["metric"]} {pred["threshold"]}', f'     {r["detail"]}']
        lines.append('')
    if by_status['❌ missed']:
        lines.append(f'## 偏离 ({len(by_status["❌ missed"])}/{n})')
        for r, pred in by_status['❌ missed']:
            lines += [f'- ❌ {r["id"]}: {pred["metric"]} {pred["threshold"]}', f'     {r["detail"]}(**需在 Phase 1 立 Q**)']
        lines.append('')
    if by_status['⏸ data_missing']:
        lines.append(f'## 数据未回流 ({len(by_status["⏸ data_missing"])}/{n})')
        for r, pred in by_status['⏸ data_missing']:
            lines += [f'- ⏸ {r["id"]}: {pred["metric"]} {pred["threshold"]}', f'     {r["detail"]}(延续到下周)']
        lines.append('')
    return '\n'.join(lines)


# type alias used in grade_prediction signature
from typing import Any


def main() -> None:
    parser = argparse.ArgumentParser(description='评判上周预测达成')
    parser.add_argument('--lineage', required=True)
    parser.add_argument('--indicator-data', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--output-json')
    args = parser.parse_args()

    lineage_path = Path(args.lineage)
    if not lineage_path.exists():
        print(f'❌ lineage 文件不存在: {lineage_path}', file=sys.stderr)
        sys.exit(1)

    lineage = json.loads(lineage_path.read_text(encoding='utf-8'))
    try:
        df = load_wbr_excel(args.indicator_data)
    except Exception as e:
        print(f'❌ 加载 Excel 失败: {e}', file=sys.stderr)
        sys.exit(1)

    results = [grade_prediction(p, df) for p in lineage.get('predictions', [])]
    md = render_grading_md(lineage, results)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding='utf-8')
    print(f'✅ grading.md 已写入: {out_path}')

    if args.output_json:
        json_path = Path(args.output_json)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps({'prev_week': lineage.get('week'), 'results': results}, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'   grading.json 已写入: {json_path}')

    missed = [r for r in results if r['status'] == '❌ missed']
    if missed:
        print(f'   ⚠️ {len(missed)} 条偏离,Phase 1 必须立对应 Q')
        for r in missed:
            print(f'      - {r["id"]}')

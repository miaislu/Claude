#!/usr/bin/env python3
"""skip_check — 判断本周是否进入 Skip Mode"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

MAX_DATA_MISSING = 2
MIN_SUBSTANTIVE_QUESTIONS = 2
WOW_THRESHOLD_PCT = 10.0


def count_missed_predictions(grading_data: Optional[dict]):
    if not grading_data:
        return 0, 0
    results = grading_data.get('results', [])
    missed = sum(1 for r in results if r.get('status', '').startswith('❌'))
    data_missing = sum(1 for r in results if r.get('status', '').startswith('⏸'))
    return missed, data_missing


def count_big_anomalies(anomaly_text: str) -> int:
    count = 0
    for line in anomaly_text.splitlines():
        wow_m = re.search(r'WoW\s*([+\-]?\d+(?:\.\d+)?)\s*%', line)
        if wow_m and abs(float(wow_m.group(1))) >= WOW_THRESHOLD_PCT:
            count += 1
            continue
        if '严重异常' in line:
            count += 1
    return count


def count_substantive_questions(questions_md_text: str, gate_report: Optional[dict] = None) -> int:
    if gate_report:
        return sum(1 for q in gate_report.get('questions', []) if q.get('passed'))
    qids = set()
    for line in questions_md_text.splitlines():
        m = re.match(r'^\s*(?:#+\s*|[-*]\s+)?Q(\d+)\b', line)
        if m:
            qids.add(int(m.group(1)))
    return len(qids)


def check_skip_eligibility(args) -> dict:
    blockers = []
    metrics = {}

    grading_data = None
    if args.grading_json and Path(args.grading_json).exists():
        try:
            grading_data = json.loads(Path(args.grading_json).read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            print(f'⚠️ grading-json 解析失败: {e}', file=sys.stderr)

    missed, data_missing = count_missed_predictions(grading_data)
    metrics['missed_predictions'] = missed
    metrics['data_missing_predictions'] = data_missing
    if missed > 0:
        blockers.append(f'上周有 {missed} 条预测偏离(❌)')
    if data_missing > MAX_DATA_MISSING:
        blockers.append(f'上周 {data_missing} 条预测数据未回流(超过 {MAX_DATA_MISSING})')

    anomaly_text = ''
    if args.anomaly_txt and Path(args.anomaly_txt).exists():
        anomaly_text = Path(args.anomaly_txt).read_text(encoding='utf-8')
    big_anomalies = count_big_anomalies(anomaly_text)
    metrics['big_anomalies'] = big_anomalies
    if big_anomalies > 0:
        blockers.append(f'本周有 {big_anomalies} 条 |WoW|>={WOW_THRESHOLD_PCT}% 或严重异常')

    metrics['user_questions'] = args.user_questions_count
    if args.user_questions_count > 0:
        blockers.append(f'用户指定了 {args.user_questions_count} 条核心问题')

    questions_text = ''
    if args.questions_md and Path(args.questions_md).exists():
        questions_text = Path(args.questions_md).read_text(encoding='utf-8')

    gate_report = None
    if args.gate_report and Path(args.gate_report).exists():
        try:
            gate_report = json.loads(Path(args.gate_report).read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            pass

    substantive = count_substantive_questions(questions_text, gate_report)
    metrics['substantive_questions'] = substantive
    if substantive >= MIN_SUBSTANTIVE_QUESTIONS:
        blockers.append(f'Phase 1 产出 {substantive} 条有料问题(≥{MIN_SUBSTANTIVE_QUESTIONS})')

    eligible = len(blockers) == 0
    return {
        'eligible': eligible, 'mode': 'skip' if eligible else 'full',
        'blockers': blockers, 'metrics': metrics,
        'thresholds': {'max_data_missing': MAX_DATA_MISSING, 'min_substantive_questions': MIN_SUBSTANTIVE_QUESTIONS, 'wow_threshold_pct': WOW_THRESHOLD_PCT},
    }


def render_human(result: dict) -> str:
    mode = result['mode']
    lines = [f'{"🟢" if mode == "skip" else "🔵"} Skip Mode 判定: **{mode.upper()}**', '', '指标:']
    for k, v in result['metrics'].items():
        lines.append(f'  - {k}: {v}')
    if result['blockers']:
        lines += ['', '未触发 Skip 的原因:'] + [f'  ✗ {b}' for b in result['blockers']]
    else:
        lines += ['', '✅ 所有条件均满足 Skip Mode,可输出极简版。']
    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description='判断是否进入 Skip Mode')
    parser.add_argument('--grading-json')
    parser.add_argument('--anomaly-txt')
    parser.add_argument('--user-questions-count', type=int, default=0)
    parser.add_argument('--questions-md')
    parser.add_argument('--gate-report')
    parser.add_argument('--output')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    result = check_skip_eligibility(args)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_human(result))

    sys.exit(0 if result['eligible'] else 1)

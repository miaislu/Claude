#!/usr/bin/env python3
"""lineage_parse — 从 WBR 报告 markdown 抽取下周 lineage.json"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Tuple

PREDICTION_PATTERNS = [
    re.compile(
        r'📌\s*\[?(?P<id>pred_W\d+_\d+)\]?[:\s]+'
        r'(?P<metric>[^\d≥≤>=<+\-]+?)\s*'
        r'(?P<threshold>[≥≤><=]+\s*[+\-]?\d[\d.,%≥≤><=亿万pp元个单人.]*[a-zA-Z%亿万元pp]*)\s*,?\s*'
        r'by\s+(?P<by_week>W\d+)',
        re.UNICODE
    ),
    re.compile(
        r'📌\s*\[?(?P<id>pred_W\d+_\d+)\]?[:\s]+'
        r'(?P<metric>[^\d≥≤>=<+\-]+?)\s*'
        r'(?P<threshold>[≥≤><=]+\s*[+\-]?\d[\d.,%≥≤><=亿万pp元个单人.]*[a-zA-Z%亿万元pp]*)\s*,?\s*'
        r'to\s+(?P<by_week>W\d+)',
        re.UNICODE
    ),
]

INVALID_PRED_PATTERNS = [
    (re.compile(r'📌[^[]*持续(关注|追踪|观察)'), '不可量化追踪项(持续关注/追踪/观察)'),
    (re.compile(r'📌[^[]*(趋势|向好|向坏|改善|恶化)'), '无具体阈值(只写方向词)'),
    (re.compile(r'📌'), '通用不匹配:不符合 [pred_W{n}_xxx] 指标 阈值 by 周次 格式'),
]

HYPOTHESIS_PATTERN = re.compile(
    r'\[(?:假设·待验证|相关性推断[,，]\s*待验证)\][^\n]*', re.UNICODE
)

QUESTION_HEADER = re.compile(
    r'^\s*(?:#+\s*|[-*]\s+)?'
    r'Q(?P<num>\d+)'
    r'\s*(?:\[来源[:：]\s*(?P<source>[^\]]+)\])?'
    r'\s*[:：.]?\s*'
    r'(?P<inline_text>.*)$',
    re.UNICODE
)


def find_section(md_text: str, heading_pattern: str) -> str | None:
    lines = md_text.split('\n')
    start_idx = None
    start_level = None
    for i, line in enumerate(lines):
        m = re.match(r'^(#+)\s+(.+)$', line)
        if m and re.search(heading_pattern, m.group(2)):
            start_idx = i
            start_level = len(m.group(1))
            break
    if start_idx is None:
        return None
    end_idx = len(lines)
    for j in range(start_idx + 1, len(lines)):
        m = re.match(r'^(#+)\s+', lines[j])
        if m and len(m.group(1)) <= start_level:
            end_idx = j
            break
    return '\n'.join(lines[start_idx + 1:end_idx])


def parse_predictions(md_text: str, week: str) -> Tuple[List[dict], List[str]]:
    section = find_section(md_text, r'下周追踪|行动建议')
    if section is None:
        return [], [f'⚠️ 未找到"下周追踪"段,跳过预测抽取(品类={week})']

    predictions = []
    errors = []
    sub_section = section
    sub_match = re.search(r'(?:^|\n)\s*\d+\.\s*下周追踪[:：]?\s*(.+?)(?=\n\s*\d+\.|$)', section, re.DOTALL)
    if sub_match:
        sub_section = sub_match.group(1)

    for line in sub_section.split('\n'):
        line = line.strip()
        if not line.startswith('📌'):
            continue
        matched = False
        for pat in PREDICTION_PATTERNS:
            m = pat.search(line)
            if m:
                predictions.append({
                    'id': m.group('id'),
                    'metric': m.group('metric').strip().rstrip(',,'),
                    'threshold': m.group('threshold').strip().rstrip(',,').strip(),
                    'by_week': m.group('by_week'),
                    'raw_line': line,
                })
                matched = True
                break
        if not matched:
            for invalid_pat, reason in INVALID_PRED_PATTERNS:
                if invalid_pat.search(line):
                    errors.append(f'❌ 不规范的预测行 ({reason}): {line}')
                    break

    return predictions, errors


def parse_hypotheses(md_text: str) -> List[dict]:
    matches = HYPOTHESIS_PATTERN.findall(md_text)
    return [{'id': f'h_auto_{i+1}', 'text': m.strip(), 'status': 'untested'} for i, m in enumerate(matches)]


def parse_unresolved_anomalies(md_text: str) -> List[dict]:
    section = find_section(md_text, r'无法解释的异动')
    if section is None:
        return []
    anomalies = []
    rows = re.findall(r'^\|\s*(?![-:|\s]+\|)(.+?)\s*\|$', section, re.MULTILINE)
    for i, row in enumerate(rows):
        cells = [c.strip() for c in row.split('|')]
        if len(cells) < 5:
            continue
        if cells[0] in ('指标', '指标名'):
            continue
        anomalies.append({
            'id': f'anom_auto_{i+1}', 'metric': cells[0], 'change_text': cells[1],
            'rule_out': cells[2], 'possible_direction': cells[3], 'judgement': cells[4],
        })
    return anomalies


def parse_questions(md_text: str) -> List[dict]:
    section = find_section(md_text, r'本周核心问题|0、本周核心问题')
    if section is None:
        return []
    lines = section.split('\n')
    questions = []
    for i, line in enumerate(lines):
        m = QUESTION_HEADER.match(line)
        if not m:
            continue
        inline = m.group('inline_text').strip()
        text = inline
        if not text:
            for j in range(i + 1, len(lines)):
                nxt = lines[j].strip()
                if not nxt:
                    continue
                if QUESTION_HEADER.match(nxt) or nxt.startswith('#'):
                    break
                text = nxt
                break
        if text:
            questions.append({'id': f'Q{m.group("num")}', 'text': text, 'source': (m.group('source') or '').strip()})
    return questions


def cn_now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')


def main() -> None:
    parser = argparse.ArgumentParser(description='抽取 WBR 报告中的 lineage 字段')
    parser.add_argument('--input', required=True)
    parser.add_argument('--week', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--category', default='')
    parser.add_argument('--strict', action='store_true')
    args = parser.parse_args()

    md_path = Path(args.input)
    if not md_path.exists():
        print(f'❌ 输入文件不存在: {md_path}', file=sys.stderr)
        sys.exit(1)

    md_text = md_path.read_text(encoding='utf-8')
    predictions, errors = parse_predictions(md_text, args.week)
    hypotheses = parse_hypotheses(md_text)
    anomalies = parse_unresolved_anomalies(md_text)
    questions = parse_questions(md_text)

    if errors:
        print('=== 预测抽取错误 ===', file=sys.stderr)
        for e in errors:
            print(e, file=sys.stderr)
        if args.strict:
            print(f'❌ strict 模式:存在 {len(errors)} 条不规范预测,退出', file=sys.stderr)
            sys.exit(2)

    lineage = {
        'schema_version': '1.0', 'week': args.week, 'category': args.category,
        'generated_at': cn_now(), 'predictions': predictions,
        'open_hypotheses': hypotheses, 'unresolved_anomalies': anomalies,
        'this_week_questions': questions, 'parse_errors': errors,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(lineage, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'✅ lineage 已写入: {out_path}')
    print(f'   predictions: {len(predictions)}')
    print(f'   open_hypotheses: {len(hypotheses)}')
    print(f'   unresolved_anomalies: {len(anomalies)}')
    print(f'   this_week_questions: {len(questions)}')
    if errors:
        print(f'   ⚠️ 解析错误: {len(errors)} 条(非 strict 模式已记入 parse_errors 字段)')

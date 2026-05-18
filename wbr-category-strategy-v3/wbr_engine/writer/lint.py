#!/usr/bin/env python3
"""positive_lint — 正向句式检查"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List

NUMBER_WITH_UNIT = re.compile(
    r'\d+(?:\.\d+)?\s*(?:%|亿|万|pp|元|个|单|人|分钟|秒|天|周|月|次|条|家|份)', re.UNICODE
)
ACTION_VERBS = re.compile(
    r'(?:投放|投入|下线|上线|启动|停止|关闭|开启|'
    r'调整|增加|减少|新增|删除|拆分|合并|迁移|转移|'
    r'扩充|收缩|升级|降级|替换|改|调|拓展|压缩|'
    r'试点|实验|测试|灰度|铺开|回收|延期|提前|'
    r'对接|联动|协同|联合|绑定|解绑|授权|撤销|'
    r'选品|铺货|备货|清仓|促销|让利|补贴|涨价|降价)', re.UNICODE
)
DIRECTION_MARKER = re.compile(
    r'(?:WoW|YoY|MoM|QoQ|HoH)\s*[+\-]|'
    r'(?:回升|回落|提升|下滑|增长|下降|止跌|反弹|见顶|触底|'
    r'飙升|暴跌|攀升|滑落|回暖|降温|加速|放缓|转正|转负)', re.UNICODE
)
SKIP_PATTERNS = [
    re.compile(r'^\s*$'),
    re.compile(r'^#+\s'),
    re.compile(r'^\s*[-*+]\s*$'),
    re.compile(r'^\s*\|'),
    re.compile(r'^\s*```'),
    re.compile(r'^\s*>'),
    re.compile(r'^\s*\d+\.\s+继续|^\s*\d+\.\s+调整|^\s*\d+\.\s+调查|^\s*\d+\.\s+下周追踪'),
    re.compile(r'^\s*📌'),
    re.compile(r'^\s*\*\*[^*]+\*\*\s*[:：]?\s*$'),
    re.compile(r'^\s*-{3,}\s*$'),
]
META_SECTIONS = ['数据完整性', '核心问题回答', '审计附件', '上周预测复盘', '本周核心问题']


def split_sentences(text: str) -> List[str]:
    parts = re.split(r'([。!?\?!]+|[,;,;]+)', text)
    sentences = []
    buf = ''
    for p in parts:
        if not p:
            continue
        if re.match(r'^[。!?\?!,;,;]+$', p):
            sentences.append((buf + p).strip())
            buf = ''
        else:
            buf = p
    if buf.strip():
        sentences.append(buf.strip())
    return [s for s in sentences if s]


def is_substantive(sentence: str):
    matched = []
    if NUMBER_WITH_UNIT.search(sentence):
        matched.append('数字+单位')
    if ACTION_VERBS.search(sentence):
        matched.append('动作动词')
    if DIRECTION_MARKER.search(sentence):
        matched.append('变化方向')
    return (len(matched) > 0, matched)


def is_in_meta_section(line_idx: int, lines: List[str]) -> bool:
    for i in range(line_idx, -1, -1):
        m = re.match(r'^#+\s+(.+?)\s*$', lines[i])
        if m:
            return any(meta in m.group(1) for meta in META_SECTIONS)
    return False


def lint_markdown(md_text: str) -> List[dict]:
    lines = md_text.split('\n')
    flagged = []
    for idx, line in enumerate(lines, start=1):
        if any(pat.match(line) for pat in SKIP_PATTERNS):
            continue
        if is_in_meta_section(idx - 1, lines):
            continue
        stripped = line.strip()
        if len(stripped) < 6:
            continue
        for sent in split_sentences(stripped):
            core = re.sub(r'[。!?\?!,;,;\s]+$', '', sent)
            if len(core) < 4:
                continue
            passed, _ = is_substantive(sent)
            if not passed:
                flagged.append({'line': idx, 'sentence': sent, 'reason': '无数字/无动作/无方向'})
    return flagged


def render_report(flagged: List[dict], md_path: str) -> str:
    if not flagged:
        return f'✅ {md_path}: 所有子句通过正向句式检查\n'
    lines = [f'⚠️ {md_path}: {len(flagged)} 条子句信息量不足', '', '逐条标记(供 critic / revisor 使用):', '']
    for item in flagged:
        lines += [f'  L{item["line"]:>4}: {item["sentence"]}', f'         → {item["reason"]}']
    lines.append('')
    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description='正向句式检查')
    parser.add_argument('input')
    parser.add_argument('--output')
    parser.add_argument('--strict', action='store_true')
    args = parser.parse_args()

    md_path = Path(args.input)
    if not md_path.exists():
        print(f'❌ 文件不存在: {md_path}', file=sys.stderr)
        sys.exit(1)

    flagged = lint_markdown(md_path.read_text(encoding='utf-8'))
    report = render_report(flagged, str(md_path))

    if args.output:
        Path(args.output).write_text(report, encoding='utf-8')
        print(f'✅ 报告已写入: {args.output}')
    else:
        print(report)

    if args.strict and flagged:
        sys.exit(1)

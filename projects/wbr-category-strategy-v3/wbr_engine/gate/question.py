#!/usr/bin/env python3
"""question_gate — Phase 1 问题质量门禁"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Tuple

METRIC_VOCAB = [
    'GTV', '订单量', '订单数', 'ARPU', 'CAC', '客单价', '单均价', '美补率',
    '新客', '老客', '复购', '留存', '渗透率', 'CTR', 'CXR', '转化率', '转化',
    '风险水位', '核销率', '持券', '投券', 'ROI', 'MTD', 'RF', 'RF达成', '达成率',
    'DAU', 'WAU', 'MAU', '核心品', '心智品', '货盘', 'SKU',
    '库存', '覆盖', '门店', '配送', '冷链', '履约',
    '曝光', '点击', '搜索', '推荐', 'feeds', '金刚', '猜你喜欢',
    '专项券', '红包', '神券', '主券', '辅领',
]
ACTION_VOCAB = [
    '投放', '下线', '上线', '调整', '调整为', '拓展', '收缩',
    '拉动', '收窄', '扩大', '收回', '补贴', '涨价', '降价',
    '调价', '选品', '铺货', '清仓', '促销', '让利',
    '试点', '灰度', '实验', '替换', '切换',
]
SUB_CATEGORY_HINTS = [
    '啤酒', '白酒', '红酒', '黄酒', '精酿', '葡萄酒',
    '手机', '家电', '小家电', '3C',
    '生鲜', '水果', '蔬菜', '肉禽', '海鲜',
    '日百', '美妆', '个护', '休食', '酒饮',
    '便利店', '超市KA', '便利店KA', '官旗', '闪电仓', '小象超市',
    '歪马', '松鼠',
]
COMPARISON_KEYWORDS = [
    'vs', 'VS', '与', '相比', '比', '相对',
    '超过', '高于', '低于', '不及', '达到', '突破',
    '持平', '一致', '回升', '回落', '止跌', '止涨', '反弹',
    '维持', '保持', '继续', '反向', '同向',
]
NUMBER_THRESHOLD = re.compile(
    r'(?:>=|<=|>|<|≥|≤|=|约)\s*\d+(?:\.\d+)?\s*[%亿万pp元个单人]|'
    r'[+\-]\s*\d+(?:\.\d+)?\s*(?:%|pp|亿|万|元)|'
    r'\d+(?:\.\d+)?\s*(?:倍|档|周|月)',
    re.UNICODE
)
TIME_WINDOW = re.compile(
    r'本周|上周|下周|本月|上月|MTD|RF|W\d+|至 W\d+|于 W\d+|从 W\d+', re.UNICODE
)
DECISION_HINTS = ACTION_VOCAB + [
    '继续', '调整', '调查', '扩大', '收缩', '停止', '启动',
    '关闭', '开启', '推进', '撤回', '加大', '减小',
]
VAGUE_AUTOFAIL_PHRASES = [
    '是否承压', '是否健康', '是否良好', '是否稳健',
    '如何看待', '如何应对', '怎么看', '怎么办',
    '是否需要关注', '是否值得关注', '是否乐观',
    '前景如何', '形势如何', '态势如何',
]
WEAK_DECISION_THEMES = ['行业', '宏观', '大环境', '竞争格局', '市场氛围', '消费心智', '消费者偏好']

QUESTION_BLOCK = re.compile(
    r'(?:^|\n)\s*(?:#+\s*|[-*]\s+)?Q(?P<num>\d+)'
    r'\s*(?:\[来源[:：]\s*(?P<source>[^\]]+)\])?\s*[:：.]?\s*(?P<inline>[^\n]*)',
    re.UNICODE
)


def parse_questions(md_text: str) -> List[dict]:
    lines = md_text.split('\n')
    qs = []
    i = 0
    while i < len(lines):
        m = QUESTION_BLOCK.match('\n' + lines[i])
        if not m:
            i += 1
            continue
        text = m.group('inline').strip()
        if not text:
            for j in range(i + 1, len(lines)):
                nxt = lines[j].strip()
                if not nxt:
                    continue
                if QUESTION_BLOCK.match('\n' + nxt) or nxt.startswith('#'):
                    break
                text = nxt
                break
        if text:
            qs.append({'id': f'Q{m.group("num")}', 'source': (m.group('source') or '').strip(), 'text': text})
        i += 1
    return qs


def check_specificity(text: str) -> Tuple[bool, str]:
    for phrase in VAGUE_AUTOFAIL_PHRASES:
        if phrase in text:
            return False, f'含模糊短语"{phrase}"'
    for v in METRIC_VOCAB:
        if v in text:
            return True, f'指标"{v}"'
    for v in ACTION_VOCAB:
        if v in text:
            return True, f'动作"{v}"'
    for v in SUB_CATEGORY_HINTS:
        if v in text:
            return True, f'实体"{v}"'
    return False, '未含具体指标/动作/业务实体'


def check_falsifiability(text: str) -> Tuple[bool, str]:
    reasons = []
    if NUMBER_THRESHOLD.search(text):
        reasons.append('含阈值')
    for kw in COMPARISON_KEYWORDS:
        if kw in text:
            reasons.append(f'含比较词"{kw}"')
            break
    if TIME_WINDOW.search(text):
        reasons.append('含时间窗')
    return (True, ' / '.join(reasons)) if reasons else (False, '无可比标准(无阈值/比较词/时间窗)')


def check_decision_relevance(text: str) -> Tuple[bool, str]:
    for theme in WEAK_DECISION_THEMES:
        if theme in text:
            return False, f'问题指向弱决策主题"{theme}"'
    for v in DECISION_HINTS:
        if v in text:
            return True, f'含决策动词"{v}"'
    for v in SUB_CATEGORY_HINTS:
        if v in text:
            return True, f'指向具体业务单元"{v}"'
    for v in METRIC_VOCAB:
        if v in text:
            return True, f'指向具体指标"{v}",可挂决策'
    return False, '未指向具体动作/单元/指标,决策路径不明'


def gate_question(q: dict) -> dict:
    text = q['text']
    spec_passed, spec_reason = check_specificity(text)
    fals_passed, fals_reason = check_falsifiability(text)
    dec_passed, dec_reason = check_decision_relevance(text)
    passed = spec_passed and fals_passed and dec_passed
    suggestions = []
    if not spec_passed:
        suggestions.append('补充具体指标(GTV/订单量等)、动作动词或子品类名称')
    if not fals_passed:
        suggestions.append('补充可比标准:阈值(±X%)、比较对象(vs 上周/去年)或时间窗(W16)')
    if not dec_passed:
        suggestions.append('明确这条问题的答案会改变下周哪个动作')
    return {
        'id': q['id'], 'source': q.get('source', ''), 'text': text, 'passed': passed,
        'dimensions': {
            'specificity': {'passed': spec_passed, 'reason': spec_reason},
            'falsifiability': {'passed': fals_passed, 'reason': fals_reason},
            'decision_relevance': {'passed': dec_passed, 'reason': dec_reason},
        },
        'suggestions': suggestions,
    }


def render_md_report(results: List[dict]) -> str:
    passed = [r for r in results if r['passed']]
    failed = [r for r in results if not r['passed']]
    lines = ['# Question Gate Report', '', f'**总计 {len(results)} 条**:✅ {len(passed)} 通过 / ❌ {len(failed)} 未通过', '']
    if passed:
        lines.append(f'## ✅ 通过 ({len(passed)})')
        for r in passed:
            lines.append(f'- **{r["id"]}** [{r["source"]}]: {r["text"]}')
            for dim, val in r['dimensions'].items():
                lines.append(f'  - {dim} {"✅" if val["passed"] else "❌"} {val["reason"]}')
        lines.append('')
    if failed:
        lines.append(f'## ❌ 未通过 ({len(failed)})')
        for r in failed:
            lines.append(f'- **{r["id"]}** [{r["source"]}]: {r["text"]}')
            for dim, val in r['dimensions'].items():
                lines.append(f'  - {dim} {"✅" if val["passed"] else "❌"} {val["reason"]}')
            lines.append('  - **改写建议**:')
            for s in r['suggestions']:
                lines.append(f'    - {s}')
        lines.append('')
    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description='Phase 1 问题质量门禁')
    parser.add_argument('input')
    parser.add_argument('--output')
    parser.add_argument('--md')
    parser.add_argument('--strict', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    md_path = Path(args.input)
    if not md_path.exists():
        print(f'❌ 文件不存在: {md_path}', file=sys.stderr)
        sys.exit(2)

    questions = parse_questions(md_path.read_text(encoding='utf-8'))
    if not questions:
        print('⚠️ 未在文件中找到任何 Q\\d+ 项', file=sys.stderr)
        sys.exit(2)

    results = [gate_question(q) for q in questions]
    payload = {'total': len(results), 'passed': sum(1 for r in results if r['passed']), 'failed': sum(1 for r in results if not r['passed']), 'questions': results}

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.md:
        Path(args.md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md).write_text(render_md_report(results), encoding='utf-8')
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_md_report(results))

    if args.strict and payload['failed'] > 0:
        sys.exit(1)

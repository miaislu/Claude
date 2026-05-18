"""Unit tests for scripts/lineage_parse.py"""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from _testutil import FIXTURES_DIR, SCRIPTS_DIR

from wbr_engine.lineage.parse import (
    parse_predictions,
    parse_questions,
    parse_unresolved_anomalies,
    parse_hypotheses,
)


SAMPLE_REPORT = (FIXTURES_DIR / 'sample_W14_report.md').read_text(encoding='utf-8')


class TestParsePredictions(unittest.TestCase):
    def test_valid_predictions_parsed(self):
        preds, errors = parse_predictions(SAMPLE_REPORT, 'W14')
        ids = [p['id'] for p in preds]
        self.assertEqual(ids, ['pred_W14_001', 'pred_W14_002', 'pred_W14_003'])

    def test_threshold_no_trailing_comma(self):
        preds, _ = parse_predictions(SAMPLE_REPORT, 'W14')
        for p in preds:
            self.assertFalse(p['threshold'].endswith(','),
                             f'threshold "{p["threshold"]}" has trailing comma')
            self.assertFalse(p['threshold'].endswith(','),
                             f'threshold "{p["threshold"]}" has trailing 中文逗号')

    def test_metric_extracted(self):
        preds, _ = parse_predictions(SAMPLE_REPORT, 'W14')
        metrics = [p['metric'] for p in preds]
        self.assertIn('啤酒消费GTV', metrics)
        self.assertIn('风险水位', metrics)
        self.assertIn('啤酒新客CAC', metrics)

    def test_by_week_extracted(self):
        preds, _ = parse_predictions(SAMPLE_REPORT, 'W14')
        for p in preds:
            self.assertEqual(p['by_week'], 'W15')

    def test_invalid_lines_collected_as_errors(self):
        _, errors = parse_predictions(SAMPLE_REPORT, 'W14')
        self.assertEqual(len(errors), 2)
        self.assertTrue(any('持续关注' in e for e in errors))
        self.assertTrue(any('保持向好' in e for e in errors))

    def test_no_predictions_section_returns_empty(self):
        preds, errors = parse_predictions('## 无关段落\n仅普通文字', 'W15')
        self.assertEqual(preds, [])
        # 找不到段落应至少产出一条 warning
        self.assertEqual(len(errors), 1)


class TestParseQuestions(unittest.TestCase):
    def test_questions_parsed_with_source(self):
        qs = parse_questions(SAMPLE_REPORT)
        ids = [q['id'] for q in qs]
        self.assertIn('Q1', ids)
        self.assertIn('Q2', ids)
        q1 = next(q for q in qs if q['id'] == 'Q1')
        self.assertEqual(q1['source'], '用户指定')
        self.assertIn('专项券', q1['text'])

    def test_no_questions_section_returns_empty(self):
        qs = parse_questions('## 无问题段\n普通文字')
        self.assertEqual(qs, [])


class TestParseAnomalies(unittest.TestCase):
    def test_table_rows_parsed(self):
        anoms = parse_unresolved_anomalies(SAMPLE_REPORT)
        self.assertEqual(len(anoms), 1)
        self.assertEqual(anoms[0]['metric'], '精酿订单量')
        self.assertIn('WoW-9%', anoms[0]['change_text'])

    def test_no_anomaly_section_returns_empty(self):
        self.assertEqual(parse_unresolved_anomalies('## 无段落'), [])


class TestParseHypotheses(unittest.TestCase):
    def test_finds_marked_paragraphs(self):
        text = '某段 [假设·待验证] 啤酒下滑可能是渠道收缩\n另一段 [相关性推断,待验证] 价高人少'
        hs = parse_hypotheses(text)
        self.assertEqual(len(hs), 2)

    def test_no_markers_returns_empty(self):
        self.assertEqual(parse_hypotheses('普通文字,无标记'), [])


class TestCli(unittest.TestCase):
    """End-to-end CLI smoke test"""

    def test_cli_produces_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'lineage.json'
            result = subprocess.run(
                ['python3', str(SCRIPTS_DIR / 'lineage_parse.py'),
                 '--input', str(FIXTURES_DIR / 'sample_W14_report.md'),
                 '--week', 'W14',
                 '--category', '啤酒',
                 '--output', str(out)],
                capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(out.read_text(encoding='utf-8'))
            self.assertEqual(len(data['predictions']), 3)
            self.assertEqual(len(data['unresolved_anomalies']), 1)
            self.assertEqual(len(data['this_week_questions']), 2)
            self.assertEqual(len(data['parse_errors']), 2)

    def test_strict_mode_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'lineage.json'
            result = subprocess.run(
                ['python3', str(SCRIPTS_DIR / 'lineage_parse.py'),
                 '--input', str(FIXTURES_DIR / 'sample_W14_report.md'),
                 '--week', 'W14', '--output', str(out), '--strict'],
                capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 2)


if __name__ == '__main__':
    unittest.main()

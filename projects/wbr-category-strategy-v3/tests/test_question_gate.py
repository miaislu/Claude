"""Unit tests for scripts/question_gate.py"""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from _testutil import FIXTURES_DIR, SCRIPTS_DIR

from wbr_engine.gate.question import (
    parse_questions,
    check_specificity,
    check_falsifiability,
    check_decision_relevance,
    gate_question,
)


GOOD_MD = (FIXTURES_DIR / 'sample_questions_good.md').read_text(encoding='utf-8')
BAD_MD = (FIXTURES_DIR / 'sample_questions_bad.md').read_text(encoding='utf-8')


class TestParse(unittest.TestCase):
    def test_three_good_questions(self):
        qs = parse_questions(GOOD_MD)
        self.assertEqual(len(qs), 3)

    def test_three_bad_questions(self):
        qs = parse_questions(BAD_MD)
        self.assertEqual(len(qs), 3)

    def test_source_parsed(self):
        qs = parse_questions(GOOD_MD)
        self.assertEqual(qs[0]['source'], '用户指定')


class TestSpecificity(unittest.TestCase):
    def test_vague_phrase_autofails(self):
        passed, reason = check_specificity('GTV 是否承压?')
        self.assertFalse(passed)
        self.assertIn('承压', reason)

    def test_metric_term_passes(self):
        passed, reason = check_specificity('啤酒 GTV 是否回升至 2.0 亿?')
        self.assertTrue(passed)

    def test_action_verb_passes(self):
        passed, _ = check_specificity('本周投放专项券是否有效?')
        self.assertTrue(passed)

    def test_no_specific_terms_fails(self):
        passed, _ = check_specificity('整体表现如何变化?')
        self.assertFalse(passed)


class TestFalsifiability(unittest.TestCase):
    def test_threshold_passes(self):
        passed, _ = check_falsifiability('GTV 能否突破 2.0 亿?')
        self.assertTrue(passed)

    def test_comparison_keyword_passes(self):
        passed, _ = check_falsifiability('白酒销售相比上周回升?')
        self.assertTrue(passed)

    def test_time_window_passes(self):
        passed, _ = check_falsifiability('本周新客数是否止跌?')
        self.assertTrue(passed)

    def test_no_signal_fails(self):
        passed, _ = check_falsifiability('用户增长是否健康?')
        self.assertFalse(passed)


class TestDecisionRelevance(unittest.TestCase):
    def test_weak_theme_fails(self):
        passed, reason = check_decision_relevance('如何看待行业格局?')
        self.assertFalse(passed)
        self.assertIn('行业', reason)

    def test_action_verb_passes(self):
        passed, _ = check_decision_relevance('是否调整选品策略?')
        self.assertTrue(passed)

    def test_sub_category_passes(self):
        passed, _ = check_decision_relevance('白酒下周走势?')
        self.assertTrue(passed)

    def test_metric_passes_as_decision_hook(self):
        passed, _ = check_decision_relevance('GTV 是否回升?')
        self.assertTrue(passed)


class TestGateQuestion(unittest.TestCase):
    def test_good_question_all_pass(self):
        q = {'id': 'Q1', 'source': '用户', 'text': '白酒新客数能否回升至 ≥ 3.8 万?'}
        r = gate_question(q)
        self.assertTrue(r['passed'])
        for dim in r['dimensions'].values():
            self.assertTrue(dim['passed'])

    def test_bad_question_fails(self):
        q = {'id': 'Q1', 'source': '', 'text': '业务是否承压?'}
        r = gate_question(q)
        self.assertFalse(r['passed'])

    def test_suggestions_provided_on_failure(self):
        q = {'id': 'Q1', 'source': '', 'text': '业务是否承压?'}
        r = gate_question(q)
        self.assertGreater(len(r['suggestions']), 0)


class TestCli(unittest.TestCase):
    def _run(self, input_path, *extra):
        cmd = ['python3', str(SCRIPTS_DIR / 'question_gate.py'), str(input_path)]
        cmd.extend(extra)
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_good_questions_pass(self):
        r = self._run(FIXTURES_DIR / 'sample_questions_good.md')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('3 通过', r.stdout)

    def test_bad_questions_strict_exits_one(self):
        r = self._run(FIXTURES_DIR / 'sample_questions_bad.md', '--strict')
        self.assertEqual(r.returncode, 1)

    def test_output_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'gate.json'
            self._run(FIXTURES_DIR / 'sample_questions_good.md', '--output', str(out))
            data = json.loads(out.read_text(encoding='utf-8'))
            self.assertEqual(data['total'], 3)
            self.assertEqual(data['passed'], 3)


if __name__ == '__main__':
    unittest.main()

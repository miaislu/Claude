"""Unit tests for scripts/skip_check.py"""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from _testutil import FIXTURES_DIR, SCRIPTS_DIR

from wbr_engine.gate.skip import (
    count_missed_predictions,
    count_big_anomalies,
    count_substantive_questions,
)


ANOMALY_QUIET = (FIXTURES_DIR / 'sample_anomaly_quiet.txt').read_text(encoding='utf-8')
ANOMALY_NOISY = (FIXTURES_DIR / 'sample_anomaly_noisy.txt').read_text(encoding='utf-8')

GRADING_ALL_OK = json.loads((FIXTURES_DIR / 'sample_grading_all_achieved.json').read_text(encoding='utf-8'))
GRADING_WITH_MISS = json.loads((FIXTURES_DIR / 'sample_grading_with_miss.json').read_text(encoding='utf-8'))


class TestCountMissed(unittest.TestCase):
    def test_all_achieved_zero_missed(self):
        missed, missing = count_missed_predictions(GRADING_ALL_OK)
        self.assertEqual(missed, 0)
        self.assertEqual(missing, 0)

    def test_with_miss_one_missed(self):
        missed, _ = count_missed_predictions(GRADING_WITH_MISS)
        self.assertEqual(missed, 1)

    def test_none_input_returns_zero(self):
        missed, missing = count_missed_predictions(None)
        self.assertEqual(missed, 0)
        self.assertEqual(missing, 0)


class TestCountAnomalies(unittest.TestCase):
    def test_quiet_returns_zero(self):
        self.assertEqual(count_big_anomalies(ANOMALY_QUIET), 0)

    def test_noisy_detects_wow_25_pct(self):
        n = count_big_anomalies(ANOMALY_NOISY)
        self.assertGreaterEqual(n, 1)

    def test_noisy_detects_severe_anomaly(self):
        # "严重异常" 标记也应计数
        n = count_big_anomalies('【X】❗️ 严重异常(下跌)')
        self.assertEqual(n, 1)

    def test_wow_below_threshold_ignored(self):
        n = count_big_anomalies('【X】WoW +3.2% 小幅波动')
        self.assertEqual(n, 0)


class TestCountSubstantiveQuestions(unittest.TestCase):
    def test_three_questions_found(self):
        text = (FIXTURES_DIR / 'sample_questions_good.md').read_text(encoding='utf-8')
        n = count_substantive_questions(text)
        self.assertEqual(n, 3)

    def test_no_questions_zero(self):
        self.assertEqual(count_substantive_questions('## 普通段落\n无 Q'), 0)

    def test_gate_report_filters_failed(self):
        gate_report = {
            'questions': [
                {'id': 'Q1', 'passed': True},
                {'id': 'Q2', 'passed': False},
                {'id': 'Q3', 'passed': True},
            ]
        }
        n = count_substantive_questions('Q1\nQ2\nQ3', gate_report)
        self.assertEqual(n, 2)


class TestCli(unittest.TestCase):
    def _run(self, **kwargs):
        cmd = ['python3', str(SCRIPTS_DIR / 'skip_check.py')]
        for k, v in kwargs.items():
            cmd.append(f'--{k.replace("_", "-")}')
            cmd.append(str(v))
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_skip_when_all_conditions_met(self):
        r = self._run(
            grading_json=FIXTURES_DIR / 'sample_grading_all_achieved.json',
            anomaly_txt=FIXTURES_DIR / 'sample_anomaly_quiet.txt',
            user_questions_count=0,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('SKIP', r.stdout)

    def test_full_when_missed_prediction(self):
        r = self._run(
            grading_json=FIXTURES_DIR / 'sample_grading_with_miss.json',
            anomaly_txt=FIXTURES_DIR / 'sample_anomaly_quiet.txt',
            user_questions_count=0,
        )
        self.assertEqual(r.returncode, 1)
        self.assertIn('FULL', r.stdout)

    def test_full_when_big_anomaly(self):
        r = self._run(
            grading_json=FIXTURES_DIR / 'sample_grading_all_achieved.json',
            anomaly_txt=FIXTURES_DIR / 'sample_anomaly_noisy.txt',
            user_questions_count=0,
        )
        self.assertEqual(r.returncode, 1)

    def test_full_when_user_questions(self):
        r = self._run(
            grading_json=FIXTURES_DIR / 'sample_grading_all_achieved.json',
            anomaly_txt=FIXTURES_DIR / 'sample_anomaly_quiet.txt',
            user_questions_count=2,
        )
        self.assertEqual(r.returncode, 1)

    def test_full_when_substantive_questions(self):
        r = self._run(
            grading_json=FIXTURES_DIR / 'sample_grading_all_achieved.json',
            anomaly_txt=FIXTURES_DIR / 'sample_anomaly_quiet.txt',
            user_questions_count=0,
            questions_md=FIXTURES_DIR / 'sample_questions_good.md',
        )
        self.assertEqual(r.returncode, 1)

    def test_output_file_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'decision.json'
            self._run(
                grading_json=FIXTURES_DIR / 'sample_grading_all_achieved.json',
                anomaly_txt=FIXTURES_DIR / 'sample_anomaly_quiet.txt',
                user_questions_count=0,
                output=out,
            )
            self.assertTrue(out.exists())
            data = json.loads(out.read_text(encoding='utf-8'))
            self.assertEqual(data['mode'], 'skip')


if __name__ == '__main__':
    unittest.main()

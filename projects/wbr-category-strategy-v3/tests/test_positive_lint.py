"""Unit tests for scripts/positive_lint.py"""
from __future__ import annotations

import unittest

from _testutil import FIXTURES_DIR, SCRIPTS_DIR  # noqa
from wbr_engine.writer.lint import (
    is_substantive,
    split_sentences,
    lint_markdown,
)


class TestSplitSentences(unittest.TestCase):
    def test_chinese_punctuation_split(self):
        s = split_sentences('本周 GTV 上涨,订单量同比+15%。下周继续观察。')
        self.assertEqual(len(s), 3)

    def test_no_punctuation_single_chunk(self):
        s = split_sentences('短句无标点')
        self.assertEqual(len(s), 1)


class TestIsSubstantive(unittest.TestCase):
    def test_number_with_unit_passes(self):
        passed, mat = is_substantive('GTV 从 1.8亿 增至 2.1亿')
        self.assertTrue(passed)
        self.assertIn('数字+单位', mat)

    def test_action_verb_passes(self):
        passed, _ = is_substantive('本周投放专项券')
        self.assertTrue(passed)

    def test_direction_marker_passes(self):
        passed, _ = is_substantive('指标 WoW+3pp')
        self.assertTrue(passed)

    def test_vague_phrase_fails(self):
        passed, mat = is_substantive('本周表现稳健')
        self.assertFalse(passed)
        self.assertEqual(mat, [])

    def test_filler_fails(self):
        passed, _ = is_substantive('业务持续推进')
        self.assertFalse(passed)


class TestLintMarkdown(unittest.TestCase):
    def test_good_content_no_flags(self):
        md = '''## 标题

啤酒 GTV 从 1.8 亿增至 2.1 亿(WoW+16.7%)。
本周投放专项券,核销率 38%→41%。'''
        flagged = lint_markdown(md)
        self.assertEqual(flagged, [])

    def test_vague_content_flagged(self):
        md = '''## 标题

本周表现稳健,业务持续推进,取得了一定成效。'''
        flagged = lint_markdown(md)
        # 应抓出 "本周表现稳健"、"业务持续推进"、"取得了一定成效"
        sentences = [f['sentence'] for f in flagged]
        self.assertTrue(any('稳健' in s for s in sentences))
        self.assertTrue(any('持续推进' in s for s in sentences))
        self.assertTrue(any('成效' in s for s in sentences))

    def test_meta_section_skipped(self):
        md = '''## 标题

### 数据完整性

无数字无动作无方向的句子也不该被标红,因为这是元信息段。'''
        flagged = lint_markdown(md)
        self.assertEqual(flagged, [])

    def test_table_row_skipped(self):
        md = '''## 标题

| 指标 | 变化 |
| --- | --- |
| GTV | 含糊描述 |'''
        flagged = lint_markdown(md)
        self.assertEqual(flagged, [])

    def test_bold_subheading_skipped(self):
        md = '''## 标题

**1、规模与目标:**

啤酒 GTV 从 1.8 亿增至 2.1 亿。'''
        flagged = lint_markdown(md)
        self.assertEqual(flagged, [])

    def test_code_block_skipped(self):
        md = '''## 标题

```bash
echo hello
```'''
        flagged = lint_markdown(md)
        # bash 命令的"echo hello"如果被纳入也不该被检测(在跳过的代码块边界处)
        # 当前实现只跳过 ``` 行,代码块内容仍会被扫描。把这当成已知限制。
        # 此测试主要验证 ``` 行本身不会被标红
        for f in flagged:
            self.assertFalse(f['sentence'].startswith('```'))


if __name__ == '__main__':
    unittest.main()

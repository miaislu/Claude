#!/usr/bin/env python3
"""
中国法律 AI Agent — Word 报告生成器
将 Markdown 格式的审查报告转换为格式化的 Word 文档

依赖：pip3 install python-docx
用法：python3 generate_docx.py --input report.md --name "项目名称" --output /path/to/reports/
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Cm, Inches


# ── 颜色定义 ──────────────────────────────────────────────────────────────
COLOR_RED    = RGBColor(0xE6, 0x39, 0x46)   # 🔴 高危
COLOR_ORANGE = RGBColor(0xE7, 0x6F, 0x51)   # 🟠 明显缺陷
COLOR_YELLOW = RGBColor(0xF4, 0xA2, 0x61)   # 🟡 中等风险
COLOR_GREEN  = RGBColor(0x2D, 0x6A, 0x4F)   # 🟢 低风险
COLOR_BLUE   = RGBColor(0x1A, 0x1A, 0x2E)   # 深蓝（标题）
COLOR_GRAY   = RGBColor(0x6C, 0x75, 0x7D)   # 灰色（注释）
COLOR_ACCENT = RGBColor(0x0D, 0x6E, 0xFD)   # 蓝色强调


def set_font(run, name="宋体", size=11, bold=False, italic=False, color=None):
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if color:
        run.font.color.rgb = color
    # 确保中文字体正确设置
    rPr = run._r.get_or_add_rPr()
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:eastAsia'), name)
    rFonts.set(qn('w:ascii'), 'Arial')
    rFonts.set(qn('w:hAnsi'), 'Arial')
    rPr.insert(0, rFonts)


def set_para_spacing(para, before=0, after=4, line_spacing=None):
    pPr = para._p.get_or_add_pPr()
    pSpacing = OxmlElement('w:spacing')
    pSpacing.set(qn('w:before'), str(before * 20))
    pSpacing.set(qn('w:after'), str(after * 20))
    if line_spacing:
        pSpacing.set(qn('w:line'), str(int(line_spacing * 240)))
        pSpacing.set(qn('w:lineRule'), 'auto')
    pPr.append(pSpacing)


def set_cell_background(cell, hex_color: str):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color)
    tcPr.append(shd)


def add_border(table):
    """给表格添加边框"""
    tbl = table._tbl
    tblPr = tbl.tblPr
    if tblPr is None:
        tblPr = OxmlElement('w:tblPr')
        tbl.insert(0, tblPr)
    tblBorders = OxmlElement('w:tblBorders')
    for border_name in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
        border = OxmlElement(f'w:{border_name}')
        border.set(qn('w:val'), 'single')
        border.set(qn('w:sz'), '4')
        border.set(qn('w:space'), '0')
        border.set(qn('w:color'), 'D0D0D0')
        tblBorders.append(border)
    tblPr.append(tblBorders)


def score_color_hex(score: int) -> str:
    if score >= 85: return "2D6A4F"
    if score >= 65: return "F4A261"
    if score >= 40: return "E76F51"
    return "E63946"


# ── 核心解析与渲染 ──────────────────────────────────────────────────────
class MarkdownToDocx:
    def __init__(self, doc: Document):
        self.doc = doc
        self.in_table = False
        self.table_rows = []
        self.in_code_block = False
        self.code_lines = []
        self.in_blockquote = False
        self.blockquote_lines = []

    def _flush_table(self):
        if not self.table_rows:
            return
        # 过滤掉分隔行 (---|---)
        rows = [r for r in self.table_rows if not re.match(r'^[\s|:\-]+$', r.replace('|', '').strip())]
        if len(rows) < 1:
            self.table_rows = []
            return

        # 解析表头和数据行
        all_rows = []
        for row in rows:
            cells = [c.strip() for c in row.strip().strip('|').split('|')]
            all_rows.append(cells)

        if not all_rows:
            self.table_rows = []
            return

        num_cols = max(len(r) for r in all_rows)
        table = self.doc.add_table(rows=len(all_rows), cols=num_cols)
        table.style = 'Table Grid'
        add_border(table)

        for i, row_data in enumerate(all_rows):
            for j, cell_text in enumerate(row_data):
                if j >= num_cols:
                    break
                cell = table.cell(i, j)
                # 清理 emoji 风险标记，保留文字
                clean = re.sub(r'[🔴🟡🟢⚪⚡🏢⚖️✅❌⚠️]', '', cell_text).strip()
                # 检测原始文字中的风险等级
                is_high   = '🔴' in cell_text or '高危' in cell_text
                is_medium = '🟡' in cell_text or '中等' in cell_text
                is_low    = '🟢' in cell_text or '低风险' in cell_text

                p = cell.paragraphs[0]
                run = p.add_run(clean)
                font_color = None
                if is_high:   font_color = COLOR_RED
                elif is_medium: font_color = COLOR_YELLOW
                elif is_low:  font_color = COLOR_GREEN
                set_font(run, size=9, bold=(i == 0), color=font_color)
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT

                if i == 0:
                    set_cell_background(cell, "1A1A2E")
                    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                elif i % 2 == 0:
                    set_cell_background(cell, "F8F9FA")

        self.table_rows = []
        self.doc.add_paragraph()  # 表格后空行

    def _flush_code_block(self):
        if not self.code_lines:
            return
        para = self.doc.add_paragraph()
        set_para_spacing(para, before=2, after=2)
        pPr = para._p.get_or_add_pPr()
        ind = OxmlElement('w:ind')
        ind.set(qn('w:left'), '360')
        pPr.append(ind)
        # 浅灰背景
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), 'F0F0F0')
        pPr.append(shd)

        for line in self.code_lines:
            run = para.add_run(line + '\n')
            run.font.name = 'Courier New'
            run.font.size = Pt(9)
            run.font.color.rgb = COLOR_BLUE
        self.code_lines = []

    def _flush_blockquote(self):
        if not self.blockquote_lines:
            return
        para = self.doc.add_paragraph()
        set_para_spacing(para, before=2, after=2)
        pPr = para._p.get_or_add_pPr()
        ind = OxmlElement('w:ind')
        ind.set(qn('w:left'), '480')
        pPr.append(ind)
        # 左边蓝色竖线
        pBdr = OxmlElement('w:pBdr')
        left = OxmlElement('w:left')
        left.set(qn('w:val'), 'single')
        left.set(qn('w:sz'), '12')
        left.set(qn('w:space'), '4')
        left.set(qn('w:color'), '0D6EFD')
        pBdr.append(left)
        pPr.append(pBdr)

        text = ' '.join(self.blockquote_lines)
        run = para.add_run(text)
        set_font(run, size=10, italic=True, color=COLOR_GRAY)
        self.blockquote_lines = []

    def _apply_inline(self, para, text: str):
        """处理行内格式：**bold**、`code`、⚡🔴🟡🟢 等"""
        # 先去掉纯 emoji 行（如 🔴🟡🟢⚪ 开头的标记）
        parts = re.split(r'(\*\*[^*]+\*\*|`[^`]+`)', text)
        for part in parts:
            if part.startswith('**') and part.endswith('**'):
                run = para.add_run(part[2:-2])
                set_font(run, bold=True)
            elif part.startswith('`') and part.endswith('`'):
                run = para.add_run(part[1:-1])
                run.font.name = 'Courier New'
                run.font.size = Pt(9.5)
                run.font.color.rgb = COLOR_ACCENT
            else:
                if part.strip():
                    run = para.add_run(part)
                    set_font(run)

    def process_line(self, line: str):
        stripped = line.rstrip()

        # 代码块
        if stripped.startswith('```'):
            if self.in_code_block:
                self._flush_code_block()
                self.in_code_block = False
            else:
                self.in_code_block = True
            return
        if self.in_code_block:
            self.code_lines.append(stripped)
            return

        # 表格
        if '|' in stripped and stripped.strip().startswith('|'):
            self._flush_blockquote()
            self.table_rows.append(stripped)
            self.in_table = True
            return
        else:
            if self.in_table:
                self._flush_table()
                self.in_table = False

        # 引用
        if stripped.startswith('>'):
            content = re.sub(r'^>\s*', '', stripped)
            if content:
                self.blockquote_lines.append(content)
            return
        else:
            if self.blockquote_lines:
                self._flush_blockquote()

        # 空行
        if not stripped:
            if self.blockquote_lines:
                self._flush_blockquote()
            return

        # 水平分隔线
        if re.match(r'^[-─*]{3,}$', stripped):
            para = self.doc.add_paragraph()
            pPr = para._p.get_or_add_pPr()
            pBdr = OxmlElement('w:pBdr')
            bottom = OxmlElement('w:bottom')
            bottom.set(qn('w:val'), 'single')
            bottom.set(qn('w:sz'), '6')
            bottom.set(qn('w:space'), '1')
            bottom.set(qn('w:color'), 'E0E0E0')
            pBdr.append(bottom)
            pPr.append(pBdr)
            return

        # 标题
        if stripped.startswith('### '):
            para = self.doc.add_paragraph()
            set_para_spacing(para, before=10, after=4)
            run = para.add_run(stripped[4:].strip())
            set_font(run, size=12, bold=True, color=COLOR_BLUE)
            return
        if stripped.startswith('## '):
            para = self.doc.add_paragraph()
            set_para_spacing(para, before=14, after=6)
            run = para.add_run(stripped[3:].strip())
            set_font(run, size=14, bold=True, color=COLOR_BLUE)
            return
        if stripped.startswith('# '):
            para = self.doc.add_paragraph()
            set_para_spacing(para, before=18, after=8)
            run = para.add_run(stripped[2:].strip())
            set_font(run, size=18, bold=True, color=COLOR_BLUE)
            return

        # 四级标题（#### 商业条款 / 律师修改分组）
        if stripped.startswith('#### '):
            para = self.doc.add_paragraph()
            set_para_spacing(para, before=10, after=4)
            text = stripped[5:].strip()
            run = para.add_run(text)
            is_business = '🏢' in text or '商业条款' in text
            is_legal    = '⚖️' in text or '律师修改' in text
            color = RGBColor(0x0D, 0x6E, 0xFD) if is_business else \
                    RGBColor(0x1E, 0x88, 0x55) if is_legal else COLOR_BLUE
            set_font(run, size=11, bold=True, color=color)
            return

        # 列表
        if re.match(r'^[-*]\s', stripped):
            para = self.doc.add_paragraph()
            set_para_spacing(para, before=0, after=2)
            pPr = para._p.get_or_add_pPr()
            ind = OxmlElement('w:ind')
            ind.set(qn('w:left'), '360')
            ind.set(qn('w:hanging'), '180')
            pPr.append(ind)
            run = para.add_run('• ')
            set_font(run, bold=True, color=COLOR_BLUE)
            self._apply_inline(para, stripped[2:].strip())
            return

        if re.match(r'^\d+\.\s', stripped):
            para = self.doc.add_paragraph()
            set_para_spacing(para, before=0, after=2)
            pPr = para._p.get_or_add_pPr()
            ind = OxmlElement('w:ind')
            ind.set(qn('w:left'), '360')
            ind.set(qn('w:hanging'), '180')
            pPr.append(ind)
            m = re.match(r'^(\d+\.\s)', stripped)
            run = para.add_run(m.group(1))
            set_font(run, bold=True, color=COLOR_BLUE)
            self._apply_inline(para, stripped[m.end():].strip())
            return

        # 普通段落
        para = self.doc.add_paragraph()
        set_para_spacing(para, before=0, after=4, line_spacing=1.3)
        self._apply_inline(para, stripped)

    def flush_all(self):
        if self.in_code_block:
            self._flush_code_block()
        if self.table_rows:
            self._flush_table()
        if self.blockquote_lines:
            self._flush_blockquote()


# ── 文档构建 ──────────────────────────────────────────────────────────────
def build_docx(markdown_text: str, project_name: str, output_path: str):
    doc = Document()

    # 页面设置：A4
    section = doc.sections[0]
    section.page_width  = Cm(21.0)
    section.page_height = Cm(29.7)
    section.left_margin = section.right_margin = Cm(2.5)
    section.top_margin  = section.bottom_margin = Cm(2.5)

    # ── 封面 ──────────────────────────────────────────────────────────────
    cover_title = doc.add_paragraph()
    cover_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_para_spacing(cover_title, before=60, after=12)
    run = cover_title.add_run('法律合同审查报告')
    set_font(run, size=24, bold=True, color=COLOR_BLUE)

    cover_sub = doc.add_paragraph()
    cover_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_para_spacing(cover_sub, before=0, after=40)
    run = cover_sub.add_run(project_name)
    set_font(run, size=14, color=COLOR_GRAY)

    # 提取评分
    score_match = re.search(r'合同安全评分[：:]\s*[🔴🟡🟢🟠]?\s*\*{0,2}(\d+)\s*/\s*100', markdown_text)
    if score_match:
        score = int(score_match.group(1))
        score_para = doc.add_paragraph()
        score_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_para_spacing(score_para, before=0, after=8)
        run = score_para.add_run(str(score))
        run.font.size = Pt(60)
        run.font.bold = True
        run.font.color.rgb = RGBColor(
            *bytes.fromhex(score_color_hex(score))
        )
        label_para = doc.add_paragraph()
        label_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = label_para.add_run('合同安全评分 / 100')
        set_font(run, size=11, color=COLOR_GRAY)

    # 生成日期
    date_para = doc.add_paragraph()
    date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_para_spacing(date_para, before=20, after=0)
    run = date_para.add_run(f'生成日期：{datetime.now().strftime("%Y年%m月%d日 %H:%M")}')
    set_font(run, size=10, color=COLOR_GRAY)

    # 免责声明横幅
    disclaimer_para = doc.add_paragraph()
    disclaimer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_para_spacing(disclaimer_para, before=16, after=0)
    run = disclaimer_para.add_run('⚠️  本报告由 AI 辅助生成，仅供参考，不构成正式法律意见')
    set_font(run, size=9, italic=True, color=COLOR_GRAY)

    doc.add_page_break()

    # ── 正文 ──────────────────────────────────────────────────────────────
    parser = MarkdownToDocx(doc)
    for line in markdown_text.split('\n'):
        parser.process_line(line)
    parser.flush_all()

    # ── 页脚 ──────────────────────────────────────────────────────────────
    footer = doc.sections[0].footer
    footer_para = footer.paragraphs[0]
    footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer_para.add_run('中国法律 AI Agent  |  本报告由 AI 辅助生成，不构成正式法律意见')
    set_font(run, size=8, color=COLOR_GRAY)

    doc.save(output_path)
    print(f'✅ 报告已保存：{output_path}')


# ── CLI ──────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='将 Markdown 审查报告转换为 Word 文档')
    parser.add_argument('--input',  required=True, help='Markdown 报告文件路径')
    parser.add_argument('--name',   required=True, help='项目名称（用于文件命名）')
    parser.add_argument('--output', required=True, help='输出目录路径')
    parser.add_argument('--score',  type=int, default=None, help='合同安全评分（可选，自动从文本提取）')
    args = parser.parse_args()

    with open(args.input, 'r', encoding='utf-8') as f:
        md_text = f.read()

    os.makedirs(args.output, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    # 清理项目名称中的特殊字符
    safe_name = re.sub(r'[\\/:*?"<>|]', '_', args.name)
    filename = f'{safe_name}_审查报告_{timestamp}.docx'
    output_path = os.path.join(args.output, filename)

    build_docx(md_text, args.name, output_path)


if __name__ == '__main__':
    main()

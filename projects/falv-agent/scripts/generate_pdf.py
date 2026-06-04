#!/usr/bin/env python3
"""
中国法律 AI Agent — PDF 报告生成器
依赖：pip3 install reportlab
"""

import argparse
import json
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── 字体注册（macOS 系统中文字体）──────────────────────────────────────────
FONT_PATHS = {
    "normal": [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ],
    "bold": [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
    ],
}

def register_fonts():
    """注册中文字体，优先使用系统自带字体。"""
    registered = False
    for path in FONT_PATHS["normal"]:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("CN", path))
                registered = True
                break
            except Exception:
                continue

    if not registered:
        print("⚠️  未找到中文字体，PDF 中文字符可能显示异常。")
        print("    建议运行：pip3 install reportlab 并确保系统安装了 PingFang 字体。")

    for path in FONT_PATHS["bold"]:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("CN-Bold", path))
                break
            except Exception:
                continue


# ── 样式定义 ──────────────────────────────────────────────────────────────
def build_styles():
    styles = getSampleStyleSheet()
    base_font = "CN" if "CN" in pdfmetrics.getRegisteredFontNames() else "Helvetica"
    bold_font = "CN-Bold" if "CN-Bold" in pdfmetrics.getRegisteredFontNames() else "Helvetica-Bold"

    custom = {
        "Title": ParagraphStyle("Title", fontName=bold_font, fontSize=22, textColor=colors.HexColor("#1a1a2e"), alignment=TA_CENTER, spaceAfter=6),
        "Subtitle": ParagraphStyle("Subtitle", fontName=base_font, fontSize=12, textColor=colors.HexColor("#4a4a6a"), alignment=TA_CENTER, spaceAfter=4),
        "Score": ParagraphStyle("Score", fontName=bold_font, fontSize=48, textColor=colors.HexColor("#e63946"), alignment=TA_CENTER),
        "ScoreLabel": ParagraphStyle("ScoreLabel", fontName=base_font, fontSize=11, textColor=colors.grey, alignment=TA_CENTER, spaceAfter=12),
        "H1": ParagraphStyle("H1", fontName=bold_font, fontSize=15, textColor=colors.HexColor("#1a1a2e"), spaceBefore=12, spaceAfter=6, borderPad=4),
        "H2": ParagraphStyle("H2", fontName=bold_font, fontSize=12, textColor=colors.HexColor("#2d6a4f"), spaceBefore=8, spaceAfter=4),
        "Body": ParagraphStyle("Body", fontName=base_font, fontSize=10, textColor=colors.HexColor("#333333"), leading=16, spaceAfter=4),
        "Disclaimer": ParagraphStyle("Disclaimer", fontName=base_font, fontSize=8, textColor=colors.grey, alignment=TA_CENTER, spaceBefore=20),
        "TableHeader": ParagraphStyle("TableHeader", fontName=bold_font, fontSize=9, textColor=colors.white, alignment=TA_CENTER),
        "TableCell": ParagraphStyle("TableCell", fontName=base_font, fontSize=9, textColor=colors.HexColor("#333333"), leading=13),
    }
    return custom


# ── 评分颜色 ──────────────────────────────────────────────────────────────
def score_color(score: int) -> colors.Color:
    if score >= 85:
        return colors.HexColor("#2d6a4f")   # 绿
    elif score >= 65:
        return colors.HexColor("#f4a261")   # 橙黄
    elif score >= 40:
        return colors.HexColor("#e76f51")   # 橙红
    else:
        return colors.HexColor("#e63946")   # 红


def risk_color(level: str) -> colors.Color:
    mapping = {
        "高危": colors.HexColor("#e63946"),
        "中等": colors.HexColor("#f4a261"),
        "低风险": colors.HexColor("#2d6a4f"),
        "无风险": colors.HexColor("#adb5bd"),
    }
    return mapping.get(level, colors.grey)


# ── 报告生成 ──────────────────────────────────────────────────────────────
def generate_report(data: dict, output_path: str, watermark: str = None, logo_path: str = None, include_suggestions: bool = False):
    register_fonts()
    styles = build_styles()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=25 * mm,
        bottomMargin=25 * mm,
        title=data.get("contract_name", "法律审查报告"),
        author="中国法律 AI Agent",
    )

    story = []
    score = data.get("overall_score", 0)

    # ── 封面 ──────────────────────────────────────────────────────────────
    if logo_path and os.path.exists(logo_path):
        story.append(Image(logo_path, width=40 * mm, height=15 * mm))
        story.append(Spacer(1, 8 * mm))

    story.append(Spacer(1, 20 * mm))
    story.append(Paragraph("法律审查报告", styles["Title"]))
    story.append(Paragraph(data.get("contract_name", "合同文件"), styles["Subtitle"]))
    story.append(Spacer(1, 10 * mm))

    # 评分大字显示
    color = score_color(score)
    story.append(Paragraph(f'<font color="{color.hexval()}">{score}</font>', styles["Score"]))
    story.append(Paragraph("合同安全评分 / 100", styles["ScoreLabel"]))
    story.append(HRFlowable(width="80%", thickness=1, color=colors.HexColor("#e0e0e0")))
    story.append(Spacer(1, 6 * mm))

    # 基本信息表
    info = data.get("basic_info", {})
    info_rows = [
        ["审查日期", datetime.now().strftime("%Y年%m月%d日")],
        ["合同类型", info.get("contract_type", "—")],
        ["甲方", info.get("party_a", "—")],
        ["乙方", info.get("party_b", "—")],
        ["合同金额", info.get("amount", "—")],
        ["有效期", info.get("duration", "—")],
    ]
    info_table = Table(info_rows, colWidths=[35 * mm, 100 * mm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "CN" if "CN" in pdfmetrics.getRegisteredFontNames() else "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#4a4a6a")),
        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
        ("ALIGN", (1, 0), (1, -1), "LEFT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(info_table)

    if watermark:
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph(
            f'<font color="#cccccc" size="28"><b>{watermark}</b></font>',
            ParagraphStyle("WM", alignment=TA_CENTER)
        ))

    story.append(PageBreak())

    # ── 执行摘要 ──────────────────────────────────────────────────────────
    story.append(Paragraph("执行摘要", styles["H1"]))
    summary = data.get("summary", {})
    summary_rows = [
        ["🔴 高危条款", str(summary.get("high_risk_count", 0)) + " 条"],
        ["🟡 中等风险", str(summary.get("medium_risk_count", 0)) + " 条"],
        ["🟢 低风险", str(summary.get("low_risk_count", 0)) + " 条"],
        ["❌ 合规缺失项", str(summary.get("compliance_failed", 0)) + " 项"],
        ["📝 修改建议", str(summary.get("recommendations_count", 0)) + " 条"],
    ]
    summary_table = Table(summary_rows, colWidths=[50 * mm, 30 * mm])
    summary_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "CN" if "CN" in pdfmetrics.getRegisteredFontNames() else "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f8f9fa"), colors.white]),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 8 * mm))

    # ── 风险条款详情 ──────────────────────────────────────────────────────
    risks = data.get("risk_assessment", [])
    if risks:
        story.append(Paragraph("风险条款详情", styles["H1"]))
        risk_data = [
            [
                Paragraph("条款位置", styles["TableHeader"]),
                Paragraph("风险等级", styles["TableHeader"]),
                Paragraph("风险描述", styles["TableHeader"]),
                Paragraph("法律依据", styles["TableHeader"]),
            ]
        ]
        for r in risks:
            level = r.get("risk_level", "—")
            risk_data.append([
                Paragraph(r.get("location", "—"), styles["TableCell"]),
                Paragraph(level, ParagraphStyle("RiskLevel", fontName="CN" if "CN" in pdfmetrics.getRegisteredFontNames() else "Helvetica", fontSize=9, textColor=risk_color(level), alignment=TA_CENTER)),
                Paragraph(r.get("risk_description", "—"), styles["TableCell"]),
                Paragraph(r.get("legal_basis", "—"), styles["TableCell"]),
            ])
        risk_table = Table(risk_data, colWidths=[25 * mm, 20 * mm, 80 * mm, 45 * mm])
        risk_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e0e0")),
            ("FONTNAME", (0, 0), (-1, -1), "CN" if "CN" in pdfmetrics.getRegisteredFontNames() else "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8f9fa"), colors.white]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(risk_table)
        story.append(Spacer(1, 8 * mm))

    # ── 合规检查结果 ──────────────────────────────────────────────────────
    compliance = data.get("compliance_check", {})
    if compliance:
        story.append(PageBreak())
        story.append(Paragraph("合规检查结果", styles["H1"]))

        failed = compliance.get("failed", [])
        if failed:
            story.append(Paragraph("❌ 不合规项（需整改）", styles["H2"]))
            for item in failed:
                story.append(Paragraph(
                    f"• <b>{item.get('item', '')}</b>（{item.get('basis', '')}）：{item.get('consequence', '')}",
                    styles["Body"]
                ))
        story.append(Spacer(1, 4 * mm))

        passed = compliance.get("passed", [])
        if passed:
            story.append(Paragraph("✅ 合规确认项", styles["H2"]))
            for item in passed:
                story.append(Paragraph(f"• {item.get('item', '')}（{item.get('basis', '')}）", styles["Body"]))

    # ── 修改建议 ──────────────────────────────────────────────────────────
    if include_suggestions:
        recommendations = data.get("recommendations", [])
        if recommendations:
            story.append(PageBreak())
            story.append(Paragraph("修改建议", styles["H1"]))
            for i, rec in enumerate(recommendations, 1):
                priority = rec.get("priority", "")
                story.append(Paragraph(f"{i}. [{priority}] {rec.get('problem', '')}", styles["H2"]))
                story.append(Paragraph(f"法律依据：{rec.get('legal_basis', '')}", styles["Body"]))
                if rec.get("original_text"):
                    story.append(Paragraph(f"原文：{rec['original_text']}", styles["Body"]))
                if rec.get("suggested_text"):
                    story.append(Paragraph(f"建议修改为：{rec['suggested_text']}", styles["Body"]))
                story.append(Spacer(1, 4 * mm))

    # ── 免责声明 ──────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e0e0e0")))
    story.append(Paragraph(
        "⚠️ 免责声明：本报告由 AI 辅助生成，仅供参考，不构成正式法律意见。"
        "如涉及重大商业决策或法律纠纷，请咨询具有相应执业资质的律师。",
        styles["Disclaimer"]
    ))

    doc.build(story)
    print(f"✅ PDF 报告已生成：{output_path}")


# ── CLI 入口 ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="生成法律审查 PDF 报告")
    parser.add_argument("--data", required=True, help="审查结果 JSON 文件路径")
    parser.add_argument("--output", default=f"法律审查报告_{datetime.now().strftime('%Y%m%d')}.pdf", help="输出 PDF 文件名")
    parser.add_argument("--watermark", default="仅供参考", help="水印文字")
    parser.add_argument("--logo", default=None, help="Logo 图片路径")
    parser.add_argument("--include-suggestions", action="store_true", help="包含修改建议")
    args = parser.parse_args()

    with open(args.data, "r", encoding="utf-8") as f:
        data = json.load(f)

    generate_report(
        data=data,
        output_path=args.output,
        watermark=args.watermark,
        logo_path=args.logo,
        include_suggestions=args.include_suggestions,
    )


if __name__ == "__main__":
    main()

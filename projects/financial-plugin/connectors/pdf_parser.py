"""
从公告 PDF URL 提取 MD&A 章节文本。

不缓存（大文件，按需提取）。
定位策略：找到标题关键词所在页后，提取后续段落直到下一个一级标题。
"""

from __future__ import annotations

import io
import warnings

import requests

warnings.filterwarnings("ignore")

# MD&A 章节标题关键词（按优先级排列）
_MDA_TITLES = [
    "管理层讨论与分析",
    "经营情况讨论与分析",
    "经营情况回顾",
    "董事会报告",
    "管理层分析",
    "业务回顾及展望",
]

# 下一个一级标题关键词（遇到时停止提取）
_STOP_TITLES = [
    "重要事项",
    "股本变动",
    "董事、监事",
    "重大事项",
    "独立审计",
    "财务报告",
    "附注",
    "审计报告",
]

_REQUEST_TIMEOUT = 30  # 秒


def _download_pdf(url: str) -> bytes | None:
    """下载 PDF 文件内容，失败返回 None。"""
    try:
        resp = requests.get(url, timeout=_REQUEST_TIMEOUT, verify=False)
        if resp.status_code == 200:
            return resp.content
        return None
    except Exception:
        return None


def _find_mda_pages(pdf_bytes: bytes) -> list[str]:
    """
    用 pdfplumber 提取 MD&A 章节文本。
    返回提取到的文字段落列表（每页一个字符串）。
    """
    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
    except Exception:
        return []

    # 1. 找到 MD&A 章节起始页
    start_page = -1
    for i, text in enumerate(pages):
        if any(title in text for title in _MDA_TITLES):
            start_page = i
            break

    if start_page == -1:
        return []

    # 2. 从起始页提取，遇到下一个一级标题停止
    extracted = []
    for i in range(start_page, min(start_page + 15, len(pages))):
        text = pages[i]
        if i > start_page and any(stop in text[:200] for stop in _STOP_TITLES):
            break
        extracted.append(text)

    return extracted


def extract_mda_from_pdf(pdf_url: str) -> str | None:
    """
    从公告 PDF URL 提取管理层讨论章节文本。
    返回合并后的文本字符串，失败返回 None。
    """
    if not pdf_url or pdf_url == "nan":
        return None

    pdf_bytes = _download_pdf(pdf_url)
    if pdf_bytes is None:
        return None

    pages = _find_mda_pages(pdf_bytes)
    if not pages:
        return None

    return "\n\n".join(pages).strip()


def extract_section(pdf_url: str, section_title: str) -> str | None:
    """
    通用章节提取：按标题关键词定位，提取后续段落。
    """
    if not pdf_url or pdf_url == "nan":
        return None

    pdf_bytes = _download_pdf(pdf_url)
    if pdf_bytes is None:
        return None

    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
    except Exception:
        return None

    start_page = -1
    for i, text in enumerate(pages):
        if section_title in text:
            start_page = i
            break

    if start_page == -1:
        return None

    extracted = []
    for i in range(start_page, min(start_page + 10, len(pages))):
        text = pages[i]
        if i > start_page and any(stop in text[:200] for stop in _STOP_TITLES):
            break
        extracted.append(text)

    return "\n\n".join(extracted).strip() if extracted else None

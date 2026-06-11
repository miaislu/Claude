"""
Connectors 层：A 股数据接入统一入口。

模块列表：
  cache           — 文件缓存（LOOKBACK_PERIODS 常量）
  fundamental     — 三表 + 财务指标（akshare）
  market          — 行情 / Beta / 北向 / 国债（akshare）
  news            — 公告 / 问询函 / 分析师预期（akshare）
  pdf_parser      — PDF 公告 MD&A 文本提取（pdfplumber）
  industry_data   — 北向资金 / 质押 / 行业指数（akshare）
  policy_monitor  — 政策新闻（akshare + 关键词白名单）
  research_monitor— 研报评级（akshare，注明覆盖局限）
"""

from .cache import LOOKBACK_PERIODS, get_cache

__all__ = ["LOOKBACK_PERIODS", "get_cache"]

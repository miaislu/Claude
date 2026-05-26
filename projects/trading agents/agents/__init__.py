from __future__ import annotations

from typing import Optional
from .schemas import AnalystReport, SUBMIT_ANALYSIS_TOOL


def user_context_block(user_context: Optional[str]) -> str:
    """
    Wrap user-supplied context (research notes, call transcripts, etc.)
    in a clearly labelled block to prepend to any agent query.
    Returns an empty string when no context is provided.
    """
    if not user_context or not user_context.strip():
        return ""
    return (
        "【用户补充信息 — 最高优先级】\n"
        "以下信息由用户直接提供，可能包含调研纪要、电话会议纪要、"
        "渠道反馈或其他第一手资料。分析时请优先参考这些信息，"
        "在与其他数据冲突时以此为准。\n\n"
        f"{user_context.strip()}\n\n"
        "【以下为常规分析任务】\n"
    )


__all__ = ["AnalystReport", "SUBMIT_ANALYSIS_TOOL", "user_context_block"]

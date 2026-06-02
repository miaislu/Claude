from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class AnalystReport(BaseModel):
    agent: str
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float = Field(ge=0.0, le=1.0)
    key_factors: List[str]
    risks: List[str]
    summary: str
    data_snapshot: Dict[str, Any] = Field(default_factory=dict)
    """工具实际返回的原始关键数值（✅事实层），与 key_factors 的分析解读层分开。"""


class DebateArgument(BaseModel):
    position: Literal["bull", "bear"]
    round_num: int
    argument: str
    key_points: List[str]
    counter_points: List[str] = Field(default_factory=list)


class DebateResult(BaseModel):
    ticker: str
    date: str
    bull_arguments: List[DebateArgument]
    bear_arguments: List[DebateArgument]
    final_signal: Literal["bullish", "bearish", "neutral"]
    final_confidence: float = Field(ge=0.0, le=1.0)
    winning_arguments: List[str]
    key_risks: List[str]
    trade_recommendation: str
    rationale: str


class RiskParameters(BaseModel):
    ticker: str
    current_price: Optional[float]
    signal: Literal["bullish", "bearish", "neutral"]
    position_size_pct: float          # % of portfolio to allocate
    stop_loss_price: Optional[float]
    take_profit_price: Optional[float]
    stop_loss_pct: Optional[float]
    take_profit_pct: Optional[float]
    risk_reward_ratio: Optional[float]
    atr_14: Optional[float]
    position_rationale: str
    warnings: List[str] = Field(default_factory=list)


# ── Shared tool definitions ────────────────────────────────────────────────────

SUBMIT_ANALYSIS_TOOL: Dict[str, Any] = {
    "name": "submit_analysis",
    "description": (
        "Submit the final analysis report. Call this as your last action "
        "after reviewing all available data."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "signal": {
                "type": "string",
                "enum": ["bullish", "bearish", "neutral"],
                "description": "Overall signal for the next 1-4 weeks",
            },
            "confidence": {
                "type": "number",
                "description": "Signal confidence 0.0–1.0 (0.7+ = strong, 0.4–0.7 = moderate)",
            },
            "key_factors": {
                "type": "array",
                "items": {"type": "string"},
                "description": "3–5 key factors supporting the signal (be specific with numbers)",
            },
            "risks": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Key risks or contradicting signals",
            },
            "summary": {
                "type": "string",
                "description": "2–3 sentence analysis summary",
            },
        },
        "required": ["signal", "confidence", "key_factors", "risks", "summary"],
    },
}

SUBMIT_ARGUMENT_TOOL: Dict[str, Any] = {
    "name": "submit_argument",
    "description": "Submit your debate argument for this round.",
    "input_schema": {
        "type": "object",
        "properties": {
            "argument": {
                "type": "string",
                "description": "Your full argument (2–3 paragraphs), grounded in the analyst data",
            },
            "key_points": {
                "type": "array",
                "items": {"type": "string"},
                "description": "3–5 strongest points supporting your position",
            },
            "counter_points": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Points from the opponent's argument you are countering (empty in round 1)",
            },
        },
        "required": ["argument", "key_points"],
    },
}

SUBMIT_RECOMMENDATION_TOOL: Dict[str, Any] = {
    "name": "submit_recommendation",
    "description": "Submit the final arbitrated trade recommendation after reviewing all debate arguments.",
    "input_schema": {
        "type": "object",
        "properties": {
            "signal": {
                "type": "string",
                "enum": ["bullish", "bearish", "neutral"],
            },
            "confidence": {
                "type": "number",
                "description": "0.0–1.0",
            },
            "winning_arguments": {
                "type": "array",
                "items": {"type": "string"},
                "description": "The 3–5 arguments that were most persuasive",
            },
            "key_risks": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Top risks that must be monitored",
            },
            "trade_recommendation": {
                "type": "string",
                "description": "Concrete action: e.g. 'Buy on dip, target entry below $180'",
            },
            "rationale": {
                "type": "string",
                "description": "2–3 sentence explanation of why this side won the debate",
            },
        },
        "required": ["signal", "confidence", "winning_arguments", "key_risks", "trade_recommendation", "rationale"],
    },
}

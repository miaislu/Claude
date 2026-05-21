from __future__ import annotations

from typing import Any, Dict, Literal, List
from pydantic import BaseModel, Field


class AnalystReport(BaseModel):
    agent: str
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float = Field(ge=0.0, le=1.0)
    key_factors: List[str]
    risks: List[str]
    summary: str


# Shared submit_analysis tool — all analyst agents use the same output schema.
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

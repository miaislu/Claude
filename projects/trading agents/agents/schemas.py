from __future__ import annotations

from typing import Literal, List
from pydantic import BaseModel, Field


class AnalystReport(BaseModel):
    agent: str
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float = Field(ge=0.0, le=1.0)
    key_factors: List[str]
    risks: List[str]
    summary: str

"""
Agent 基类：提供 Skills 桥接、LLM 调用、存档加载。

LLM 模式（渐进增强）：
  - 有 ANTHROPIC_API_KEY → _call_llm() 调用 Claude API
  - 无 API Key → 返回 None，调用方 fall back 规则引擎
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

_LLM_MODEL = "claude-sonnet-4-6"


def load_skill(agent_name: str) -> str:
    """按 Agent 类名加载对应的 skills/*.md 文件。"""
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", agent_name).lower()
    path = _ROOT / "skills" / f"{snake}.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


class AgentBase:
    """
    所有金融 Agent 的基类。

    提供：
      self.skill_prompt     — 领域知识 prompt（来自 skills/*.md）
      self._call_llm()      — 调用 Claude API（无 Key 时返回 None）
      self._load_storage()  — 从 storage/ 读取上游存档（含时效元数据）
    """

    # ──────────────────────────────────────────
    # Skills 桥接
    # ──────────────────────────────────────────

    @property
    def skill_name(self) -> str:
        return re.sub(r"(?<!^)(?=[A-Z])", "_", self.__class__.__name__).lower()

    @property
    def skill_prompt(self) -> str:
        return load_skill(self.__class__.__name__)

    # ──────────────────────────────────────────
    # LLM 调用（渐进增强）
    # ──────────────────────────────────────────

    def _call_llm(
        self,
        user_data: dict[str, Any],
        max_tokens: int = 2048,
        model: str = _LLM_MODEL,
    ) -> str | None:
        """
        以 skill_prompt 为 system prompt，调用 Claude API 分析 user_data。

        返回 LLM 文本响应；无 API Key 时返回 None（调用方应 fall back 规则引擎）。

        使用示例：
          result = self._call_llm({
              "task": "thesis_analysis",
              "data": {...},
              "output_format": "[{verdict, evidence, confidence}]"
          })
          if result:
              return parse_llm_output(result)
          else:
              return fallback_rules(...)
        """
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return None
        try:
            import anthropic
            client = anthropic.Anthropic()
            resp = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=self.skill_prompt,
                messages=[{
                    "role": "user",
                    "content": json.dumps(user_data, ensure_ascii=False, default=str),
                }],
            )
            return resp.content[0].text
        except Exception as e:
            import sys
            print(f"[{self.__class__.__name__}] LLM call failed: {e}", file=sys.stderr)
            return None

    # ──────────────────────────────────────────
    # 存档加载（带时效检查）
    # ──────────────────────────────────────────

    @staticmethod
    def _load_storage(
        code: str,
        agent_key: str,
    ) -> tuple[dict | None, int | None]:
        """
        从 storage/ 读取最新存档，返回 (data, age_days)。

        - 文件不存在 → (None, None)
        - 文件存在但过期（> 90 天）→ (data, age_days) 仍返回，由调用方决定是否警告
        - age_days 基于文件名中的时间戳；若无时间戳则基于文件 mtime
        """
        storage = _ROOT / "storage"
        files = sorted(storage.glob(f"{code}_{agent_key}_*.json"), reverse=True)
        if not files:
            import sys
            print(
                f"[AgentBase] 未找到 {code}_{agent_key} 存档，该 Agent 将以无上游数据模式运行",
                file=sys.stderr,
            )
            return None, None

        path = files[0]
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None, None

        # 计算数据年龄
        age_days = _file_age_days(path)
        return data, age_days

    @staticmethod
    def _storage_warning(code: str, agent_key: str, age_days: int | None) -> str | None:
        """
        根据存档状态生成人类可读的警告文本。
        返回 None 表示数据新鲜，无需警告。
        """
        if age_days is None:
            return f"未找到 {agent_key} 数据（{code}），相关字段为空"
        if age_days > 90:
            return f"{agent_key} 数据已 {age_days} 天未更新，建议重新运行"
        return None


# ──────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────

def _file_age_days(path: Path) -> int | None:
    """从文件名时间戳或 mtime 估算数据年龄（天）。"""
    # 尝试从文件名解析：{code}_{agent}_{YYYYMMDD}[_{HHMMSS}].json
    stem = path.stem
    parts = stem.rsplit("_", maxsplit=3)
    for part in reversed(parts):
        if len(part) == 8 and part.isdigit():
            try:
                file_date = datetime.strptime(part, "%Y%m%d").replace(tzinfo=timezone.utc)
                delta = datetime.now(timezone.utc) - file_date
                return delta.days
            except ValueError:
                pass
    # fallback: 文件 mtime
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        return (datetime.now(timezone.utc) - mtime).days
    except Exception:
        return None

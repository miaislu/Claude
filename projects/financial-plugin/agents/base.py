"""
Agent 基类：提供 Skills 文件桥接和通用工具。

skills/*.md 是每个 Agent 的领域知识 prompt 文件。
当前 MVP 实现是纯 rule-based Python；升级为 LLM 驱动时，
通过 self.skill_prompt 将 .md 内容注入 system prompt。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))


def load_skill(agent_name: str) -> str:
    """
    按 Agent 类名加载对应的 skills/*.md 文件。

    EarningsReviewer → skills/earnings_reviewer.md
    ModelBuilder     → skills/model_builder.md
    ...
    """
    # CamelCase → snake_case
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", agent_name).lower()
    path = _ROOT / "skills" / f"{snake}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


class AgentBase:
    """
    所有金融 Agent 的基类。

    提供：
      self.skill_prompt  — 对应 skills/*.md 的内容
      self.skill_name    — snake_case 名称（如 "earnings_reviewer"）
    """

    @property
    def skill_name(self) -> str:
        return re.sub(r"(?<!^)(?=[A-Z])", "_", self.__class__.__name__).lower()

    @property
    def skill_prompt(self) -> str:
        """
        返回该 Agent 对应的领域知识 prompt。

        当前用途：
          - 调试 / 文档：print(agent.skill_prompt)
          - LLM 升级路径：作为 system_prompt 传入 Claude API

        示例（未来 LLM 模式）：
          import anthropic
          client = anthropic.Anthropic()
          response = client.messages.create(
              model="claude-opus-4-8",
              system=self.skill_prompt,
              messages=[{"role": "user", "content": data_json}],
          )
        """
        return load_skill(self.__class__.__name__)

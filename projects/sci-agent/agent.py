"""
科研 Agent 核心 harness。

设计原则（对应 12-Factor Agents）:
- Factor 1: 自然语言 → 工具调用，由 Claude 理解意图，代码负责执行
- Factor 3: 主动管理上下文，注入 SKILL.md 作为工具使用指南
- Factor 8: 自己掌控控制流，不依赖框架的隐式循环
- Factor 12: Agent 是无状态 Reducer：(messages, action) → next_state
"""

import json
import os
from pathlib import Path
from typing import Any

import anthropic
from dotenv import load_dotenv
from tools import pubmed_search, fetch_abstract

load_dotenv()

client = anthropic.Anthropic()

# ── 工具定义（Claude 看到的 schema）──────────────────────────────────────────

TOOLS: list[dict[str, Any]] = [
    {
        "name": "pubmed_search",
        "description": (
            "搜索 PubMed 生物医学文献数据库。返回匹配的论文 ID 列表。"
            "适合用于：查找特定主题的研究论文、了解某领域的研究现状。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索词，支持 MeSH 术语和布尔运算符，如 'CRISPR cancer therapy'",
                },
                "max_results": {
                    "type": "integer",
                    "description": "返回结果数，默认 10，最大 100",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_abstract",
        "description": "根据 PubMed ID (PMID) 获取论文的摘要、作者、期刊和发表年份。",
        "input_schema": {
            "type": "object",
            "properties": {
                "pmid": {
                    "type": "string",
                    "description": "PubMed ID，如 '38900000'",
                },
            },
            "required": ["pmid"],
        },
    },
]

# ── 工具执行（Factor 1：代码负责执行，Claude 只负责决策）────────────────────

TOOL_REGISTRY = {
    "pubmed_search": pubmed_search,
    "fetch_abstract": fetch_abstract,
}


def execute_tool(name: str, tool_input: dict[str, Any]) -> str:
    """执行工具调用，返回 JSON 字符串结果。"""
    if name not in TOOL_REGISTRY:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        result = TOOL_REGISTRY[name](**tool_input)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── 上下文构建（Factor 3：主动管理注入哪些内容）─────────────────────────────

def load_skills(skills_dir: str = "skills") -> str:
    """加载 skills/ 目录下所有 SKILL.md 的描述字段，注入系统提示。"""
    skills_path = Path(skills_dir)
    if not skills_path.exists():
        return ""

    descriptions = []
    for skill_file in sorted(skills_path.glob("*/SKILL.md")):
        content = skill_file.read_text(encoding="utf-8")
        # 只取 frontmatter 的 description 行，保持上下文精简
        for line in content.splitlines():
            if line.startswith("description:"):
                desc = line.replace("description:", "").strip()
                descriptions.append(f"- {desc}")
                break

    if not descriptions:
        return ""
    return "\n\nAvailable Skills:\n" + "\n".join(descriptions)


def build_system_prompt() -> str:
    """构建系统提示。稳定内容放前面，便于 prompt caching。"""
    base = (
        "你是一位科研 AI 助手，擅长检索文献、分析数据和撰写科学报告。\n"
        "在回答问题前，优先使用可用工具获取最新、准确的信息。\n"
        "引用文献时请注明 PMID 和标题。"
    )
    skills_context = load_skills()
    return base + skills_context


# ── 核心 Agent 循环（Factor 8：自己控制流，Factor 12：无状态 Reducer）───────

def run_agent(user_query: str, max_iterations: int = 10) -> str:
    """
    运行科研 Agent 对话循环。

    设计为无状态 Reducer 模式：
        (messages, llm_response) → 追加 action → 新的 messages
    每次迭代都是纯粹的状态转换，易于测试和调试。
    """
    system_prompt = build_system_prompt()
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": user_query}
    ]

    for iteration in range(max_iterations):
        # ── 调用 Claude API ────────────────────────────────────────────────
        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=4096,
            thinking={"type": "adaptive"},        # 复杂科研问题需要推理
            output_config={"effort": "high"},
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        # ── 提取本轮的文本输出（用于实时显示）──────────────────────────────
        for block in response.content:
            if block.type == "text" and block.text.strip():
                print(f"\n[Claude]: {block.text}")

        # ── 检查是否完成（无状态 Reducer 的终止条件）────────────────────────
        if response.stop_reason == "end_turn":
            final_text = next(
                (b.text for b in response.content if b.type == "text"), ""
            )
            return final_text

        if response.stop_reason != "tool_use":
            # 其他 stop reason（max_tokens、refusal 等）
            return f"[停止原因: {response.stop_reason}]"

        # ── 执行工具调用（Factor 1：代码负责执行）───────────────────────────
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        tool_results = []

        for tool_block in tool_use_blocks:
            print(f"\n[工具调用]: {tool_block.name}({json.dumps(tool_block.input, ensure_ascii=False)})")
            result_text = execute_tool(tool_block.name, tool_block.input)
            print(f"[工具结果]: {result_text[:200]}{'...' if len(result_text) > 200 else ''}")

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_block.id,
                "content": result_text,
            })

        # ── 状态转换：追加本轮 assistant 响应和工具结果（Reducer 模式）────────
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    return "[达到最大迭代次数，任务未完成]"


# ── 交互式入口 ────────────────────────────────────────────────────────────────

def main():
    print("科研 Agent 已启动（输入 'quit' 退出）\n")
    print("示例问题：")
    print("  - 搜索最近关于 AlphaFold 蛋白质结构预测的论文")
    print("  - 查找 2024 年 CAR-T 细胞治疗的最新进展")
    print("  - 找 3 篇关于单细胞 RNA 测序方法的综述\n")

    while True:
        user_input = input("你: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("再见！")
            break

        print("\n" + "─" * 50)
        result = run_agent(user_input)
        print("\n" + "─" * 50)
        print(f"\n[最终答案]:\n{result}\n")


if __name__ == "__main__":
    main()

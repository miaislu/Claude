# 科研 Agent 骨架

基于 Anthropic SDK 原生 tool use 的最小可用科研 Agent，对应 12-Factor Agents 的核心原则。

## 快速开始

```bash
# 安装依赖（需要 Python 3.12+）
pip install -e .

# 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 ANTHROPIC_API_KEY

# 运行
python agent.py
```

## 项目结构

```
sci-agent/
├── agent.py          # 核心 harness：控制流 + 上下文管理 + Agent 循环
├── tools/
│   ├── __init__.py
│   └── pubmed.py     # PubMed 文献检索（无需 API Key）
├── skills/
│   └── pubmed_search/
│       └── SKILL.md  # 工具使用指南（注入系统提示）
└── pyproject.toml
```

## 扩展工具

在 `tools/` 下新增一个 Python 文件，实现工具函数，然后在 `agent.py` 中：

1. 在 `TOOLS` 列表添加 JSON schema 定义
2. 在 `TOOL_REGISTRY` 注册函数

## 对应 12-Factor Agents 原则

| Factor | 实现位置 |
|--------|---------|
| 1. 自然语言→工具调用 | `TOOLS` schema + `execute_tool()` |
| 3. 掌控上下文窗口 | `build_system_prompt()` + `load_skills()` |
| 8. 掌控控制流 | `run_agent()` 中的 while 循环 |
| 12. 无状态 Reducer | `messages` 列表的状态转换模式 |

## 下一步

当遇到以下问题时，按需引入对应原则：

- **任务中断无法恢复** → Factor 6：添加 checkpoint 机制
- **上下文太长** → Factor 3：主动裁剪 messages 历史
- **需要人工确认** → Factor 7：添加 human_approval 工具
- **难以测试调试** → Factor 12：提取纯函数 reducer

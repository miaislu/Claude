"""
Financial Plugin MCP Server
纯 stdlib 实现 MCP 标准 stdio 协议（JSON-RPC 2.0 over stdin/stdout）。
兼容 Python 3.9+，无需 mcp 包。

启动方式：
  python3 server.py

注册到 Claude Code（~/.claude/settings.json 的 mcpServers 字段）：
  {
    "financial-plugin": {
      "command": "python3",
      "args": ["/Users/miazhang/Documents/Claude/projects/financial-plugin/server.py"]
    }
  }
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

_ROOT = Path(__file__).parent
sys.path.insert(0, str(_ROOT))

_SERVER_NAME    = "financial-plugin"
_SERVER_VERSION = "1.0.0"
_PROTOCOL_VER   = "2024-11-05"


# ══════════════════════════════════════════════════════════
# MCP Server 核心（纯 stdlib）
# ══════════════════════════════════════════════════════════

class MCPServer:
    def __init__(self) -> None:
        self._tools: dict[str, dict[str, Any]] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Callable[..., Any],
    ) -> None:
        self._tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
            "handler": handler,
        }

    def run(self) -> None:
        """主循环：读 stdin，写 stdout，逐行处理 JSON-RPC。"""
        for raw in sys.stdin:
            raw = raw.strip()
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError as e:
                self._write({"jsonrpc": "2.0", "id": None,
                             "error": {"code": -32700, "message": f"Parse error: {e}"}})
                continue

            try:
                response = self._dispatch(msg)
            except Exception as e:
                _log(f"Unhandled error: {e}\n{traceback.format_exc()}")
                mid = msg.get("id")
                if mid is not None:
                    self._write({"jsonrpc": "2.0", "id": mid,
                                 "error": {"code": -32603, "message": str(e)}})
                continue

            if response is not None:
                self._write(response)

    def _dispatch(self, msg: dict[str, Any]) -> dict | None:
        method = msg.get("method", "")
        mid    = msg.get("id")          # None for notifications
        params = msg.get("params", {})

        # ── MCP 握手 ──────────────────────────────────────
        if method == "initialize":
            return {
                "jsonrpc": "2.0", "id": mid,
                "result": {
                    "protocolVersion": _PROTOCOL_VER,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": _SERVER_NAME, "version": _SERVER_VERSION},
                },
            }

        if method == "notifications/initialized":
            return None  # 通知，无需响应

        # ── 工具列表 ──────────────────────────────────────
        if method == "tools/list":
            return {
                "jsonrpc": "2.0", "id": mid,
                "result": {
                    "tools": [
                        {
                            "name": t["name"],
                            "description": t["description"],
                            "inputSchema": t["inputSchema"],
                        }
                        for t in self._tools.values()
                    ]
                },
            }

        # ── 工具调用 ──────────────────────────────────────
        if method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})

            if tool_name not in self._tools:
                return {
                    "jsonrpc": "2.0", "id": mid,
                    "error": {"code": -32601, "message": f"Tool not found: {tool_name}"},
                }

            try:
                handler = self._tools[tool_name]["handler"]
                result  = handler(**arguments)
                text    = json.dumps(result, ensure_ascii=False, default=str, indent=2)
                return {
                    "jsonrpc": "2.0", "id": mid,
                    "result": {"content": [{"type": "text", "text": text}]},
                }
            except Exception as e:
                _log(f"Tool {tool_name} error: {e}\n{traceback.format_exc()}")
                return {
                    "jsonrpc": "2.0", "id": mid,
                    "result": {
                        "content": [{"type": "text", "text": f"Error in {tool_name}: {e}"}],
                        "isError": True,
                    },
                }

        # ── 未知方法 ──────────────────────────────────────
        if mid is not None:
            return {
                "jsonrpc": "2.0", "id": mid,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }
        return None

    @staticmethod
    def _write(obj: dict[str, Any]) -> None:
        print(json.dumps(obj, ensure_ascii=False, default=str), flush=True)


def _log(msg: str) -> None:
    """向 stderr 输出调试信息（不干扰 stdout 协议流）。"""
    print(f"[financial-plugin] {msg}", file=sys.stderr, flush=True)


# ══════════════════════════════════════════════════════════
# 工具 handlers（每个调用对应 Agent 方法）
# ══════════════════════════════════════════════════════════

def _handle_review_earnings(
    code: str,
    period: str,
    thesis: list[str] | None = None,
) -> dict:
    """读取 A 股财报，识别预期差，输出 thesis 验证和模型更新指令。"""
    from agents.earnings_reviewer import EarningsReviewer
    return EarningsReviewer().review(code, period, thesis or []).to_dict()


def _handle_build_model(
    code: str,
    period: str,
    g: float,
    comps_codes: list[str] | None = None,
) -> dict:
    """
    从零构建 A 股财务模型（三表 + DCF + 可比估值），生成 Excel 工作簿。
    g: 永续增长率（用户必须提供，如 0.05 表示 5%）
    """
    from agents.model_builder import ModelBuilder
    return ModelBuilder().build(code, period, g, comps_codes or []).to_dict()


def _handle_update_model(
    code: str,
    instructions_json: str,
) -> dict:
    """
    接收 Earnings Reviewer 的更新指令 JSON，更新已有财务模型。
    instructions_json: JSON 字符串，包含 ModelUpdateInstruction 列表。
    """
    from agents.model_builder import ModelBuilder
    from models import ModelUpdateInstruction

    raw = json.loads(instructions_json)
    if not isinstance(raw, list):
        raise ValueError("instructions_json 必须是 JSON 数组")
    instructions = [ModelUpdateInstruction(**item) for item in raw]
    return ModelBuilder().update(code, instructions).to_dict()


def _handle_review_valuation(
    code: str,
    context: str = "二级市场",
    industry: str = "",
    iteration: int = 0,
) -> dict:
    """
    审查最新财务模型的估值合理性，输出 PASS / REVISE / REJECT 裁定。
    从 storage/ 自动读取该 code 最新的 ModelBuildResult。
    """
    import json as _json
    from agents.valuation_reviewer import ValuationReviewer
    from models import ChangeLogEntry, LinkageError, ModelBuildResult

    # 读取最新 ModelBuildResult 存档
    storage = _ROOT / "storage"
    files = sorted(storage.glob(f"{code}_model_build_*.json"), reverse=True)
    if not files:
        raise FileNotFoundError(
            f"未找到 {code} 的 ModelBuildResult 存档，请先运行 build_model"
        )
    data = _json.loads(files[0].read_text(encoding="utf-8"))

    # 正确反序列化嵌套 dataclass（JSON 存档中它们是 list[dict]）
    scalar_fields = {
        k: v for k, v in data.items()
        if k in ModelBuildResult.__dataclass_fields__
        and k not in ("linkage_errors", "change_log")
    }
    mr = ModelBuildResult(
        **scalar_fields,
        linkage_errors=[LinkageError(**e) for e in (data.get("linkage_errors") or [])],
        change_log=[ChangeLogEntry(**e)   for e in (data.get("change_log")     or [])],
    )

    return ValuationReviewer().review(mr, context=context, industry=industry, iteration=iteration).to_dict()


def _handle_build_pitch(
    code: str,
    audience: str = "buyside_memo",
) -> dict:
    """
    合成投资材料（买方备忘录或 1-pager），读取所有上游 Agent 存档。
    audience: buyside_memo（默认）/ buyside_1pager / full_suite
    """
    from agents.pitch_builder import PitchBuilder
    return PitchBuilder().build(code, audience).to_dict()


def _handle_prepare_meeting(
    code: str,
    meeting_type: str = "company_visit",
    meeting_time: str | None = None,
    attendees: list[str] | None = None,
    thesis: list[str] | None = None,
    fresh_window_h: float = 2.0,
) -> dict:
    """
    生成会前情报简报和问题清单（Markdown 文件）。
    meeting_type: company_visit / earnings_call / roadshow / investment_committee
    attendees: ["CEO", "CFO", "IR"] 等
    """
    from agents.meeting_preparer import MeetingPreparer
    return MeetingPreparer().prepare(
        code, meeting_type, meeting_time,
        attendees or [], thesis or [], fresh_window_h,
    ).to_dict()


def _handle_prepare_expert_call(
    sector: str,
    focus_topics: list[str] | None = None,
    meeting_time: str | None = None,
) -> dict:
    """
    为行业专家访谈生成简报和问题清单，不需要股票代码。
    sector: 如 "电力设备"、"食品饮料"
    focus_topics: 访谈重点列表
    """
    from agents.meeting_preparer import MeetingPreparer
    return MeetingPreparer().prepare_expert_call(
        sector, focus_topics or [], meeting_time
    ).to_dict()


def _handle_scan_market(
    codes: list[str] | None = None,
) -> dict:
    """
    扫描 watchlist（或指定股票列表）近期公告，分级输出市场信号摘要。
    codes 为空时使用 config/watchlist.yaml 中的默认监控列表。
    """
    from agents.market_researcher import MarketResearcher
    return MarketResearcher().run_daily_scan(codes or []).to_dict()


def _handle_query_market(
    code: str,
    days: int = 30,
    thesis: list[str] | None = None,
) -> dict:
    """
    临时查询单只股票近 N 天的公告信号，标注与 thesis 的相关性。
    """
    from agents.market_researcher import MarketResearcher
    return MarketResearcher().query(code, days, thesis or []).to_dict()


# ══════════════════════════════════════════════════════════
# JSON Schema（每个工具的输入模式）
# ══════════════════════════════════════════════════════════

_STR  = {"type": "string"}
_INT  = {"type": "integer"}
_NUM  = {"type": "number"}
_SARR = {"type": "array", "items": {"type": "string"}}


def _schema(required: list[str], props: dict[str, dict]) -> dict:
    return {"type": "object", "required": required, "properties": props}


_SCHEMAS: dict[str, dict] = {
    "review_earnings": _schema(
        ["code", "period"],
        {
            "code":   {**_STR, "description": "6位股票代码，如 '600519'"},
            "period": {**_STR, "description": "报告期 ISO 格式，如 '2024-12-31'"},
            "thesis": {**_SARR, "description": "投资论点关键词列表，如 ['高端化','提价']"},
        },
    ),
    "build_model": _schema(
        ["code", "period", "g"],
        {
            "code":        {**_STR, "description": "6位股票代码"},
            "period":      {**_STR, "description": "最新报告期，如 '2024-12-31'"},
            "g":           {**_NUM, "description": "永续增长率（小数），如 0.05 表示 5%"},
            "comps_codes": {**_SARR, "description": "可比公司代码列表（可选）"},
        },
    ),
    "update_model": _schema(
        ["code", "instructions_json"],
        {
            "code":              {**_STR, "description": "6位股票代码"},
            "instructions_json": {**_STR, "description": "ModelUpdateInstruction 列表的 JSON 字符串"},
        },
    ),
    "review_valuation": _schema(
        ["code"],
        {
            "code":      {**_STR, "description": "6位股票代码（从 storage/ 读取最新 ModelBuildResult）"},
            "context":   {**_STR, "description": "估值背景：二级市场（默认）/ IPO / 并购"},
            "industry":  {**_STR, "description": "公司所属行业，如 '食品饮料'"},
            "iteration": {**_INT, "description": "当前迭代轮次，0=首次（默认）"},
        },
    ),
    "build_pitch": _schema(
        ["code"],
        {
            "code":     {**_STR, "description": "6位股票代码"},
            "audience": {
                "type": "string",
                "enum": ["buyside_memo", "buyside_1pager", "full_suite"],
                "description": "受众类型，默认 buyside_memo",
            },
        },
    ),
    "prepare_meeting": _schema(
        ["code"],
        {
            "code":           {**_STR, "description": "6位股票代码"},
            "meeting_type":   {
                "type": "string",
                "enum": ["company_visit", "earnings_call", "roadshow", "investment_committee"],
                "description": "会议类型，默认 company_visit",
            },
            "meeting_time":   {**_STR, "description": "会议时间，ISO 格式，如 '2025-03-15 14:00'（可选）"},
            "attendees":      {**_SARR, "description": "参会方列表，如 ['CEO','CFO']（可选）"},
            "thesis":         {**_SARR, "description": "投资论点关键词（覆盖 watchlist 默认值）"},
            "fresh_window_h": {**_NUM,  "description": "实时数据拉取时间窗口（小时），默认 2"},
        },
    ),
    "prepare_expert_call": _schema(
        ["sector"],
        {
            "sector":       {**_STR,  "description": "行业名称，如 '电力设备'"},
            "focus_topics": {**_SARR, "description": "访谈重点列表，如 ['储能需求','竞争格局']"},
            "meeting_time": {**_STR,  "description": "会议时间（可选）"},
        },
    ),
    "scan_market": _schema(
        [],
        {
            "codes": {**_SARR, "description": "额外监控的股票代码列表（可选，空则用 watchlist.yaml）"},
        },
    ),
    "query_market": _schema(
        ["code"],
        {
            "code":   {**_STR,  "description": "6位股票代码"},
            "days":   {**_INT,  "description": "查询最近 N 天，默认 30"},
            "thesis": {**_SARR, "description": "投资论点关键词（可选）"},
        },
    ),
}


# ══════════════════════════════════════════════════════════
# 工具注册与入口
# ══════════════════════════════════════════════════════════

_TOOLS: list[tuple[str, str, Callable]] = [
    ("review_earnings",
     "读取 A 股财报（季报/中报/年报），识别预期差，验证投资论点，生成模型更新指令。",
     _handle_review_earnings),

    ("build_model",
     "从历史财务数据构建 A 股三表模型 + DCF 估值，输出目标价和 Excel 工作簿。需用户提供永续增长率 g。",
     _handle_build_model),

    ("update_model",
     "接收 Earnings Reviewer 的更新指令，自动更新已有财务模型（HIGH confidence 项自动执行）。",
     _handle_update_model),

    ("review_valuation",
     "从方法论、可比公司、关键假设、A 股特有调整、终值合理性五维度审查估值，输出 PASS/REVISE/REJECT。",
     _handle_review_valuation),

    ("build_pitch",
     "合成投资材料：从所有上游 Agent 存档生成买方投资备忘录（Word）或 Markdown 1-pager。",
     _handle_build_pitch),

    ("prepare_meeting",
     "生成会前情报简报（≤800字 Markdown）和结构化问题清单，支持公司调研/业绩会/路演/投委会。",
     _handle_prepare_meeting),

    ("prepare_expert_call",
     "为行业专家访谈生成简报和问题清单，只需行业名称，不需要股票代码。",
     _handle_prepare_expert_call),

    ("scan_market",
     "扫描 watchlist 监控股票的近期公告，按 P0/P1/P2 优先级分类，追踪投资论点健康度。",
     _handle_scan_market),

    ("query_market",
     "临时查询单只股票近 N 天的公告信号，标注与投资论点的 CONFIRM/RISK/NEUTRAL 关系。",
     _handle_query_market),
]


def build_server() -> MCPServer:
    server = MCPServer()
    for name, description, handler in _TOOLS:
        server.register_tool(name, description, _SCHEMAS[name], handler)
    return server


if __name__ == "__main__":
    _log(f"Starting {_SERVER_NAME} v{_SERVER_VERSION} (Python {sys.version.split()[0]})")
    _log(f"Registered tools: {[t[0] for t in _TOOLS]}")
    build_server().run()

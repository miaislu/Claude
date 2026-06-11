"""
MCP Server 离线协议测试。
直接调用 MCPServer._dispatch()，不走 stdin/stdout，不触发网络。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ──────────────────────────────────────────
# 辅助 fixtures
# ──────────────────────────────────────────

@pytest.fixture
def server():
    from server import build_server
    return build_server()


def req(method: str, params: dict | None = None, id_: int = 1) -> dict:
    msg = {"jsonrpc": "2.0", "id": id_, "method": method}
    if params:
        msg["params"] = params
    return msg


def notify(method: str, params: dict | None = None) -> dict:
    """通知消息（无 id）。"""
    msg = {"jsonrpc": "2.0", "method": method}
    if params:
        msg["params"] = params
    return msg


# ──────────────────────────────────────────
# 握手协议
# ──────────────────────────────────────────

class TestHandshake:
    def test_initialize_returns_protocol_version(self, server):
        resp = server._dispatch(req("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"},
        }))
        assert resp["result"]["protocolVersion"] == "2024-11-05"
        assert resp["result"]["serverInfo"]["name"] == "financial-plugin"
        assert "tools" in resp["result"]["capabilities"]

    def test_initialized_notification_returns_none(self, server):
        resp = server._dispatch(notify("notifications/initialized"))
        assert resp is None

    def test_unknown_method_returns_error(self, server):
        resp = server._dispatch(req("unknown/method"))
        assert "error" in resp
        assert resp["error"]["code"] == -32601

    def test_unknown_notification_returns_none(self, server):
        """无 id 的未知方法：是通知，不应有响应。"""
        resp = server._dispatch(notify("unknown/notification"))
        assert resp is None


# ──────────────────────────────────────────
# tools/list
# ──────────────────────────────────────────

class TestToolsList:
    def test_returns_all_9_tools(self, server):
        resp = server._dispatch(req("tools/list"))
        tools = resp["result"]["tools"]
        names = {t["name"] for t in tools}
        expected = {
            "review_earnings", "build_model", "update_model",
            "review_valuation", "build_pitch",
            "prepare_meeting", "prepare_expert_call",
            "scan_market", "query_market",
        }
        assert names == expected

    def test_each_tool_has_description_and_schema(self, server):
        resp = server._dispatch(req("tools/list"))
        for tool in resp["result"]["tools"]:
            assert tool["name"]
            assert tool["description"]
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"

    def test_required_fields_in_schemas(self, server):
        resp = server._dispatch(req("tools/list"))
        schema_map = {t["name"]: t["inputSchema"] for t in resp["result"]["tools"]}

        # review_earnings 需要 code 和 period
        er = schema_map["review_earnings"]
        assert "code" in er["required"]
        assert "period" in er["required"]
        assert "code" in er["properties"]

        # build_model 需要 g（用户必须提供）
        bm = schema_map["build_model"]
        assert "g" in bm["required"]
        assert bm["properties"]["g"]["type"] == "number"

        # prepare_expert_call 需要 sector 而非 code
        ec = schema_map["prepare_expert_call"]
        assert "sector" in ec["required"]
        assert "code" not in ec.get("required", [])

        # review_valuation 的 code 是 required
        rv = schema_map["review_valuation"]
        assert "code" in rv["required"]

    def test_audience_is_enum_in_build_pitch(self, server):
        resp = server._dispatch(req("tools/list"))
        schema_map = {t["name"]: t["inputSchema"] for t in resp["result"]["tools"]}
        aud_prop = schema_map["build_pitch"]["properties"]["audience"]
        assert "enum" in aud_prop
        assert "buyside_memo" in aud_prop["enum"]


# ──────────────────────────────────────────
# tools/call
# ──────────────────────────────────────────

class TestToolsCall:
    def test_unknown_tool_returns_error(self, server):
        resp = server._dispatch(req("tools/call", {
            "name": "nonexistent_tool",
            "arguments": {},
        }))
        assert "error" in resp
        assert resp["error"]["code"] == -32601

    def test_tool_error_returns_is_error_true(self, server):
        """当 handler 抛异常时，响应包含 isError=True。"""
        resp = server._dispatch(req("tools/call", {
            "name": "update_model",
            "arguments": {
                "code": "600519",
                "instructions_json": "not valid json!!!",
            },
        }))
        result = resp["result"]
        assert result.get("isError") is True
        assert result["content"][0]["type"] == "text"

    def test_tool_result_is_json_text(self, server, monkeypatch, tmp_path):
        """Mock EarningsReviewer.review() 验证工具返回 JSON 文本。"""
        from models import EarningsReviewResult

        mock_result = EarningsReviewResult(
            stock_code="600519",
            period="2024-12-31",
            report_type="年报",
            overall_verdict="BEAT",
            summary="测试摘要",
        )

        import agents.earnings_reviewer as er_mod
        monkeypatch.setattr(
            er_mod.EarningsReviewer, "review",
            lambda self, code, period, thesis: mock_result
        )

        resp = server._dispatch(req("tools/call", {
            "name": "review_earnings",
            "arguments": {
                "code": "600519",
                "period": "2024-12-31",
                "thesis": ["高端化"],
            },
        }))

        assert "result" in resp
        assert "isError" not in resp["result"]
        content = resp["result"]["content"][0]
        assert content["type"] == "text"

        data = json.loads(content["text"])
        assert data["stock_code"] == "600519"
        assert data["overall_verdict"] == "BEAT"

    def test_review_valuation_missing_file_returns_error(self, server):
        """当 storage/ 没有该 code 的 ModelBuildResult 时，返回 isError。"""
        resp = server._dispatch(req("tools/call", {
            "name": "review_valuation",
            "arguments": {"code": "999999"},   # 不存在的股票
        }))
        result = resp["result"]
        assert result.get("isError") is True

    def test_scan_market_returns_json_text(self, server, monkeypatch):
        """Mock MarketResearcher.run_daily_scan() 验证工具链路。"""
        from models import MarketResearchDigest

        mock_digest = MarketResearchDigest(
            digest_date="2025-01-15",
            digest_type="daily",
            stocks_monitored=["600519"],
        )

        import agents.market_researcher as mr_mod
        monkeypatch.setattr(
            mr_mod.MarketResearcher, "run_daily_scan",
            lambda self, codes: mock_digest
        )

        resp = server._dispatch(req("tools/call", {
            "name": "scan_market",
            "arguments": {"codes": ["600519"]},
        }))

        assert "result" in resp
        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["digest_type"] == "daily"
        assert "600519" in data["stocks_monitored"]


# ──────────────────────────────────────────
# 协议边缘情况
# ──────────────────────────────────────────

class TestProtocolEdgeCases:
    def test_id_preserved_in_response(self, server):
        resp = server._dispatch(req("tools/list", id_=42))
        assert resp["id"] == 42

    def test_jsonrpc_version_in_all_responses(self, server):
        for method in ["initialize", "tools/list"]:
            resp = server._dispatch(req(method, params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "t", "version": "1"},
            } if method == "initialize" else None))
            assert resp["jsonrpc"] == "2.0"

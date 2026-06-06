#!/usr/bin/env python3
"""
北大法宝 MCP 轻量客户端。

用途：
- 验证已注册的北大法宝 MCP 服务是否可直接通过 HTTP MCP 调用。
- 为 legal_citation_check.py / update_legal_citations.py 提供显式上游核验能力。

要求：
- 环境变量 PKULAW_ACCESS_TOKEN 已设置。
- 默认只调用精准法条服务 mcp-fatiao。
"""

import argparse
import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional


DEFAULT_ENDPOINT = "https://apim-gateway.pkulaw.com/mcp-fatiao"
DEFAULT_PROTOCOL_VERSION = "2024-11-05"


class PkulawMcpError(RuntimeError):
    pass


def parse_sse_json(raw: str) -> dict[str, Any]:
    """北大法宝 streamable HTTP 返回 SSE 文本，data 行中是 JSON-RPC payload。"""
    for line in raw.splitlines():
        if line.startswith("data:"):
            payload = line[len("data:"):].strip()
            if payload:
                return json.loads(payload)
    return json.loads(raw)


def post_json_rpc(endpoint: str, payload: dict[str, Any], token: Optional[str] = None) -> dict[str, Any]:
    token = token or os.environ.get("PKULAW_ACCESS_TOKEN", "")
    if not token:
        raise PkulawMcpError("缺少环境变量 PKULAW_ACCESS_TOKEN。")

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise PkulawMcpError(f"北大法宝 MCP HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise PkulawMcpError(f"北大法宝 MCP 连接失败：{exc}") from exc

    result = parse_sse_json(raw)
    if "error" in result:
        raise PkulawMcpError(json.dumps(result["error"], ensure_ascii=False))
    return result


def initialize(endpoint: str = DEFAULT_ENDPOINT) -> dict[str, Any]:
    return post_json_rpc(endpoint, {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": DEFAULT_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "falv-agent", "version": "0.1"},
        },
    })


def list_tools(endpoint: str = DEFAULT_ENDPOINT) -> dict[str, Any]:
    return post_json_rpc(endpoint, {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    })


def call_tool(endpoint: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return post_json_rpc(endpoint, {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    })


def get_law_item_content(title: str, article_number: float, endpoint: str = DEFAULT_ENDPOINT) -> dict[str, Any]:
    return call_tool(endpoint, "get_law_item_content", {
        "title": title,
        "tiao_num": article_number,
    })


def extract_tool_text_json(result: dict[str, Any]) -> dict[str, Any]:
    content = result.get("result", {}).get("content", [])
    if not isinstance(content, list):
        return {}
    for item in content:
        if not isinstance(item, dict) or item.get("type") != "text":
            continue
        text = item.get("text", "")
        if not text:
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"Text": text}
    return {}


def summarize_law_item_response(result: dict[str, Any]) -> dict[str, Any]:
    payload = extract_tool_text_json(result)
    data = payload.get("Data", {}) if isinstance(payload, dict) else {}
    full_text = data.get("FullText", "") if isinstance(data, dict) else ""
    return {
        "code": payload.get("Code", "") if isinstance(payload, dict) else "",
        "message": payload.get("Message", "") if isinstance(payload, dict) else "",
        "title": data.get("Title", ""),
        "article": data.get("Tiao", ""),
        "timeliness": data.get("TimelinessDic", {}),
        "effectiveness": data.get("EffectivenessDic", {}),
        "issue_date": data.get("IssueDate", ""),
        "implement_date": data.get("ImplementDate", ""),
        "update_time": data.get("UpdateTime", ""),
        "url": data.get("Url", ""),
        "full_text_excerpt": full_text[:500],
    }


def main():
    parser = argparse.ArgumentParser(description="北大法宝 MCP 轻量客户端")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="MCP endpoint")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("initialize", help="初始化 MCP 连接")
    sub.add_parser("tools", help="列出 MCP 工具")

    p_law = sub.add_parser("law-item", help="精准查询法条内容")
    p_law.add_argument("--title", required=True, help="法律标题关键词，如 民法典")
    p_law.add_argument("--article", required=True, type=float, help="条号，如 585")

    args = parser.parse_args()
    if args.command == "initialize":
        result = initialize(args.endpoint)
    elif args.command == "tools":
        result = list_tools(args.endpoint)
    elif args.command == "law-item":
        result = get_law_item_content(args.title, args.article, args.endpoint)
        result = {
            "raw": result,
            "summary": summarize_law_item_response(result),
        }
    else:
        parser.print_help()
        return
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

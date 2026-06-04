#!/usr/bin/env python3
"""
中国法律 AI Agent — 检查点管理器（Factor 6: Launch/Pause/Resume）

用法：
  python3 checkpoint.py save   --project 名称 --context '{...}' --report report.md --output /path/
  python3 checkpoint.py update --project 名称 --status completed --docx /path/to.docx --dir /path/
  python3 checkpoint.py load   --file /path/to.checkpoint.json
  python3 checkpoint.py list   --dir /path/to/reports/
"""

import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


CHECKPOINT_VERSION = "1.0"


def _find_latest_checkpoint(project_name: str, reports_dir: str) -> Optional[str]:
    """查找指定项目最新的检查点文件"""
    pattern = os.path.join(reports_dir, f"{project_name}_审查报告_*.checkpoint.json")
    files = sorted(glob.glob(pattern), reverse=True)
    return files[0] if files else None


def cmd_save(args):
    """保存检查点"""
    reports_dir = os.path.expanduser(args.output)
    os.makedirs(reports_dir, exist_ok=True)

    # 解析 session_context
    try:
        ctx = json.loads(args.context) if args.context else {}
    except json.JSONDecodeError:
        ctx = {"raw": args.context}

    # 读取报告 Markdown
    report_md = ""
    if args.report and os.path.exists(args.report):
        with open(args.report, "r", encoding="utf-8") as f:
            report_md = f.read()

    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    safe_name = re.sub(r'[\\/:*?"<>|]', '_', args.project)
    filename = f"{safe_name}_审查报告_{timestamp}.checkpoint.json"
    filepath = os.path.join(reports_dir, filename)

    checkpoint = {
        "checkpoint_version": CHECKPOINT_VERSION,
        "project_name": args.project,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "status": "report_generated",
        "session_context": ctx,
        "report_markdown": report_md,
        "skipped_agents": [],
        "docx_path": None,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)

    print(f"✅ 检查点已保存：{filepath}")
    return filepath


def cmd_update(args):
    """更新检查点状态（通常在 Word 导出成功后调用）"""
    reports_dir = os.path.expanduser(args.dir)
    filepath = _find_latest_checkpoint(args.project, reports_dir)

    if not filepath:
        print(f"⚠️  未找到项目 [{args.project}] 的检查点，跳过更新", file=sys.stderr)
        return

    with open(filepath, "r", encoding="utf-8") as f:
        checkpoint = json.load(f)

    if args.status:
        checkpoint["status"] = args.status
    if args.docx:
        checkpoint["docx_path"] = os.path.expanduser(args.docx)

    checkpoint["updated_at"] = datetime.now().isoformat()

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)

    print(f"✅ 检查点已更新：{filepath}（状态: {checkpoint['status']}）")


def cmd_load(args):
    """加载并显示检查点内容"""
    filepath = os.path.expanduser(args.file)

    if not os.path.exists(filepath):
        print(f"❌ 检查点文件不存在：{filepath}", file=sys.stderr)
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        checkpoint = json.load(f)

    # 版本兼容检查
    if checkpoint.get("checkpoint_version") != CHECKPOINT_VERSION:
        print(
            f"⚠️  检查点版本不匹配（文件: {checkpoint.get('checkpoint_version')}，"
            f"当前: {CHECKPOINT_VERSION}），可能存在兼容性问题",
            file=sys.stderr,
        )

    # 输出摘要（供 Claude 读取和显示）
    print("=" * 60)
    print(f"项目名称：{checkpoint['project_name']}")
    print(f"创建时间：{checkpoint['created_at'][:16].replace('T', ' ')}")
    print(f"当前状态：{checkpoint['status']}")
    if checkpoint.get("session_context"):
        ctx = checkpoint["session_context"]
        print(f"合同类型：{ctx.get('contract_type', '未知')}")
        print(f"审查立场：{ctx.get('party_stance', '未知')}")
    if checkpoint.get("skipped_agents"):
        print(f"跳过 Agent：{', '.join(checkpoint['skipped_agents'])}")
    if checkpoint.get("docx_path"):
        print(f"Word 文件：{checkpoint['docx_path']}")
    print("=" * 60)

    # 将报告内容输出到 stdout（供 Claude 展示）
    if checkpoint.get("report_markdown"):
        print("\n--- 报告内容 ---\n")
        print(checkpoint["report_markdown"])

    return checkpoint


def cmd_list(args):
    """列出指定目录下的所有检查点"""
    reports_dir = os.path.expanduser(args.dir)
    pattern = os.path.join(reports_dir, "*.checkpoint.json")
    files = sorted(glob.glob(pattern), reverse=True)

    if not files:
        print(f"📭 在 {reports_dir} 中未找到任何检查点")
        return

    print(f"📋 共找到 {len(files)} 个检查点：\n")
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                cp = json.load(fp)
            status_icon = {"completed": "✅", "report_generated": "📄", "in_progress": "⏳"}.get(
                cp.get("status", ""), "❓"
            )
            print(
                f"  {status_icon} {cp.get('project_name', '?')} "
                f"— {cp.get('created_at', '')[:16].replace('T', ' ')} "
                f"({cp.get('status', '?')})"
            )
            print(f"     文件：{os.path.basename(f)}")
        except Exception:
            print(f"  ❓ 无法读取：{f}")


# ── CLI ──────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="法律 Agent 检查点管理器")
    sub = parser.add_subparsers(dest="command")

    # save
    p_save = sub.add_parser("save", help="保存检查点")
    p_save.add_argument("--project",  required=True, help="项目名称")
    p_save.add_argument("--context",  default="{}", help="session_context JSON 字符串")
    p_save.add_argument("--report",   default=None, help="报告 Markdown 文件路径")
    p_save.add_argument("--output",   required=True, help="输出目录")

    # update
    p_upd = sub.add_parser("update", help="更新检查点状态")
    p_upd.add_argument("--project", required=True, help="项目名称")
    p_upd.add_argument("--status",  default=None, help="新状态")
    p_upd.add_argument("--docx",    default=None, help="Word 文件路径")
    p_upd.add_argument("--dir",     required=True, help="reports 目录")

    # load
    p_load = sub.add_parser("load", help="加载检查点")
    p_load.add_argument("--file", required=True, help="检查点文件路径")

    # list
    p_list = sub.add_parser("list", help="列出所有检查点")
    p_list.add_argument("--dir", required=True, help="reports 目录")

    args = parser.parse_args()

    if args.command == "save":
        cmd_save(args)
    elif args.command == "update":
        cmd_update(args)
    elif args.command == "load":
        cmd_load(args)
    elif args.command == "list":
        cmd_list(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

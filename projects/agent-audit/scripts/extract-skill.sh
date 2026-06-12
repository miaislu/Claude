#!/bin/bash
# extract-skill.sh — 将 zip 包或目录路径规范化为可审查的 skill_root 路径
#
# 用法：
#   bash scripts/extract-skill.sh /path/to/skill.zip
#   bash scripts/extract-skill.sh /path/to/skill-directory/
#
# 输出：
#   stdout: skill_root 的绝对路径（包含 SKILL.md 的目录）
#   exit 0: 成功
#   exit 1: 失败（错误信息输出到 stderr）

INPUT="$1"

if [[ -z "$INPUT" ]]; then
    echo "用法：$0 <zip文件路径 | skill目录路径>" >&2
    exit 1
fi

# 展开 ~ 和相对路径
INPUT="${INPUT/#\~/$HOME}"
INPUT="$(cd "$(dirname "$INPUT")" 2>/dev/null && pwd)/$(basename "$INPUT")" 2>/dev/null || INPUT="$1"

if [[ -f "$INPUT" && "$INPUT" == *.zip ]]; then
    # zip 输入：解压到临时目录
    if ! command -v unzip &>/dev/null; then
        echo "ERROR: unzip 未安装，无法处理 zip 文件" >&2
        exit 1
    fi

    TMPDIR=$(mktemp -d /tmp/agent-audit-XXXXXX)
    if ! unzip -q "$INPUT" -d "$TMPDIR" 2>/dev/null; then
        echo "ERROR: 解压失败，请检查 zip 文件是否损坏：$INPUT" >&2
        rm -rf "$TMPDIR"
        exit 1
    fi

    # 找到包含 SKILL.md 的目录（最多深入 3 层）
    SKILL_MD=$(find "$TMPDIR" -name "SKILL.md" -maxdepth 3 2>/dev/null | head -1)

    if [[ -z "$SKILL_MD" ]]; then
        echo "ERROR: zip 包中未找到 SKILL.md（搜索深度 3 层）" >&2
        rm -rf "$TMPDIR"
        exit 1
    fi

    SKILL_ROOT=$(dirname "$SKILL_MD")
    echo "$SKILL_ROOT"

elif [[ -d "$INPUT" ]]; then
    # 目录输入：直接验证
    SKILL_MD="$INPUT/SKILL.md"

    if [[ ! -f "$SKILL_MD" ]]; then
        # 尝试在子目录中找
        SKILL_MD=$(find "$INPUT" -name "SKILL.md" -maxdepth 2 2>/dev/null | head -1)
        if [[ -z "$SKILL_MD" ]]; then
            echo "ERROR: 目录中未找到 SKILL.md：$INPUT" >&2
            exit 1
        fi
    fi

    SKILL_ROOT=$(dirname "$SKILL_MD")
    echo "$(cd "$SKILL_ROOT" && pwd)"

else
    echo "ERROR: 输入路径不存在或格式不支持：$INPUT" >&2
    echo "支持的格式：.zip 文件 或 包含 SKILL.md 的目录" >&2
    exit 1
fi

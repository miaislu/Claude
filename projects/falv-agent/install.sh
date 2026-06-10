#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# 中国法律 AI Agent — 安装脚本
# 将技能和 Agent 部署到 ~/.claude/ 目录，使其在 Claude Code 中全局可用
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
SKILLS_SRC="$SCRIPT_DIR/skills"
AGENTS_SRC="$SCRIPT_DIR/agents"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()    { echo -e "${BLUE}[信息]${NC} $*"; }
success() { echo -e "${GREEN}[完成]${NC} $*"; }
warn()    { echo -e "${YELLOW}[警告]${NC} $*"; }
error()   { echo -e "${RED}[错误]${NC} $*"; exit 1; }

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║       中国法律 AI Agent — 安装程序            ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── 检查 Claude Code 是否安装 ───────────────────────────────────────────────
if ! command -v claude &>/dev/null; then
    warn "未检测到 Claude Code CLI。安装完成后请先安装 Claude Code。"
    warn "安装方式：https://claude.ai/code"
fi

# ── 创建目标目录 ──────────────────────────────────────────────────────────────
info "创建 Claude Code 目录结构..."
mkdir -p "$CLAUDE_DIR/skills"
mkdir -p "$CLAUDE_DIR/agents"

# ── 安装技能 ──────────────────────────────────────────────────────────────────
info "安装法律技能..."

SKILLS=(legal onboard review risk compliance draft plain-language labor corporate report)
SKILL_NAMES=("主路由(/legal)" "冷启动面试" "合同审查" "风险评估" "合规检查" "文件起草" "白话翻译" "劳动合同" "公司法" "Word报告")

installed_skills=0
for i in "${!SKILLS[@]}"; do
    skill="${SKILLS[$i]}"
    name="${SKILL_NAMES[$i]}"
    src="$SKILLS_SRC/$skill"
    dst="$CLAUDE_DIR/skills/$skill"

    if [[ -d "$src" ]]; then
        mkdir -p "$dst"
        cp "$src/SKILL.md" "$dst/SKILL.md"
        success "  ✓ /legal $skill（$name）"
        ((installed_skills++))
    else
        warn "  ✗ 未找到技能文件：$src/SKILL.md"
    fi
done

# ── 安装 Agent ────────────────────────────────────────────────────────────────
info "安装专项 Agent..."

AGENTS=(clause-analyzer risk-assessor compliance-checker obligations-extractor amendment-writer)
AGENT_NAMES=("条款分析师" "风险评估师" "合规检查员" "权利义务解析" "修改建议引擎")

# 公共指南（所有 Agent 依赖）
if [[ -f "$AGENTS_SRC/_guidelines.md" ]]; then
    cp "$AGENTS_SRC/_guidelines.md" "$CLAUDE_DIR/agents/_guidelines.md"
    success "  ✓ 公共指南（_guidelines.md）"
fi

# 类型专项上下文（context 目录）
if [[ -d "$AGENTS_SRC/context" ]]; then
    mkdir -p "$CLAUDE_DIR/agents/context"
    cp "$AGENTS_SRC/context/"*.md "$CLAUDE_DIR/agents/context/"
    context_count=$(ls "$AGENTS_SRC/context/"*.md 2>/dev/null | wc -l | tr -d ' ')
    success "  ✓ 合同类型专项上下文（${context_count} 个文件）"
fi

installed_agents=0
for i in "${!AGENTS[@]}"; do
    agent="${AGENTS[$i]}"
    name="${AGENT_NAMES[$i]}"
    src="$AGENTS_SRC/$agent.md"
    dst="$CLAUDE_DIR/agents/$agent.md"

    if [[ -f "$src" ]]; then
        cp "$src" "$dst"
        success "  ✓ $name（$agent）"
        ((installed_agents++))
    else
        warn "  ✗ 未找到 Agent 文件：$src"
    fi
done

# ── 部署脚本 ──────────────────────────────────────────────────────────────────
info "部署脚本..."
mkdir -p "$CLAUDE_DIR/scripts"
for script in pipeline.py security_preflight.py redact_contract.py legal_citation_check.py legal_coverage_check.py pkulaw_mcp_client.py pkulaw_batch_verify.py usage_log.py update_legal_citations.py render_report.py generate_docx.py generate_pdf.py checkpoint.py eval_runner.py bundle_review.py; do
    if [[ -f "$SCRIPT_DIR/scripts/$script" ]]; then
        cp "$SCRIPT_DIR/scripts/$script" "$CLAUDE_DIR/scripts/$script"
        success "  ✓ $script"
    fi
done

if [[ -d "$SCRIPT_DIR/legal_knowledge" ]]; then
    mkdir -p "$CLAUDE_DIR/legal_knowledge"
    cp "$SCRIPT_DIR/legal_knowledge/"*.json "$CLAUDE_DIR/legal_knowledge/" 2>/dev/null || true
    cp "$SCRIPT_DIR/legal_knowledge/README.md" "$CLAUDE_DIR/legal_knowledge/README.md" 2>/dev/null || true
    success "  ✓ legal_knowledge 结构化法条知识库"
fi

# ── 创建报告存放目录 ───────────────────────────────────────────────────────────
REPORTS_DIR="$SCRIPT_DIR/reports"
mkdir -p "$REPORTS_DIR"
success "  ✓ reports/ 目录就绪：$REPORTS_DIR"

# ── 检查 Python 依赖 ──────────────────────────────────────────────────────────
echo ""
info "检查 Python 依赖..."
if command -v python3 &>/dev/null; then
    if python3 -c "import anthropic" &>/dev/null 2>&1; then
        success "  ✓ anthropic 已安装（核心分析管道）"
    else
        warn "  ✗ anthropic 未安装（分析功能不可用，必装）"
        echo "      pip3 install anthropic"
    fi
    if python3 -c "import docx" &>/dev/null 2>&1; then
        success "  ✓ python-docx 已安装（Word 报告生成）"
    else
        warn "  ✗ python-docx 未安装（Word 报告功能不可用）"
        echo "      pip3 install python-docx"
    fi
    if python3 -c "import reportlab" &>/dev/null 2>&1; then
        success "  ✓ reportlab 已安装（PDF 报告生成）"
    else
        warn "  ✗ reportlab 未安装（PDF 报告功能不可用）"
        echo "      pip3 install reportlab"
    fi
else
    warn "  未检测到 python3，报告生成功能将不可用。"
fi

# ── 安装完成 ──────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║              安装完成！                       ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
success "已安装 ${installed_skills} 个技能，${installed_agents} 个 Agent"
echo ""
echo "  在 Claude Code 中使用："
echo "  ┌────────────────────────────────────────────────┐"
echo "  │  /legal onboard              （首次使用，设置画像）│"
echo "  │  /legal review 合同.pdf                        │"
echo "  │  /legal risk 协议.txt                          │"
echo "  │  /legal compliance --type pipl                 │"
echo "  │  /legal draft --type 劳动合同                  │"
echo "  │  /legal                  （查看所有命令）       │"
echo "  └────────────────────────────────────────────────┘"
echo ""
echo "  文档：查看 CLAUDE.md 了解完整功能说明"
echo ""

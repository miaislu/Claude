#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# 中国法律 AI Agent — 卸载脚本
# 从 ~/.claude/ 目录移除所有已安装的技能和 Agent
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

CLAUDE_DIR="$HOME/.claude"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[信息]${NC} $*"; }
success() { echo -e "${GREEN}[完成]${NC} $*"; }
warn()    { echo -e "${YELLOW}[警告]${NC} $*"; }

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║       中国法律 AI Agent — 卸载程序            ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# 确认提示
read -rp "确认卸载所有法律 Agent 技能？[y/N] " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "已取消。"
    exit 0
fi

echo ""

# ── 移除技能 ──────────────────────────────────────────────────────────────────
info "移除法律技能..."

SKILLS=(legal onboard review risk compliance draft plain-language labor corporate report)

for skill in "${SKILLS[@]}"; do
    target="$CLAUDE_DIR/skills/$skill"
    if [[ -d "$target" ]]; then
        rm -rf "$target"
        success "  ✓ 已移除技能：$skill"
    else
        warn "  - 技能不存在（跳过）：$skill"
    fi
done

# ── 移除 Agent ────────────────────────────────────────────────────────────────
info "移除专项 Agent..."

AGENTS=(clause-analyzer risk-assessor compliance-checker obligations-extractor amendment-writer _guidelines)

for agent in "${AGENTS[@]}"; do
    target="$CLAUDE_DIR/agents/$agent.md"
    if [[ -f "$target" ]]; then
        rm -f "$target"
        success "  ✓ 已移除 Agent：$agent"
    else
        warn "  - Agent 不存在（跳过）：$agent"
    fi
done

# ── 移除 context 目录 ─────────────────────────────────────────────────────────
if [[ -d "$CLAUDE_DIR/agents/context" ]]; then
    rm -rf "$CLAUDE_DIR/agents/context"
    success "  ✓ 已移除合同类型专项上下文目录"
fi

# ── 移除脚本 ──────────────────────────────────────────────────────────────────
info "移除脚本..."
SCRIPTS=(pipeline.py security_preflight.py redact_contract.py legal_citation_check.py \
         legal_coverage_check.py pkulaw_mcp_client.py pkulaw_batch_verify.py usage_log.py \
         update_legal_citations.py render_report.py generate_docx.py generate_pdf.py \
         checkpoint.py eval_runner.py bundle_review.py)
for script in "${SCRIPTS[@]}"; do
    target="$CLAUDE_DIR/scripts/$script"
    if [[ -f "$target" ]]; then
        rm -f "$target"
        success "  ✓ 已移除：$script"
    fi
done

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║              卸载完成                        ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  如需重新安装，运行：bash install.sh"
echo ""

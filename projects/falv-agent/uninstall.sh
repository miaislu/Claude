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

SKILLS=(falv shencha fengxian hege qicao fanyi laodong gongsi baogao)

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

AGENTS=(tiao-kuan-fen-xi feng-xian-ping-gu he-gui-jian-cha yi-wu-jie-xi jian-yi-yin-qing _guidelines)

for agent in "${AGENTS[@]}"; do
    target="$CLAUDE_DIR/agents/$agent.md"
    if [[ -f "$target" ]]; then
        rm -f "$target"
        success "  ✓ 已移除 Agent：$agent"
    else
        warn "  - Agent 不存在（跳过）：$agent"
    fi
done

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║              卸载完成                        ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  如需重新安装，运行：bash install.sh"
echo ""

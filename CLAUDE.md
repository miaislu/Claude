# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## File Storage

All files generated during a session (documents, reports, scripts, analysis output, etc.) must be saved under `~/Claude/projects/`. Never write output files directly to the home directory or other locations.

New projects go to `~/Claude/projects/<project-name>/`.

## Git Sync

`~/Claude/` is a local git repo synced to `git@github.com:miaislu/Claude.git` (branch: `main`). A Stop hook in `~/.claude/settings.json` auto-commits and pushes at session end with message `auto-sync: <ISO timestamp>`. To record a meaningful commit message, commit manually before the session ends.

## Environment

- **Python**: managed via `pyenv` (`~/.pyenv`)
- **Node.js**: managed via `nvm` (`~/.nvm`)
- **Homebrew**: installed at `~/homebrew/bin` (non-standard prefix)
- **Claude Code alias**: `mcc` runs `mc --code --model catpaw-claude-opus-4.7`

## Active Projects

| Project | Path |
|---|---|
| `ceo-review-advisor` | `~/Claude/projects/ceo-review-advisor/` |
| `wbr-category-strategy-v3` | `~/Claude/projects/wbr-category-strategy-v3/` |

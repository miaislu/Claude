# Managed Agent Cookbooks

This directory contains **managed agent cookbook** configurations for the Chinese Law AI Agent system. These YAML definitions run on Anthropic's managed infrastructure via the Managed Agents API.

## What Are Managed Agent Cookbooks?

Managed agent cookbooks are declarative YAML files that define multi-agent pipelines using the `agent_toolset_20260401` tool type. They differ from Claude Code skills (`.claude/skills/`) in several key ways:

| Dimension | Skills (SKILL.md) | Managed Agent Cookbooks (agent.yaml) |
|---|---|---|
| Runtime | Claude Code local CLI | Anthropic managed cloud infrastructure |
| API key | Uses your local `ANTHROPIC_API_KEY` | Runs on Anthropic's own infra — no key needed |
| Invocation | `/skill-name` slash command in Claude Code | REST call to the Managed Agents API endpoint |
| Orchestration | Claude Code handles the loop | Declared in YAML; platform handles scheduling |
| Parallelism | Sequential by default | Native parallel fan-out via `callable_agents` |
| State | Local filesystem, `.claude/` directory | Managed session context, no local disk writes |

In short: skills are for local developer workflows; managed agent cookbooks are for production deployments where you want Anthropic to handle infrastructure, scaling, and agent lifecycle.

## Directory Structure

```
managed-agent-cookbooks/
└── contract-review/
    ├── agent.yaml                        # Orchestration agent (entry point)
    └── subagents/
        ├── clause-analyzer.yaml          # Phase 1: clause identification
        ├── risk-assessor.yaml            # Phase 2a: risk scoring
        ├── compliance-checker.yaml       # Phase 2b: Chinese law compliance
        ├── obligations-extractor.yaml    # Phase 2c: rights/obligations/deadlines
        └── amendment-writer.yaml         # Phase 3: modification suggestions
```

## Execution DAG

```
[Input Contract]
       │
       ▼
 clause-analyzer          ← Phase 1 (solo)
       │
       ├──────────────────────────────────┐
       ▼                  ▼               ▼
 risk-assessor   compliance-checker  obligations-extractor   ← Phase 2 (parallel)
       │                  │               │
       └──────────────────┴───────────────┘
                          │
                          ▼
                  amendment-writer      ← Phase 3 (solo)
                          │
                          ▼
               [Structured Review Report]
```

## How to Use

### Via Anthropic Managed Agents API

```bash
curl https://api.anthropic.com/v1/managed-agents/runs \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2026-04-01" \
  -H "content-type: application/json" \
  -d '{
    "agent": "contract-review",
    "input": {
      "contract_text": "<合同全文>",
      "party_perspective": "甲方（买方）",
      "contract_type": "买卖合同"
    }
  }'
```

### Deploying the Cookbook

Upload the cookbook directory to your Anthropic workspace:

```bash
anthropic agents deploy ./managed-agent-cookbooks/contract-review/
```

### Local Testing (with Claude Code)

The subagent YAML definitions are compatible with Claude Code's agent runner for local iteration:

```bash
claude agent run ./managed-agent-cookbooks/contract-review/agent.yaml \
  --input contract.txt
```

## Relationship to This Project's Skills

The `contract-review` cookbook mirrors the five-agent DAG already implemented as Claude Code agents under `.claude/agents/`. The cookbook version is the production-ready, infrastructure-managed equivalent intended for API integration, SaaS deployment, or embedding in external legal tech platforms.

For local development and iteration, continue using the skills-based workflow (`/legal review`). For production API deployments, use the cookbook.

# /legal — Chinese Law AI Agent

## Usage

```
/legal <subcommand> [args]
```

## Subcommand Routing

| Subcommand | Function | Example |
|---|---|---|
| `review` | Full contract review (flagship) | `/legal review contract.pdf` |
| `risk` | Risk clause scoring | `/legal risk agreement.txt` |
| `compliance` | Compliance check | `/legal compliance --type pipl` |
| `draft` | Legal document drafting | `/legal draft --type labor-contract` |
| `plain-language` | Legal terms in plain Chinese | `/legal plain-language clause.txt` |
| `labor` | Labor contract specialist review | `/legal labor contract.pdf` |
| `corporate` | Corporate law matters | `/legal corporate --type shareholders-agreement` |
| `report` | Export last review as Word/PDF | `/legal report --last` |
| `onboard` | Practice profile setup (run first) | `/legal onboard` |

## Routing Logic

When the user types a `/legal` command:

1. **Parse subcommand** — first argument is the subcommand name
2. **Route** — delegate to the corresponding skill (`skills/<subcommand>/SKILL.md`)
3. **No subcommand** — display routing table above and prompt user
4. **Unknown subcommand** — show available commands list, ask user intent

## Common Flags

- `--lang [zh|en]` — output language, default `zh`
- `--brief` — summary only, skip detailed analysis
- `--save <filename>` — save report as Markdown

## Notes

- All analysis defaults to **mainland China** law
- Hong Kong / overseas content: sub-skills auto-annotate applicable jurisdiction
- Every output must end with the standard disclaimer

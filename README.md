# ctxaudit

Audit the invisible context tax from agent skills, rules, and instruction files.

Every AI coding agent silently loads skills, rules, and instruction files into your context window. Most of this context is stale, duplicated, or irrelevant to what you're actually doing -- and it actively degrades agent performance. More context doesn't mean better results. Irrelevant instructions compete for attention, contradict each other, and push useful conversation history out of the window faster.

`ctxaudit` scans everything that gets loaded and shows you exactly what's eating your context -- so you can cut the noise.

## Install & Run

```bash
uvx ctxaudit
```

Or install permanently:

```bash
uv tool install ctxaudit
```

## What it scans

| Source | Platforms |
|---|---|
| **Skills** (`SKILL.md`) | Claude Code, Cursor, Codex, Cline, Amp, Windsurf, Gemini CLI, Copilot, Roo Code, and more |
| **Rules** (`.mdc`, `.md`) | Cursor, Claude Code, Roo Code, Windsurf, Cline |
| **Instruction files** | `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.cursorrules`, `.goosehints`, etc. |
| **Plugins** | Claude Code plugins (skills, agents, commands) |

Both **user-level** (`~/.claude/`, `~/.cursor/`, etc.) and **project-level** (`.cursor/rules/`, `AGENTS.md`, etc.) paths are scanned.

## Example output

```
CONTEXT AUDIT  (project: ~/work/my-project)
──────────────────────────────────────────────────────

User-Level

  Claude Code (2 skills, 53 plugin items)
    ~/.claude/skills                              95 startup     4,170 full
    15 plugin skills                           1,087 startup    41,730 full
    19 plugin agents                           1,515 startup    22,781 full
    19 plugin commands                           242 startup    16,370 full
  Cursor (12 skills)
    ~/.cursor/skills, ~/.cursor/skills-cursor    244 startup    10,653 full

──────────────────────────────────────────────────────

Project-Level

  Cursor (48 files)
    .cursor/rules/always/project-index.mdc    1,353 always
    .cursor/rules/features/auth.mdc               11 description (5,738 full)
    ...

──────────────────────────────────────────────────────

  Scannable context: ~18,244 tokens loaded every session
  System overhead:  ~15,000-30,000 tokens (agent system prompt, tools, built-in instructions)
  Effective total:  ~33,244-48,244 tokens before you type anything
  Context used:    17-24% of 200,000 token window
```

## What the columns mean

- **startup** — tokens loaded into every session (skill metadata, always-on rules)
- **full** — total tokens if the skill/rule is fully activated
- **always** — loaded every session unconditionally
- **description** — only the description is loaded at startup; the agent decides whether to load the full content
- **on-demand** — not loaded at startup; only loaded when triggered by file globs or explicit invocation

## Options

```bash
ctxaudit              # Scan user-level + current project
ctxaudit --user-only  # Scan user-level only (no project context)
```

## Loading behavior by file type

| File type | Startup cost | When fully loaded |
|---|---|---|
| Skill (`SKILL.md`) | Name + description | Agent decides to invoke it |
| Cursor rule (`alwaysApply: true`) | Full content | Always |
| Cursor rule (with `description`) | Description only | Agent decides it's relevant |
| Cursor rule (with `globs`) | Nothing | Matching file is open |
| Claude Code rule (no `paths`) | Full content | Always |
| Claude Code rule (with `paths`) | Nothing | Matching file is open |
| Instruction file (`CLAUDE.md`, etc.) | Full content | Always |

## License

MIT

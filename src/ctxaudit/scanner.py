from __future__ import annotations

import re
from pathlib import Path

import tiktoken
import yaml

from ctxaudit.types import ContextFile, ScanResult

_enc = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_enc.encode(text))


# ---------------------------------------------------------------------------
# Path registries
# ---------------------------------------------------------------------------

# Agent paths sourced from vercel-labs/skills (MIT) agents.ts
SKILL_DIRS: list[dict] = [
    # -- User-level (global) --
    # Agents using ~/.config/agents/skills (shared universal dir)
    {"path": "~/.config/agents/skills", "platform": "Amp", "scope": "user",
     "readers": ["Amp", "Kimi CLI", "Replit"]},
    # Agents using ~/.agents/skills (shared)
    {"path": "~/.agents/skills", "platform": "Cline", "scope": "user"},
    # Agent-specific global dirs
    {"path": "~/.adal/skills", "platform": "AdaL", "scope": "user"},
    {"path": "~/.augment/skills", "platform": "Augment", "scope": "user"},
    {"path": "~/.claude/skills", "platform": "Claude Code", "scope": "user",
     "readers": ["Claude Code", "Cursor"]},
    {"path": "~/.codebuddy/skills", "platform": "CodeBuddy", "scope": "user"},
    {"path": "~/.codeium/windsurf/skills", "platform": "Windsurf", "scope": "user"},
    {"path": "~/.codex/skills", "platform": "Codex", "scope": "user",
     "readers": ["Codex", "Cursor"]},
    {"path": "~/.commandcode/skills", "platform": "Command Code", "scope": "user"},
    {"path": "~/.config/crush/skills", "platform": "Crush", "scope": "user"},
    {"path": "~/.config/goose/skills", "platform": "Goose", "scope": "user"},
    {"path": "~/.config/opencode/skills", "platform": "OpenCode", "scope": "user"},
    {"path": "~/.continue/skills", "platform": "Continue", "scope": "user"},
    {"path": "~/.copilot/skills", "platform": "GitHub Copilot", "scope": "user"},
    {"path": "~/.cursor/skills", "platform": "Cursor", "scope": "user"},
    {"path": "~/.cursor/skills-cursor", "platform": "Cursor", "scope": "user"},
    {"path": "~/.factory/skills", "platform": "Droid", "scope": "user"},
    {"path": "~/.gemini/antigravity/skills", "platform": "Antigravity", "scope": "user"},
    {"path": "~/.gemini/skills", "platform": "Gemini CLI", "scope": "user"},
    {"path": "~/.iflow/skills", "platform": "iFlow CLI", "scope": "user"},
    {"path": "~/.junie/skills", "platform": "Junie", "scope": "user"},
    {"path": "~/.kilocode/skills", "platform": "Kilo Code", "scope": "user"},
    {"path": "~/.kiro/skills", "platform": "Kiro CLI", "scope": "user"},
    {"path": "~/.kode/skills", "platform": "Kode", "scope": "user"},
    {"path": "~/.mcpjam/skills", "platform": "MCPJam", "scope": "user"},
    {"path": "~/.mux/skills", "platform": "Mux", "scope": "user"},
    {"path": "~/.neovate/skills", "platform": "Neovate", "scope": "user"},
    {"path": "~/.openclaw/skills", "platform": "OpenClaw", "scope": "user"},
    {"path": "~/.openhands/skills", "platform": "OpenHands", "scope": "user"},
    {"path": "~/.pi/agent/skills", "platform": "Pi", "scope": "user"},
    {"path": "~/.pochi/skills", "platform": "Pochi", "scope": "user"},
    {"path": "~/.qoder/skills", "platform": "Qoder", "scope": "user"},
    {"path": "~/.qwen/skills", "platform": "Qwen Code", "scope": "user"},
    {"path": "~/.roo/skills", "platform": "Roo Code", "scope": "user"},
    {"path": "~/.snowflake/cortex/skills", "platform": "Cortex Code", "scope": "user"},
    {"path": "~/.trae/skills", "platform": "Trae", "scope": "user"},
    {"path": "~/.trae-cn/skills", "platform": "Trae CN", "scope": "user"},
    {"path": "~/.vibe/skills", "platform": "Mistral Vibe", "scope": "user"},
    {"path": "~/.zencoder/skills", "platform": "Zencoder", "scope": "user"},
    # -- Project-level --
    # Universal .agents/skills dir (shared by many agents)
    {
        "path": ".agents/skills",
        "platform": "Cross-Platform",
        "scope": "project",
        "readers": ["Amp", "Cline", "Codex", "Cursor", "Gemini CLI", "GitHub Copilot",
                     "Kimi CLI", "OpenCode", "Replit"],
    },
    # Agent-specific project dirs
    {"path": ".adal/skills", "platform": "AdaL", "scope": "project"},
    {"path": ".agent/skills", "platform": "Antigravity", "scope": "project"},
    {"path": ".augment/skills", "platform": "Augment", "scope": "project"},
    {"path": ".claude/skills", "platform": "Claude Code", "scope": "project"},
    {"path": ".codebuddy/skills", "platform": "CodeBuddy", "scope": "project"},
    {"path": ".commandcode/skills", "platform": "Command Code", "scope": "project"},
    {"path": ".continue/skills", "platform": "Continue", "scope": "project"},
    {"path": ".cortex/skills", "platform": "Cortex Code", "scope": "project"},
    {"path": ".crush/skills", "platform": "Crush", "scope": "project"},
    {"path": ".factory/skills", "platform": "Droid", "scope": "project"},
    {"path": ".goose/skills", "platform": "Goose", "scope": "project"},
    {"path": ".iflow/skills", "platform": "iFlow CLI", "scope": "project"},
    {"path": ".junie/skills", "platform": "Junie", "scope": "project"},
    {"path": ".kilocode/skills", "platform": "Kilo Code", "scope": "project"},
    {"path": ".kiro/skills", "platform": "Kiro CLI", "scope": "project"},
    {"path": ".kode/skills", "platform": "Kode", "scope": "project"},
    {"path": ".mcpjam/skills", "platform": "MCPJam", "scope": "project"},
    {"path": ".mux/skills", "platform": "Mux", "scope": "project"},
    {"path": ".neovate/skills", "platform": "Neovate", "scope": "project"},
    {"path": ".openhands/skills", "platform": "OpenHands", "scope": "project"},
    {"path": ".pi/skills", "platform": "Pi", "scope": "project"},
    {"path": ".pochi/skills", "platform": "Pochi", "scope": "project"},
    {"path": ".qoder/skills", "platform": "Qoder", "scope": "project"},
    {"path": ".qwen/skills", "platform": "Qwen Code", "scope": "project"},
    {"path": ".roo/skills", "platform": "Roo Code", "scope": "project"},
    {"path": ".trae/skills", "platform": "Trae", "scope": "project"},
    {"path": ".vibe/skills", "platform": "Mistral Vibe", "scope": "project"},
    {"path": ".windsurf/skills", "platform": "Windsurf", "scope": "project"},
    {"path": ".zencoder/skills", "platform": "Zencoder", "scope": "project"},
    {"path": "skills", "platform": "OpenClaw", "scope": "project"},
]

RULE_DIRS: list[dict] = [
    {"path": "~/.claude/rules", "platform": "Claude Code", "scope": "user", "style": "claude"},
    {"path": ".claude/rules", "platform": "Claude Code", "scope": "project", "style": "claude"},
    {"path": ".cursor/rules", "platform": "Cursor", "scope": "project", "style": "cursor"},
    {"path": ".roo/rules", "platform": "Roo Code", "scope": "project", "style": "always"},
    {"path": ".windsurf/rules", "platform": "Windsurf", "scope": "project", "style": "always"},
    {"path": ".clinerules", "platform": "Cline", "scope": "project", "style": "always"},
]

INSTRUCTION_FILES: list[dict] = [
    # User-level
    {"path": "~/.claude/CLAUDE.md", "platform": "Claude Code", "scope": "user", "readers": ["Claude Code"]},
    {"path": "~/.codex/AGENTS.md", "platform": "Codex", "scope": "user", "readers": ["Codex"]},
    # Project-level
    {
        "path": "AGENTS.md",
        "platform": "Cross-Platform",
        "scope": "project",
        "readers": ["Codex", "Cursor", "Amp", "Zed", "VS Code", "Copilot", "Junie", "Goose", "Aider", "Warp"],
    },
    {"path": "AGENTS.override.md", "platform": "Codex", "scope": "project", "readers": ["Codex"]},
    {
        "path": "CLAUDE.md",
        "platform": "Claude Code",
        "scope": "project",
        "readers": ["Claude Code", "Zed", "VS Code"],
    },
    {"path": ".claude/CLAUDE.md", "platform": "Claude Code", "scope": "project", "readers": ["Claude Code"]},
    {"path": "CLAUDE.local.md", "platform": "Claude Code", "scope": "project", "readers": ["Claude Code"]},
    {"path": "GEMINI.md", "platform": "Gemini CLI", "scope": "project", "readers": ["Gemini CLI", "Zed"]},
    {
        "path": ".github/copilot-instructions.md",
        "platform": "GitHub Copilot",
        "scope": "project",
        "readers": ["GitHub Copilot", "Zed"],
    },
    {"path": ".junie/guidelines.md", "platform": "Junie", "scope": "project", "readers": ["Junie"]},
    {
        "path": ".cursorrules",
        "platform": "Cursor",
        "scope": "project",
        "readers": ["Cursor (legacy)", "Zed"],
    },
    {
        "path": ".windsurfrules",
        "platform": "Windsurf",
        "scope": "project",
        "readers": ["Windsurf (legacy)", "Zed"],
    },
    {
        "path": ".clinerules",
        "platform": "Cline",
        "scope": "project",
        "readers": ["Cline (legacy)", "Zed"],
    },
    {"path": ".roorules", "platform": "Roo Code", "scope": "project", "readers": ["Roo Code (legacy)"]},
    {"path": ".goosehints", "platform": "Goose", "scope": "project", "readers": ["Goose"]},
]

LEGACY_COMMAND_DIRS: list[dict] = [
    {"path": ".claude/commands", "platform": "Claude Code", "scope": "project"},
]

PLUGIN_DIRS: list[dict] = [
    {"path": "~/.claude/plugins", "platform": "Claude Code", "scope": "user"},
]


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> dict:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}


# ---------------------------------------------------------------------------
# Skill scanning
# ---------------------------------------------------------------------------


def _scan_skill_dir(base: Path, platform: str, scope: str, readers: list[str] | None = None) -> list[ContextFile]:
    results = []
    if not base.is_dir():
        return results

    for skill_md in sorted(base.rglob("SKILL.md")):
        if not skill_md.is_file():
            continue
        child = skill_md.parent

        try:
            text = skill_md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        fm = _parse_frontmatter(text)
        name = fm.get("name") or child.name
        description = fm.get("description", "")
        disable_invocation = fm.get("disable-model-invocation", False)
        full_tokens = count_tokens(text)

        if disable_invocation:
            startup_tokens = 0
        else:
            metadata_text = f"{name}: {description}"
            startup_tokens = count_tokens(metadata_text)

        # include scripts/references token counts in full_tokens
        for subdir_name in ("scripts", "references", "assets"):
            subdir = child / subdir_name
            if subdir.is_dir():
                for f in subdir.rglob("*"):
                    if f.is_file():
                        try:
                            full_tokens += count_tokens(f.read_text(encoding="utf-8", errors="replace"))
                        except OSError:
                            pass

        results.append(
            ContextFile(
                path=child,
                platform=platform,
                scope=scope,
                kind="skill",
                startup_tokens=startup_tokens,
                full_tokens=full_tokens,
                readers=readers or [platform],
                name=name,
            )
        )

    return results


# ---------------------------------------------------------------------------
# Rule scanning
# ---------------------------------------------------------------------------


def _scan_rule_dir(entry: dict) -> list[ContextFile]:
    base = _resolve(entry["path"])
    if not base.exists():
        return []

    style = entry["style"]
    platform = entry["platform"]
    scope = entry["scope"]
    results = []

    # Single-file rule directory (e.g. .clinerules as a dir of .md files, or single file)
    if base.is_file():
        results.append(_make_rule_file(base, platform, scope, style))
        return results

    if not base.is_dir():
        return results

    for f in sorted(base.rglob("*.md")) + sorted(base.rglob("*.mdc")):
        if f.is_file():
            results.append(_make_rule_file(f, platform, scope, style))

    return results


def _make_rule_file(path: Path, platform: str, scope: str, style: str) -> ContextFile:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""

    full_tokens = count_tokens(text)
    fm = _parse_frontmatter(text)

    if style == "cursor":
        always_apply = fm.get("alwaysApply")
        has_globs = bool(fm.get("globs"))
        description = fm.get("description", "")

        if always_apply is True:
            startup_tokens = full_tokens
        elif has_globs:
            startup_tokens = 0
        elif description:
            startup_tokens = count_tokens(description)
        else:
            startup_tokens = full_tokens
    elif style == "claude":
        has_paths = bool(fm.get("paths") or fm.get("globs"))
        startup_tokens = 0 if has_paths else full_tokens
    else:
        startup_tokens = full_tokens

    return ContextFile(
        path=path,
        platform=platform,
        scope=scope,
        kind="rule",
        startup_tokens=startup_tokens,
        full_tokens=full_tokens,
        readers=[platform],
        name=path.name,
    )


# ---------------------------------------------------------------------------
# Instruction file scanning
# ---------------------------------------------------------------------------


def _scan_instruction_file(entry: dict) -> ContextFile | None:
    path = _resolve(entry["path"])
    if not path.is_file():
        return None

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    tokens = count_tokens(text)
    if tokens == 0:
        return None

    return ContextFile(
        path=path,
        platform=entry["platform"],
        scope=entry["scope"],
        kind="instructions",
        startup_tokens=tokens,
        full_tokens=tokens,
        readers=entry.get("readers", [entry["platform"]]),
        name=path.name,
    )


# ---------------------------------------------------------------------------
# Legacy command scanning
# ---------------------------------------------------------------------------


def _scan_legacy_commands(entry: dict) -> list[ContextFile]:
    base = _resolve(entry["path"])
    if not base.is_dir():
        return []

    results = []
    for f in sorted(base.rglob("*.md")):
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        tokens = count_tokens(text)
        results.append(
            ContextFile(
                path=f,
                platform=entry["platform"],
                scope=entry["scope"],
                kind="instructions",
                startup_tokens=tokens,
                full_tokens=tokens,
                readers=[entry["platform"]],
                name=f.stem,
            )
        )
    return results


# ---------------------------------------------------------------------------
# Claude Code plugin scanning
# ---------------------------------------------------------------------------


def _scan_plugins(base: Path, platform: str, scope: str) -> list[ContextFile]:
    """Scan Claude Code plugins for skills, agents, and commands."""
    results: list[ContextFile] = []
    if not base.is_dir():
        return results

    for skill_md in sorted(base.rglob("SKILL.md")):
        if not skill_md.is_file():
            continue
        child = skill_md.parent
        try:
            text = skill_md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        fm = _parse_frontmatter(text)
        name = fm.get("name") or child.name
        description = fm.get("description", "")
        full_tokens = count_tokens(text)
        metadata_text = f"{name}: {description}"
        startup_tokens = count_tokens(metadata_text)

        results.append(
            ContextFile(
                path=child,
                platform=platform,
                scope=scope,
                kind="plugin-skill",
                startup_tokens=startup_tokens,
                full_tokens=full_tokens,
                readers=[platform],
                name=name,
            )
        )

    for agent_md in sorted(base.rglob("agents/*.md")):
        if not agent_md.is_file():
            continue
        try:
            text = agent_md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        full_tokens = count_tokens(text)
        fm = _parse_frontmatter(text)
        description = fm.get("description", "")
        name = fm.get("name") or agent_md.stem

        metadata_text = f"{name}: {description}"
        startup_tokens = count_tokens(metadata_text)

        results.append(
            ContextFile(
                path=agent_md,
                platform=platform,
                scope=scope,
                kind="plugin-agent",
                startup_tokens=startup_tokens,
                full_tokens=full_tokens,
                readers=[platform],
                name=name,
            )
        )

    for cmd_md in sorted(base.rglob("commands/*.md")):
        if not cmd_md.is_file():
            continue
        try:
            text = cmd_md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        full_tokens = count_tokens(text)
        fm = _parse_frontmatter(text)
        name = fm.get("name") or cmd_md.stem
        description = fm.get("description", "")
        metadata_text = f"{name}: {description}" if description else name
        startup_tokens = count_tokens(metadata_text)

        results.append(
            ContextFile(
                path=cmd_md,
                platform=platform,
                scope=scope,
                kind="plugin-command",
                startup_tokens=startup_tokens,
                full_tokens=full_tokens,
                readers=[platform],
                name=name,
            )
        )

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve(path_str: str) -> Path:
    return Path(path_str).expanduser()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def scan(user_only: bool = False) -> ScanResult:
    result = ScanResult()
    project = Path.cwd()

    for entry in SKILL_DIRS:
        if entry["scope"] == "project" and user_only:
            continue

        if entry["scope"] == "project":
            base = project / entry["path"]
        else:
            base = _resolve(entry["path"])

        result.files.extend(
            _scan_skill_dir(
                base,
                platform=entry["platform"],
                scope=entry["scope"],
                readers=entry.get("readers"),
            )
        )

    for entry in RULE_DIRS:
        if entry["scope"] == "project" and user_only:
            continue
        if entry["scope"] == "project":
            entry = {**entry, "path": str(project / entry["path"])}
        result.files.extend(_scan_rule_dir(entry))

    for entry in INSTRUCTION_FILES:
        if entry["scope"] == "project" and user_only:
            continue
        if entry["scope"] == "project":
            entry = {**entry, "path": str(project / entry["path"])}
        cf = _scan_instruction_file(entry)
        if cf:
            result.files.append(cf)

    if not user_only:
        for entry in LEGACY_COMMAND_DIRS:
            entry_resolved = {**entry, "path": str(project / entry["path"])}
            result.files.extend(_scan_legacy_commands(entry_resolved))

    for entry in PLUGIN_DIRS:
        base = _resolve(entry["path"])
        result.files.extend(
            _scan_plugins(base, platform=entry["platform"], scope=entry["scope"])
        )

    return result

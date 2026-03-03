from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from rich.console import Console
from rich.table import Table

from ctxaudit.types import ContextFile, ScanResult

RECOMMENDED_SKILL_TOKENS = 5_000
CONTEXT_WINDOW = 200_000
SYSTEM_OVERHEAD_LOW = 15_000
SYSTEM_OVERHEAD_HIGH = 30_000


def _fmt_tokens(n: int) -> str:
    if n >= 1_000:
        return f"{n:,}"
    return str(n)


def _group_by_platform(files: list[ContextFile]) -> dict[str, list[ContextFile]]:
    groups: dict[str, list[ContextFile]] = defaultdict(list)
    for f in files:
        groups[f.platform].append(f)
    return dict(sorted(groups.items(), key=lambda x: (-_platform_sort_key(x[0]), x[0])))


def _platform_sort_key(platform: str) -> int:
    """Cross-Platform first, then alphabetical."""
    return 1 if platform == "Cross-Platform" else 0


def _render_scope_section(console: Console, title: str, files: list[ContextFile]) -> None:
    if not files:
        return

    console.print()
    console.print(f"  [bold]{title}[/bold]")
    console.print()

    groups = _group_by_platform(files)
    for platform, platform_files in groups.items():
        skills = [f for f in platform_files if f.kind == "skill"]
        plugin_skills = [f for f in platform_files if f.kind == "plugin-skill"]
        plugin_agents = [f for f in platform_files if f.kind == "plugin-agent"]
        plugin_commands = [f for f in platform_files if f.kind == "plugin-command"]
        non_skills = [f for f in platform_files if f.kind not in ("skill", "plugin-skill", "plugin-agent", "plugin-command")]

        parts = []
        if skills:
            parts.append(f"{len(skills)} skill{'s' if len(skills) != 1 else ''}")
        if plugin_skills or plugin_agents or plugin_commands:
            plugin_total = len(plugin_skills) + len(plugin_agents) + len(plugin_commands)
            parts.append(f"{plugin_total} plugin item{'s' if plugin_total != 1 else ''}")
        if non_skills:
            parts.append(f"{len(non_skills)} file{'s' if len(non_skills) != 1 else ''}")
        summary = ", ".join(parts)

        console.print(f"  [cyan]{platform}[/cyan] ({summary})")

        if skills:
            skill_startup = sum(s.startup_tokens for s in skills)
            skill_full = sum(s.full_tokens for s in skills)
            disabled = sum(1 for s in skills if s.startup_tokens == 0)

            location = _skill_group_location(skills)

            line = f"    {location:<42} {_fmt_tokens(skill_startup):>6} startup    {_fmt_tokens(skill_full):>6} full"
            if disabled:
                line += f"  ({disabled} disabled)"
            console.print(line)

        for group_name, group_files in [("plugin skills", plugin_skills), ("plugin agents", plugin_agents), ("plugin commands", plugin_commands)]:
            if group_files:
                group_startup = sum(f.startup_tokens for f in group_files)
                group_full = sum(f.full_tokens for f in group_files)
                label = f"{len(group_files)} {group_name}"
                line = f"    {label:<42} {_fmt_tokens(group_startup):>6} startup    {_fmt_tokens(group_full):>6} full"
                console.print(line)

        for f in non_skills:
            label = _loading_label(f)
            display = _short_path(f)
            line = f"    {display:<42} {_fmt_tokens(f.startup_tokens):>6} {label}"
            console.print(line)

            if len(f.readers) > 1:
                reader_str = ", ".join(f.readers)
                console.print(f"      [dim]→ {reader_str}[/dim]")


def _short_path(f: ContextFile) -> str:
    """Concise path: ~/... for user scope, relative for project scope."""
    if f.scope == "project":
        try:
            return str(f.path.relative_to(Path.cwd()))
        except ValueError:
            pass
    return f.display_path


def _skill_group_location(skills: list[ContextFile]) -> str:
    """Show the common parent directory for a group of skills."""
    parents = sorted({s.path.parent for s in skills})
    home = Path.home()

    def _short(p: Path) -> str:
        try:
            return "~/" + str(p.relative_to(home))
        except ValueError:
            try:
                return str(p.relative_to(Path.cwd()))
            except ValueError:
                return str(p)

    # Remove children when a parent already covers them
    deduped: list[Path] = []
    for p in parents:
        if not any(p != existing and _is_subpath(p, existing) for existing in parents):
            deduped.append(p)

    if len(deduped) == 1:
        return _short(deduped[0])
    return ", ".join(_short(p) for p in deduped)


def _is_subpath(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _loading_label(f: ContextFile) -> str:
    if f.is_always_loaded:
        return "always"
    if f.is_on_demand:
        return f"on-demand ({_fmt_tokens(f.full_tokens)} full)"
    return f"description ({_fmt_tokens(f.full_tokens)} full)"


def _render_largest(console: Console, result: ScanResult) -> None:
    skills = sorted(result.skills(), key=lambda s: s.full_tokens, reverse=True)[:5]
    if not skills:
        return

    console.print()
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("Skill")
    table.add_column("Location")
    table.add_column("Tokens", justify="right")
    table.add_column("")

    for s in skills:
        flag = "[red]!![/red]" if s.full_tokens > RECOMMENDED_SKILL_TOKENS else ""
        table.add_row(s.name or "?", s.display_path, _fmt_tokens(s.full_tokens), flag)

    console.print("  [bold]Largest Skills[/bold]")
    console.print(table)


def _render_duplicates(console: Console, result: ScanResult) -> None:
    dupes = result.duplicates()
    if not dupes:
        return

    console.print()
    console.print("  [bold]Duplicates[/bold]")
    for name, files in dupes.items():
        locations = ", ".join(f.display_path for f in files)
        console.print(f"    [yellow]{name}[/yellow] → {locations}")


def _render_suggestions(console: Console, result: ScanResult) -> None:
    suggestions = []

    oversized = [s for s in result.skills() if s.full_tokens > RECOMMENDED_SKILL_TOKENS]
    if oversized:
        suggestions.append(
            f"{len(oversized)} skill{'s' if len(oversized) != 1 else ''} "
            f"exceed{'s' if len(oversized) == 1 else ''} the {RECOMMENDED_SKILL_TOKENS:,}-token recommendation"
        )

    dupes = result.duplicates()
    if dupes:
        for name in dupes:
            suggestions.append(f'"{name}" duplicated across {len(dupes[name])} locations')

    disabled = [s for s in result.skills() if s.startup_tokens == 0]
    if disabled:
        suggestions.append(
            f"{len(disabled)} skill{'s' if len(disabled) != 1 else ''} "
            f"excluded from startup (disable-model-invocation)"
        )

    if not suggestions:
        return

    console.print()
    console.print("  [bold]Suggestions[/bold]")
    for s in suggestions:
        console.print(f"    [dim]•[/dim] {s}")


FIX_PROMPT = (
    "Run `uvx ctxaudit` and fix the issues it reports. "
    "Skills over 5,000 tokens should be refactored -- move detailed content into references/ or assets/ subdirectories. "
    "Remove duplicate skills after asking me which copy to keep."
)


def _render_fix_prompt(console: Console, result: ScanResult) -> None:
    oversized = [s for s in result.skills() if s.full_tokens > RECOMMENDED_SKILL_TOKENS]
    dupes = result.duplicates()
    if not oversized and not dupes:
        return

    console.print()
    console.print("  [bold]Fix Prompt[/bold] [dim](paste into your coding agent)[/dim]")
    console.print(f"  [italic]{FIX_PROMPT}[/italic]")


def render(result: ScanResult, user_only: bool = False) -> None:
    console = Console()

    if not result.files:
        console.print("\n  [dim]No context files found.[/dim]\n")
        return

    cwd = Path.cwd()
    home = Path.home()
    try:
        project_label = "~/" + str(cwd.relative_to(home))
    except ValueError:
        project_label = str(cwd)

    header = f"CONTEXT AUDIT  [dim](project: {project_label})[/dim]" if not user_only else "CONTEXT AUDIT  [dim](user-level only)[/dim]"
    console.print()
    console.print(f"  [bold]{header}[/bold]")
    console.print(f"  {'─' * 54}")

    user_files = result.by_scope("user")
    project_files = result.by_scope("project")

    _render_scope_section(console, "User-Level", user_files)

    if not user_only and project_files:
        console.print()
        console.print(f"  {'─' * 54}")
        _render_scope_section(console, "Project-Level", project_files)

    console.print()
    console.print(f"  {'─' * 54}")
    console.print()

    startup = result.total_startup_tokens
    pct = (startup / CONTEXT_WINDOW) * 100

    console.print(f"  [bold]Scannable context:[/bold] ~{_fmt_tokens(startup)} tokens loaded every session")

    effective_low = startup + SYSTEM_OVERHEAD_LOW
    effective_high = startup + SYSTEM_OVERHEAD_HIGH
    pct_low = (effective_low / CONTEXT_WINDOW) * 100
    pct_high = (effective_high / CONTEXT_WINDOW) * 100

    console.print(f"  [bold]System overhead:[/bold]  ~{_fmt_tokens(SYSTEM_OVERHEAD_LOW)}-{_fmt_tokens(SYSTEM_OVERHEAD_HIGH)} tokens [dim](agent system prompt, tools, built-in instructions)[/dim]")
    console.print(f"  [bold]Effective total:[/bold]  ~{_fmt_tokens(effective_low)}-{_fmt_tokens(effective_high)} tokens before you type anything")

    if pct_high < 10:
        pct_style = "green"
    elif pct_high < 25:
        pct_style = "yellow"
    else:
        pct_style = "red"
    console.print(f"  [bold]Context used:[/bold]    [{pct_style}]{pct_low:.0f}-{pct_high:.0f}%[/{pct_style}] of {_fmt_tokens(CONTEXT_WINDOW)} token window")

    console.print()
    console.print(f"  {'─' * 54}")

    _render_largest(console, result)
    _render_duplicates(console, result)
    _render_suggestions(console, result)
    _render_fix_prompt(console, result)

    console.print()

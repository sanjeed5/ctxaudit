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

FIX_PROMPT = (
    "Run `uvx ctxaudit` and fix the issues it reports. "
    "Skills over 5,000 tokens should be refactored -- move detailed content into references/ or assets/ subdirectories. "
    "Remove duplicate skills after asking me which copy to keep."
)


def _fmt_tokens(n: int) -> str:
    if n >= 1_000:
        return f"{n:,}"
    return str(n)


def _pct_style(pct_high: float) -> str:
    if pct_high < 10:
        return "green"
    if pct_high < 25:
        return "yellow"
    return "red"


def _project_label(user_only: bool) -> str:
    if user_only:
        return "user-level only"
    cwd = Path.cwd()
    try:
        return "~/" + str(cwd.relative_to(Path.home()))
    except ValueError:
        return str(cwd)


# ---------------------------------------------------------------------------
# Compact output (default)
# ---------------------------------------------------------------------------


def _render_compact(console: Console, result: ScanResult, user_only: bool) -> None:
    label = _project_label(user_only)
    console.print()
    console.print(f"  [bold]CONTEXT AUDIT[/bold]  [dim]({label})[/dim]")
    console.print(f"  {'─' * 54}")
    console.print()

    per_agent = result.per_agent_startup()
    if not per_agent:
        console.print("  [dim]No context files found.[/dim]")
        console.print()
        return

    for agent, tokens in per_agent.items():
        eff_low = tokens + SYSTEM_OVERHEAD_LOW
        eff_high = tokens + SYSTEM_OVERHEAD_HIGH
        pct_low = (eff_low / CONTEXT_WINDOW) * 100
        pct_high = (eff_high / CONTEXT_WINDOW) * 100
        style = _pct_style(pct_high)
        console.print(
            f"  {agent:<22} {_fmt_tokens(tokens):>6} tokens"
            f"    [{style}]{pct_low:.0f}-{pct_high:.0f}% of context[/{style}]"
        )

    # Collect issues
    issues: list[str] = []

    oversized = sorted(
        [s for s in result.skills() if s.full_tokens > RECOMMENDED_SKILL_TOKENS],
        key=lambda s: s.full_tokens,
        reverse=True,
    )
    if oversized:
        biggest = oversized[0]
        issues.append(
            f"{len(oversized)} skill{'s' if len(oversized) != 1 else ''} "
            f"exceed {RECOMMENDED_SKILL_TOKENS:,} tokens "
            f"(largest: {biggest.name} at {_fmt_tokens(biggest.full_tokens)})"
        )

    dupes = result.duplicates()
    for name, files in dupes.items():
        all_readers: list[set[str]] = [set(f.readers) for f in files]
        shared: set[str] = set()
        for i, r1 in enumerate(all_readers):
            for r2 in all_readers[i + 1:]:
                shared |= r1 & r2
        affected = ", ".join(sorted(shared))
        issues.append(f"{name} seen twice by {affected}")

    if issues:
        console.print()
        console.print(f"  {'─' * 54}")
        console.print()
        console.print("  [bold]Issues[/bold]")
        for issue in issues:
            console.print(f"    [yellow]!![/yellow] {issue}")

        console.print()
        console.print(f"  [dim]  Run [/dim][italic]ctxaudit -v[/italic][dim] for details. Paste the fix prompt into your agent:[/dim]")
        console.print(f"  [italic]{FIX_PROMPT}[/italic]")

    console.print()


# ---------------------------------------------------------------------------
# Verbose output (--verbose)
# ---------------------------------------------------------------------------


def _short_path(f: ContextFile) -> str:
    if f.scope == "project":
        try:
            return str(f.path.relative_to(Path.cwd()))
        except ValueError:
            pass
    return f.display_path


def _skill_group_location(skills: list[ContextFile]) -> str:
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


def _group_by_platform(files: list[ContextFile]) -> dict[str, list[ContextFile]]:
    groups: dict[str, list[ContextFile]] = defaultdict(list)
    for f in files:
        groups[f.platform].append(f)
    return dict(sorted(groups.items(), key=lambda x: (-(x[0] == "Cross-Platform"), x[0])))


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


def _render_verbose(console: Console, result: ScanResult, user_only: bool) -> None:
    label = _project_label(user_only)
    console.print()
    console.print(f"  [bold]CONTEXT AUDIT[/bold]  [dim]({label})[/dim]")
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

    # Per-agent totals
    per_agent = result.per_agent_startup()
    if per_agent:
        console.print("  [bold]Per-Agent Startup[/bold]")
        for agent, tokens in per_agent.items():
            eff_low = tokens + SYSTEM_OVERHEAD_LOW
            eff_high = tokens + SYSTEM_OVERHEAD_HIGH
            pct_low = (eff_low / CONTEXT_WINDOW) * 100
            pct_high = (eff_high / CONTEXT_WINDOW) * 100
            style = _pct_style(pct_high)
            console.print(
                f"    {agent:<22} {_fmt_tokens(tokens):>6} tokens"
                f"    [{style}]{pct_low:.0f}-{pct_high:.0f}%[/{style}] effective"
            )

    # Largest skills
    skills = sorted(result.skills(), key=lambda s: s.full_tokens, reverse=True)[:5]
    if skills:
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

    # Duplicates
    dupes = result.duplicates()
    if dupes:
        console.print()
        console.print("  [bold]Duplicates[/bold] [dim](same skill visible to the same agent)[/dim]")
        for name, files in dupes.items():
            all_readers: list[set[str]] = [set(f.readers) for f in files]
            shared: set[str] = set()
            for i, r1 in enumerate(all_readers):
                for r2 in all_readers[i + 1:]:
                    shared |= r1 & r2
            affected = ", ".join(sorted(shared))
            locations = ", ".join(f.display_path for f in files)
            console.print(f"    [yellow]{name}[/yellow] → {locations}")
            console.print(f"      [dim]seen twice by: {affected}[/dim]")

    # Suggestions
    suggestions = []
    oversized = [s for s in result.skills() if s.full_tokens > RECOMMENDED_SKILL_TOKENS]
    if oversized:
        suggestions.append(
            f"{len(oversized)} skill{'s' if len(oversized) != 1 else ''} "
            f"exceed{'s' if len(oversized) == 1 else ''} the {RECOMMENDED_SKILL_TOKENS:,}-token recommendation"
        )
    if dupes:
        for name in dupes:
            suggestions.append(f'"{name}" duplicated across {len(dupes[name])} locations')
    disabled = [s for s in result.skills() if s.startup_tokens == 0]
    if disabled:
        suggestions.append(
            f"{len(disabled)} skill{'s' if len(disabled) != 1 else ''} "
            f"excluded from startup (disable-model-invocation)"
        )
    if suggestions:
        console.print()
        console.print("  [bold]Suggestions[/bold]")
        for s in suggestions:
            console.print(f"    [dim]•[/dim] {s}")

    # Fix prompt
    if oversized or dupes:
        console.print()
        console.print("  [bold]Fix Prompt[/bold] [dim](paste into your coding agent)[/dim]")
        console.print(f"  [italic]{FIX_PROMPT}[/italic]")

    console.print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def render(result: ScanResult, user_only: bool = False, verbose: bool = False) -> None:
    console = Console()

    if not result.files:
        console.print("\n  [dim]No context files found.[/dim]\n")
        return

    if verbose:
        _render_verbose(console, result, user_only)
    else:
        _render_compact(console, result, user_only)

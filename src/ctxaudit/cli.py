from __future__ import annotations

import click

from ctxaudit.reporter import render
from ctxaudit.scanner import scan


@click.command()
@click.option("--user-only", is_flag=True, help="Only scan user-level paths, skip project context.")
def main(user_only: bool) -> None:
    """Audit the invisible context tax from agent skills, rules, and instruction files."""
    result = scan(user_only=user_only)
    render(result, user_only=user_only)

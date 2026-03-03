from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ContextFile:
    path: Path
    platform: str
    scope: str  # "user" or "project"
    kind: str  # "skill", "rule", "instructions"
    startup_tokens: int  # tokens loaded every session
    full_tokens: int  # total tokens if fully loaded/activated
    readers: list[str] = field(default_factory=list)
    name: str | None = None

    @property
    def is_on_demand(self) -> bool:
        return self.startup_tokens == 0

    @property
    def is_always_loaded(self) -> bool:
        return self.startup_tokens == self.full_tokens and self.startup_tokens > 0

    @property
    def display_path(self) -> str:
        """Show path relative to home or CWD for cleaner output."""
        home = Path.home()
        try:
            return "~/" + str(self.path.relative_to(home))
        except ValueError:
            try:
                return str(self.path.relative_to(Path.cwd()))
            except ValueError:
                return str(self.path)


@dataclass
class ScanResult:
    files: list[ContextFile] = field(default_factory=list)

    @property
    def total_startup_tokens(self) -> int:
        return sum(f.startup_tokens for f in self.files)

    @property
    def total_full_tokens(self) -> int:
        return sum(f.full_tokens for f in self.files)

    def by_scope(self, scope: str) -> list[ContextFile]:
        return [f for f in self.files if f.scope == scope]

    def by_platform(self, platform: str) -> list[ContextFile]:
        return [f for f in self.files if f.platform == platform]

    def skills(self) -> list[ContextFile]:
        return [f for f in self.files if f.kind in ("skill", "plugin-skill")]

    def duplicates(self) -> dict[str, list[ContextFile]]:
        """Find skills with the same name in different locations."""
        by_name: dict[str, list[ContextFile]] = {}
        for f in self.skills():
            if f.name:
                by_name.setdefault(f.name, []).append(f)
        return {name: files for name, files in by_name.items() if len(files) > 1}

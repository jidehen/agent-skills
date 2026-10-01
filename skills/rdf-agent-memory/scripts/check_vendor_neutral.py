#!/usr/bin/env python3
"""Check published text for runtime or product bindings."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ["".join(parts) for parts in (
    ("vir", "tuoso"), ("web", "dav"), ("open", "link"),
    ("cla", "ude"), ("anthro", "pic"), ("cod", "ex"),
    ("chat", "gpt"), ("g", "rok"), ("neo", "4j"),
)]
COMPARISON_ONLY = "".join(("open", "search"))
COMPARISON_FILE = Path("references/architecture-faq.md")
PUBLISHABLE = {".md", ".py", ".ttl", ".rq", ".toml", ".txt", ".jsonl"}
TECHNICAL_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache"}
PROJECT_DATA_DIRS = {"corpus", "renditions", "work", "memory"}


def publishable_files():
    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT)
        if not path.is_file() or relative.parts[0] in PROJECT_DATA_DIRS or any(
            part in TECHNICAL_DIRS or part.endswith(".egg-info") for part in relative.parts
        ):
            continue
        if path.suffix in PUBLISHABLE or path.name == ".gitignore":
            yield path


def forbidden_terms(relative: Path) -> list[str]:
    return FORBIDDEN if relative == COMPARISON_FILE else [*FORBIDDEN, COMPARISON_ONLY]


def main() -> int:
    failures = []
    scanned = 0
    for path in publishable_files():
        scanned += 1
        content = path.read_text(encoding="utf-8").casefold()
        relative = path.relative_to(ROOT)
        for term in forbidden_terms(relative):
            if term in content:
                failures.append(f"{relative}: forbidden runtime/product name")
    for failure in failures:
        print(failure, file=sys.stderr)
    if failures:
        return 1
    print(f"Portable publication scan passed ({scanned} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

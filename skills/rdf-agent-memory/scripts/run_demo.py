#!/usr/bin/env python3
"""Create a synthetic project and show accepted claims and reviewed conflict."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from memory_lib import ROOT, MemoryError, init, inventory, load, promote, stage, validate


def demonstrate(root: Path) -> dict:
    init(root)
    shutil.copy2(ROOT / "examples" / "demo-ontology.ttl", root / "memory" / "projects" / "demo-ontology.ttl")
    shutil.copytree(ROOT / "examples" / "source-documents", root / "corpus", dirs_exist_ok=True)
    manifest = inventory(root, batch_size=1)
    staged = stage(root, ROOT / "examples" / "candidates.jsonl")
    promote(root, staged[0], "demo-reviewer", "Source line and digest checked")
    promote(root, staged[1], "demo-reviewer", "Source line checked; owner disagreement remains unresolved", conflicts_with=[staged[0]], conflict_classification="unresolved", conflict_note="Both documents name a different owner for the same control on the same date")
    errors = validate(root)
    if errors:
        raise MemoryError("; ".join(errors))
    claims = list(load(root).query((ROOT / "queries" / "claims-with-evidence.rq").read_text(encoding="utf-8")))
    conflicts = list(load(root).query((ROOT / "queries" / "reviewed-conflicts.rq").read_text(encoding="utf-8")))
    return {"documents": manifest["document_count"], "staged": len(staged), "accepted_claims": len(claims), "reviewed_conflicts": len(conflicts), "memory_root": str(root / "memory")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="New project directory to retain; omit for a temporary demonstration")
    args = parser.parse_args()
    try:
        if args.output:
            print(json.dumps(demonstrate(args.output.resolve()), indent=2))
        else:
            with tempfile.TemporaryDirectory(prefix="rdf-memory-demo-") as directory:
                print(json.dumps(demonstrate(Path(directory)), indent=2))
        return 0
    except (MemoryError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

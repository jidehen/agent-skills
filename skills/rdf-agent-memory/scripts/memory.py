#!/usr/bin/env python3
"""Portable command line for project-local RDF memory."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from memory_lib import MEM, MemoryError, init, inventory, load, merged, promote, record_memory, register_rendition, stage, validate
from rdflib import RDF


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Project-local RDF memory and document ontology")
    subcommands = command.add_subparsers(dest="command", required=True)
    for name in ("init", "inventory", "register-rendition", "stage", "promote", "remember-rule", "record-session", "query", "validate", "status"):
        item = subcommands.add_parser(name)
        item.add_argument("--memory-root", type=Path, default=Path.cwd() / "memory", help="Project's canonical memory directory")
        item.add_argument("--corpus-root", type=Path, help="Source corpus directory; default is sibling corpus/")
        item.add_argument("--rendition-root", type=Path, help="UTF-8 rendition directory; default is sibling renditions/")
        if name == "inventory":
            item.add_argument("--batch-size", type=int, default=100)
        elif name == "register-rendition":
            item.add_argument("--source", required=True, help="Original corpus-relative source path")
            item.add_argument("--text", required=True, help="Rendition-relative UTF-8 text path")
            item.add_argument("--method", required=True)
            item.add_argument("--version", required=True)
        elif name == "stage":
            item.add_argument("candidate_file", type=Path, help="UTF-8 JSON Lines handoff")
        elif name == "promote":
            item.add_argument("claim_id")
            item.add_argument("--reviewer", required=True)
            item.add_argument("--rationale", required=True)
            item.add_argument("--conflicts-with", action="append", default=[], help="Accepted claim ID with reviewed contradictory meaning")
            item.add_argument("--conflict-classification", choices=("temporal", "scope", "definition", "unresolved"))
            item.add_argument("--conflict-note", help="Why the pair is a conflict")
            item.add_argument("--compatible-with", action="append", default=[], help="Accepted claim ID with a reviewed compatible difference")
            item.add_argument("--compatibility-note", help="Why values can coexist")
        elif name in ("remember-rule", "record-session"):
            item.add_argument("--id", required=True)
            item.add_argument("--text", required=True)
            item.add_argument("--recorded-by", required=True)
        elif name == "query":
            item.add_argument("query_file", type=Path, help="SPARQL .rq file")
            item.add_argument("--json", action="store_true", help="Emit JSON rows")
    return command


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    memory = args.memory_root.resolve()
    if memory.name != "memory":
        raise MemoryError("--memory-root must point to a directory named memory")
    root = memory.parent
    corpus = args.corpus_root.resolve() if args.corpus_root else root / "corpus"
    renditions = args.rendition_root.resolve() if args.rendition_root else root / "renditions"
    if args.command == "init":
        init(root)
        print(f"Initialized {memory}")
    elif args.command == "inventory":
        print(json.dumps(inventory(root, args.batch_size, corpus), indent=2))
    elif args.command == "register-rendition":
        print(json.dumps({"rendition": str(register_rendition(root, args.source, args.text, args.method, args.version, corpus, renditions))}, indent=2))
    elif args.command == "stage":
        print(json.dumps({"staged": stage(root, args.candidate_file, corpus, renditions)}, indent=2))
    elif args.command == "promote":
        print(json.dumps(promote(root, args.claim_id, args.reviewer, args.rationale, corpus, args.conflicts_with, args.conflict_classification, args.conflict_note, renditions, args.compatible_with, args.compatibility_note), indent=2))
    elif args.command in ("remember-rule", "record-session"):
        kind = "rule" if args.command == "remember-rule" else "session"
        print(json.dumps({"record": str(record_memory(root, kind, args.id, args.text, args.recorded_by))}, indent=2))
    elif args.command == "validate":
        errors = validate(root, corpus, renditions)
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print("Memory valid")
    elif args.command == "status":
        graph = merged(root)
        data = {
            "documents": len(set(graph.subjects(RDF.type, MEM.SourceDocument))),
            "accepted_claims": len(set(graph.subjects(RDF.type, MEM.Claim))),
            "staged_claims": len(list((root / "work" / "staging").glob("*.json"))),
            "reviewed_conflicts": len(set(graph.subjects(RDF.type, MEM.Conflict))),
        }
        print(json.dumps(data, indent=2))
    elif args.command == "query":
        sparql = args.query_file.read_text(encoding="utf-8")
        if re.search(r"\b(SERVICE|FROM|USING|LOAD|INSERT|DELETE|CLEAR|CREATE|DROP|MOVE|COPY|ADD)\b", sparql, re.IGNORECASE):
            raise MemoryError("Query file may only read local graphs; remote clauses and updates are disabled")
        without_comments = re.sub(r"(?m)^\s*#.*$", "", sparql)
        without_prefixes = re.sub(r"(?im)^\s*(PREFIX|BASE)\s+[^\n]+", "", without_comments)
        if not re.match(r"^\s*SELECT\b", without_prefixes, re.IGNORECASE):
            raise MemoryError("Only local SELECT queries are allowed")
        result = load(root).query(sparql)
        if result.type != "SELECT":
            raise MemoryError("Only SELECT queries are supported by this command")
        names = [str(name) for name in result.vars]
        rows = [{name: str(value) if value is not None else None for name, value in zip(names, row)} for row in result]
        if args.json:
            print(json.dumps(rows, indent=2))
        else:
            print("\t".join(names))
            for row in rows:
                print("\t".join(row[name] or "" for name in names))
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return run(argv)
    except (MemoryError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

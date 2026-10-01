#!/usr/bin/env python3
"""Bounded synthetic throughput probe; reports observations, not capacity claims."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

from rdflib import Graph, RDF, RDFS, Literal, URIRef

from memory_lib import MemoryError, init, inventory, load, promote, stage, validate, write_graph, write_text_atomic


def peak_memory_bytes() -> int | None:
    try:
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return peak if sys.platform == "darwin" else peak * 1024
    except (ImportError, AttributeError):
        return None


def run(root: Path, document_count: int, bytes_per_document: int, batch_size: int) -> dict:
    if document_count < 1 or bytes_per_document < 80 or batch_size < 1:
        raise MemoryError("Require positive documents/batch size and at least 80 bytes per document")
    init(root)
    extension = Graph()
    extension.add((URIRef("urn:benchmark:status"), RDF.type, RDF.Property))
    extension.add((URIRef("urn:benchmark:status"), RDFS.label, Literal("Status")))
    write_graph(root / "memory" / "projects" / "benchmark-ontology.ttl", extension)
    corpus = root / "corpus" / "docs"
    corpus.mkdir()
    for number in range(document_count):
        statement = f"Document {number:06d} says status active.\n"
        text = statement + "x" * max(0, bytes_per_document - len(statement.encode()))
        (corpus / f"d{number:06d}.txt").write_text(text, encoding="utf-8")
    t0 = time.perf_counter()
    manifest = inventory(root, batch_size=batch_size)
    inventory_seconds = time.perf_counter() - t0
    row = {
        "claim_id": "sample-status", "ontology_version": "1.0.0", "subject": "urn:benchmark:document:0",
        "predicate": "urn:benchmark:status", "object": {"literal": "active"},
        "source": "docs/d000000.txt", "locator": "line:1",
        "quote": "Document 000000 says status active.",
        "entities": [{"iri": "urn:benchmark:document:0", "label": "Document 0"}],
    }
    handoff = root / "work" / "sample.jsonl"
    write_text_atomic(handoff, json.dumps(row) + "\n")
    t0 = time.perf_counter()
    stage(root, handoff)
    promote(root, "sample-status", "benchmark-reviewer", "Synthetic source line checked")
    promotion_seconds = time.perf_counter() - t0
    t0 = time.perf_counter()
    errors = validate(root)
    validation_seconds = time.perf_counter() - t0
    if errors:
        raise MemoryError("; ".join(errors))
    t0 = time.perf_counter()
    result = list(load(root).query("PREFIX mem: <urn:agent-memory:> SELECT (COUNT(?claim) AS ?count) WHERE { ?claim a mem:Claim ; mem:verificationStatus mem:Verified . }"))
    query_seconds = time.perf_counter() - t0
    return {
        "documents": manifest["document_count"],
        "bytes_per_document": bytes_per_document,
        "batches": len(manifest["batches"]),
        "accepted_claims": int(result[0][0]),
        "inventory_seconds": round(inventory_seconds, 3),
        "stage_and_promote_seconds": round(promotion_seconds, 3),
        "validation_seconds": round(validation_seconds, 3),
        "query_seconds": round(query_seconds, 3),
        "peak_process_memory_bytes": peak_memory_bytes(),
        "memory_root": str(root / "memory"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--documents", type=int, default=50)
    parser.add_argument("--bytes-per-document", type=int, default=512)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--output", type=Path, help="Retain the synthetic project here")
    args = parser.parse_args()
    try:
        if args.output:
            print(json.dumps(run(args.output.resolve(), args.documents, args.bytes_per_document, args.batch_size), indent=2))
        else:
            with tempfile.TemporaryDirectory(prefix="rdf-memory-smoke-") as directory:
                print(json.dumps(run(Path(directory), args.documents, args.bytes_per_document, args.batch_size), indent=2))
        return 0
    except (MemoryError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

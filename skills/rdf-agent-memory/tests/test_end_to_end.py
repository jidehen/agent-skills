from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from rdflib import Graph, Literal, RDF, RDFS


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from memory_lib import (  # noqa: E402
    MEM, MemoryError, claim_iri, digest, document_iri, init, inventory, load,
    merged, promote, record_memory, register_rendition, stage, validate, write_graph,
)
from check_vendor_neutral import COMPARISON_ONLY, forbidden_terms, publishable_files  # noqa: E402


def command(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "memory.py"), *args], cwd=cwd or ROOT, text=True, capture_output=True)


def make_project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    init(root)
    shutil.copy2(ROOT / "examples" / "demo-ontology.ttl", root / "memory" / "projects" / "demo-ontology.ttl")
    return root


def candidate(claim_id: str, source: str, quote: str, obj: dict, **extra) -> dict:
    value = {
        "claim_id": claim_id, "ontology_version": "1.0.0", "subject": "urn:demo:control:17",
        "predicate": "urn:demo:status", "object": obj,
        "source": source, "locator": "line:1", "quote": quote,
        "entities": [{"iri": "urn:demo:control:17", "label": "Control 17"}],
    }
    value.update(extra)
    return value


def stage_row(root: Path, tmp_path: Path, row: dict) -> None:
    handoff = tmp_path / f"{row['claim_id']}.jsonl"
    handoff.write_text(json.dumps(row) + "\n", encoding="utf-8")
    stage(root, handoff)


def test_full_demo_and_staging_exclusion(tmp_path: Path) -> None:
    root = tmp_path / "poc"
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_demo.py"), "--output", str(root)], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["reviewed_conflicts"] == 1
    assert validate(root) == []
    query = command("query", str(ROOT / "queries" / "claims-with-evidence.rq"), "--memory-root", str(root / "memory"), "--json")
    assert query.returncode == 0, query.stderr
    rows = json.loads(query.stdout)
    assert len(rows) == 2
    assert {row["sourcePath"] for row in rows} == {"northstar/a.md", "northstar/b.md"}
    assert all(row["locator"] == "line:2" for row in rows)
    for row in rows:
        source_sha = digest(root / "corpus" / row["sourcePath"])
        assert row["source"] == str(document_iri(row["sourcePath"], source_sha))
        assert row["sourceSha"] == source_sha
        assert row["rendition"].startswith("urn:agent-memory:rendition:")
        assert row["renditionSha"] == source_sha
    staged_only = candidate("unreviewed", "northstar/a.md", "On 2026-01-15, the Atlas team owns Control 17.", {"literal": "draft"}, locator="line:2")
    stage_row(root, tmp_path, staged_only)
    query_again = command("query", str(ROOT / "queries" / "claims-with-evidence.rq"), "--memory-root", str(root / "memory"), "--json")
    assert len(json.loads(query_again.stdout)) == 2
    conflicts = list(load(root).query((ROOT / "queries" / "reviewed-conflicts.rq").read_text(encoding="utf-8")))
    assert len(conflicts) == 1
    assert str(conflicts[0].classification) == "unresolved"


def test_memory_rule_session_and_retrieval(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    rule = record_memory(root, "rule", "release-review", "Every release needs a reviewer.", "project-owner")
    record_memory(root, "session", "first-review", "Recorded release review policy.", "project-owner")
    assert rule in set(merged(root).objects(MEM.catalog, RDFS.seeAlso))
    assert validate(root) == []
    rows = list(load(root).query((ROOT / "queries" / "standing-memory.rq").read_text(encoding="utf-8")))
    assert len(rows) == 2
    assert any("Every release needs a reviewer" in str(row.text) for row in rows)


def test_cli_runs_from_an_unrelated_project_directory(tmp_path: Path) -> None:
    project = tmp_path / "separate-project"
    memory = project / "memory"
    created = command("init", "--memory-root", str(memory), cwd=tmp_path)
    assert created.returncode == 0, created.stderr
    remembered = command(
        "remember-rule", "--memory-root", str(memory), "--id", "review-every-release",
        "--text", "Every release needs a reviewer.", "--recorded-by", "project-owner", cwd=tmp_path,
    )
    assert remembered.returncode == 0, remembered.stderr
    queried = command("query", str(ROOT / "queries" / "standing-memory.rq"), "--memory-root", str(memory), "--json", cwd=tmp_path)
    assert queried.returncode == 0, queried.stderr
    assert len(json.loads(queried.stdout)) == 1
    assert command("validate", "--memory-root", str(memory), cwd=tmp_path).returncode == 0
    for name in ("corpus", "renditions", "work"):
        assert (project / name / ".gitignore").is_file()


def test_binary_source_rendition_chain_and_drift(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    (root / "corpus" / "report.pdf").write_bytes(b"%PDF synthetic demonstration bytes")
    inventory(root)
    (root / "renditions" / "report.txt").write_text("Control 17 is active.\n", encoding="utf-8")
    rendition = register_rendition(root, "report.pdf", "report.txt", "approved-text-extractor", "2")
    row = candidate("from-binary", "report.pdf", "Control 17 is active.", {"literal": "active", "lang": "en"}, rendition="report.txt")
    stage_row(root, tmp_path, row)
    promote(root, "from-binary", "reviewer-1", "Checked original digest and text rendition")
    assert validate(root) == []
    graph = merged(root)
    assert (rendition, MEM.extractionVersion, Literal("2")) in graph
    (root / "renditions" / "report.txt").write_text("Control 17 is retired.\n", encoding="utf-8")
    assert any("Text rendition changed" in error or "Quote does not match" in error for error in validate(root))


def test_invalid_quote_cannot_promote_and_no_partial_claim(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    (root / "corpus" / "a.txt").write_text("Control 17 is active.\n", encoding="utf-8")
    inventory(root)
    stage_row(root, tmp_path, candidate("bad-quote", "a.txt", "Control 17 is retired.", {"literal": "retired"}))
    with pytest.raises(MemoryError, match="Quote does not match"):
        promote(root, "bad-quote", "reviewer-1", "Checked evidence")
    assert (claim_iri("bad-quote"), RDF.type, MEM.Claim) not in merged(root)
    assert not (root / "memory" / "entities" / "bad-quote.ttl").exists()


def test_inventory_batches_replace_stale_and_version_sources(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    for number in range(3):
        (root / "corpus" / f"d{number}.txt").write_text(f"Document {number}\n", encoding="utf-8")
    assert inventory(root, batch_size=1)["batches"] == ["batch-00001", "batch-00002", "batch-00003"]
    original = document_iri("d0.txt", digest(root / "corpus" / "d0.txt"))
    (root / "corpus" / "d0.txt").write_text("Revised document\n", encoding="utf-8")
    assert inventory(root, batch_size=2)["batches"] == ["batch-00001", "batch-00002"]
    assert not (root / "work" / "queue" / "batch-00003.json").exists()
    graph = merged(root)
    assert (original, RDF.type, MEM.SourceDocument) in graph
    assert (document_iri("d0.txt", digest(root / "corpus" / "d0.txt")), RDF.type, MEM.SourceDocument) in graph


@pytest.mark.parametrize("sparql", [
    "SELECT * WHERE { SERVICE <https://example.invalid/sparql> { ?s ?p ?o } }",
    "SELECT * FROM <https://example.invalid/data> WHERE { ?s ?p ?o }",
    "ASK { ?s ?p ?o }",
    "DELETE WHERE { ?s ?p ?o }",
])
def test_query_rejects_remote_or_mutating_forms_before_loading(tmp_path: Path, sparql: str) -> None:
    query = tmp_path / "unsafe.rq"
    query.write_text(sparql, encoding="utf-8")
    result = command("query", str(query), "--memory-root", str(tmp_path / "missing" / "memory"))
    assert result.returncode == 2
    assert "disabled" in result.stderr or "Only local SELECT" in result.stderr
    assert "Run init first" not in result.stderr


def test_cardinality_and_index_target_gate(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    (root / "corpus" / "a.txt").write_text("Control 17 is active.\n", encoding="utf-8")
    inventory(root)
    stage_row(root, tmp_path, candidate("active", "a.txt", "Control 17 is active.", {"literal": "active"}))
    promote(root, "active", "reviewer-1", "Checked source")
    index_path = root / "memory" / "index.ttl"
    graph = Graph().parse(index_path, format="turtle")
    graph.add((claim_iri("active"), MEM.storedAt, Literal("entities/missing.ttl")))
    write_graph(index_path, graph)
    assert any("Expected exactly one" in error for error in validate(root))


def test_every_differing_value_needs_reviewed_disposition(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    (root / "corpus" / "a.txt").write_text("Control 17 is active.\n", encoding="utf-8")
    (root / "corpus" / "b.txt").write_text("Control 17 is under review.\n", encoding="utf-8")
    inventory(root)
    stage_row(root, tmp_path, candidate("active", "a.txt", "Control 17 is active.", {"literal": "active"}))
    stage_row(root, tmp_path, candidate("under-review", "b.txt", "Control 17 is under review.", {"literal": "under review"}))
    promote(root, "active", "reviewer-1", "Checked source")
    with pytest.raises(MemoryError, match="explicit conflict or compatibility"):
        promote(root, "under-review", "reviewer-1", "Checked source")
    result = promote(root, "under-review", "reviewer-1", "Checked source", compatible_with=["active"], compatibility_note="Active overall; under review is a parallel workflow state")
    assert len(result["compatibilities"]) == 1
    assert result["conflicts"] == []
    assert validate(root) == []


def test_staging_private_and_malformed_turtle_gates(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    (root / "memory" / "staging").mkdir()
    (root / "memory" / "staging" / "untrusted.ttl").write_text('<urn:demo:staged> <urn:demo:status> "untrusted" .\n', encoding="utf-8")
    (root / "memory" / "private" / "overlay.ttl").write_text('<urn:demo:private> <urn:demo:status> "private" .\n', encoding="utf-8")
    (root / "memory" / "preferences.private.ttl").write_text('<urn:demo:private> <urn:demo:status> "private-root" .\n', encoding="utf-8")
    graph = merged(root)
    assert not list(graph.triples((None, None, Literal("untrusted"))))
    assert not list(graph.triples((None, None, Literal("private"))))
    assert not list(graph.triples((None, None, Literal("private-root"))))
    named_graphs = {str(context.identifier) for context in load(root).graphs() if str(context.identifier) != "urn:x-rdflib:default"}
    assert named_graphs
    assert all(identifier.startswith("urn:agent-memory:graph:") for identifier in named_graphs)
    broken = root / "memory" / "projects" / "broken.ttl"
    broken.write_text("this is not Turtle @@@", encoding="utf-8")
    assert any("Turtle parse error" in error for error in validate(root))


def test_source_drift_and_ontology_version_are_detected(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    source = root / "corpus" / "a.txt"
    source.write_text("Control 17 is active.\n", encoding="utf-8")
    inventory(root)
    stage_row(root, tmp_path, candidate("active", "a.txt", "Control 17 is active.", {"literal": "active"}))
    promote(root, "active", "reviewer-1", "Checked source")
    source.write_text("Control 17 is retired.\n", encoding="utf-8")
    assert any("Original source changed" in error for error in validate(root))
    with pytest.raises(MemoryError, match="restore it"):
        inventory(root)
    source.write_text("Control 17 is active.\n", encoding="utf-8")
    ontology = root / "memory" / "ontology.ttl"
    ontology.write_text(ontology.read_text(encoding="utf-8").replace('mem:version "1.0.0"', 'mem:version "1.1.0"'), encoding="utf-8")
    assert any("ontology version mismatch" in error for error in validate(root))


def test_predicate_must_be_declared(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    (root / "corpus" / "a.txt").write_text("Control 17 is active.\n", encoding="utf-8")
    inventory(root)
    row = candidate("invalid-predicate", "a.txt", "Control 17 is active.", {"literal": "active"})
    row["predicate"] = "urn:demo:undeclared"
    handoff = tmp_path / "invalid.jsonl"
    handoff.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(MemoryError, match="not declared"):
        stage(root, handoff)


def test_memory_vocabulary_must_declare_emitted_terms(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    rogue = root / "memory" / "projects" / "rogue.ttl"
    rogue.write_text("<urn:demo:thing> a <urn:agent-memory:UndeclaredClass> ; <urn:agent-memory:undeclaredProperty> \"x\" .\n", encoding="utf-8")
    errors = validate(root)
    assert any("Undeclared memory class" in error for error in errors)
    assert any("Undeclared memory predicate" in error for error in errors)


def test_unreviewed_identity_equivalence_is_rejected(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    identity = root / "memory" / "projects" / "identity.ttl"
    identity.write_text("<urn:demo:team:alpha> <http://www.w3.org/2002/07/owl#sameAs> <urn:demo:team:beta> .\n", encoding="utf-8")
    assert any("Identity equivalence requires" in error for error in validate(root))


def test_portable_core_scan() -> None:
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_vendor_neutral.py")], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert ROOT / "assets" / "memory" / "ontology.ttl" in set(publishable_files())
    assert COMPARISON_ONLY in forbidden_terms(Path("SKILL.md"))
    assert COMPARISON_ONLY not in forbidden_terms(Path("references/architecture-faq.md"))


def test_bounded_smoke_benchmark(tmp_path: Path) -> None:
    result = subprocess.run([
        sys.executable, str(ROOT / "scripts" / "benchmark_smoke.py"),
        "--documents", "4", "--bytes-per-document", "100", "--batch-size", "2",
    ], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["documents"] == 4
    assert data["batches"] == 2
    assert data["accepted_claims"] == 1

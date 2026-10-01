"""Filesystem-canonical RDF memory primitives. No network or server required."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from rdflib import Dataset, Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import OWL, PROV, XSD


MEM = Namespace("urn:agent-memory:")
ROOT = Path(__file__).resolve().parents[1]
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,79}$")
LOCATOR_PATTERN = re.compile(r"^line:([1-9][0-9]*)$")
BOOTSTRAP = ("core.ttl", "preferences.ttl", "ontology.ttl", "index.ttl")


class MemoryError(ValueError):
    """A user-correctable memory or evidence error."""


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def document_iri(relative: str, sha: str) -> URIRef:
    identity = f"{relative}\n{sha}"
    return URIRef(f"urn:agent-memory:document:{hashlib.sha256(identity.encode()).hexdigest()[:24]}")


def claim_iri(claim_id: str) -> URIRef:
    return URIRef(f"urn:agent-memory:claim:{claim_id}")


def evidence_iri(claim_id: str) -> URIRef:
    return URIRef(f"urn:agent-memory:evidence:{claim_id}")


def review_iri(claim_id: str) -> URIRef:
    return URIRef(f"urn:agent-memory:review:{claim_id}")


def rendition_iri(source: URIRef, relative: str, sha: str) -> URIRef:
    key = f"{source}\n{relative}\n{sha}"
    return URIRef(f"urn:agent-memory:rendition:{hashlib.sha256(key.encode()).hexdigest()[:24]}")


def init(root: Path) -> None:
    memory = root / "memory"
    if memory.exists():
        raise MemoryError(f"Memory already exists: {memory}")
    root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "assets" / "memory", memory)
    for name in ("entities", "projects", "sessions", "provenance", "private", "howto"):
        (memory / name).mkdir()
    (root / "corpus").mkdir(exist_ok=True)
    (root / "renditions").mkdir(exist_ok=True)
    (root / "work" / "queue").mkdir(parents=True, exist_ok=True)
    (root / "work" / "staging").mkdir(parents=True, exist_ok=True)
    write_text_atomic(memory / ".gitignore", "preferences.private.ttl\nprivate/\n")
    for private_dir in (memory / "private", root / "corpus", root / "renditions", root / "work"):
        write_text_atomic(private_dir / ".gitignore", "*\n!.gitignore\n")


def ontology_version(graph: Graph) -> str:
    versions = list(graph.objects(MEM.ontology, MEM.version))
    if len(versions) != 1 or not str(versions[0]).strip():
        raise MemoryError("Ontology must declare exactly one nonempty mem:version")
    return str(versions[0])


def canonical_files(root: Path) -> list[Path]:
    memory = root / "memory"
    if not memory.is_dir():
        raise MemoryError(f"Run init first: {memory} is missing")
    files = []
    for path in sorted(memory.rglob("*.ttl")):
        relative = path.relative_to(memory)
        if path.name != "preferences.private.ttl" and not ({"staging", "private"} & set(relative.parts)):
            files.append(path)
    return files


def load(root: Path) -> Dataset:
    dataset = Dataset(default_union=True)
    for path in canonical_files(root):
        relative = path.relative_to(root / "memory").as_posix()
        graph_iri = URIRef("urn:agent-memory:graph:" + quote(relative, safe="/"))
        dataset.graph(graph_iri).parse(path, format="turtle", publicID="urn:agent-memory:base:")
    return dataset


def merged(root: Path) -> Graph:
    graph = Graph()
    for path in canonical_files(root):
        graph.parse(path, format="turtle", publicID="urn:agent-memory:base:")
    return graph


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    temporary.replace(path)


def write_graph(path: Path, graph: Graph) -> None:
    data = graph.serialize(format="turtle")
    checked = Graph()
    checked.parse(data=data, format="turtle", publicID="urn:agent-memory:base:")
    write_text_atomic(path, data)


def commit_graphs(graphs: dict[Path, Graph]) -> None:
    """Prepare every Turtle file, then restore prior bytes if a write fails."""
    prepared = {}
    before = {}
    for path, graph in graphs.items():
        data = graph.serialize(format="turtle")
        Graph().parse(data=data, format="turtle", publicID="urn:agent-memory:base:")
        prepared[path] = data
        before[path] = path.read_bytes() if path.exists() else None
    written = []
    try:
        for path, data in prepared.items():
            write_text_atomic(path, data)
            written.append(path)
    except Exception:
        for path in reversed(written):
            previous = before[path]
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                write_text_atomic(path, previous.decode("utf-8"))
        raise


def corpus_file(root: Path, relative: str, corpus_root: Path | None = None) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise MemoryError("Source must be a nonempty corpus-relative POSIX path")
    base = (corpus_root or root / "corpus").resolve()
    target = (base / relative).resolve()
    if not target.is_relative_to(base) or not target.is_file() or target.is_symlink():
        raise MemoryError(f"Unsafe or missing corpus source: {relative}")
    return target


def rendition_file(root: Path, relative: str, rendition_root: Path | None = None) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise MemoryError("Rendition must be a nonempty relative POSIX path")
    base = (rendition_root or root / "renditions").resolve()
    target = (base / relative).resolve()
    if not target.is_relative_to(base) or not target.is_file() or target.is_symlink():
        raise MemoryError(f"Unsafe or missing text rendition: {relative}")
    try:
        with target.open("r", encoding="utf-8") as stream:
            for _ in stream:
                pass
    except UnicodeDecodeError as exc:
        raise MemoryError("Rendition must be UTF-8 text") from exc
    return target


def rendition_record(root: Path, source: URIRef, relative: str, path: Path, method: str, version: str, area: str) -> URIRef:
    sha = digest(path)
    rendition = rendition_iri(source, relative, sha)
    graph = Graph()
    for triple in (
        (rendition, RDF.type, MEM.TextRendition),
        (rendition, MEM.forSource, source),
        (rendition, MEM.relativePath, Literal(relative)),
        (rendition, MEM.sha256, Literal(sha)),
        (rendition, MEM.storageArea, Literal(area)),
        (rendition, MEM.extractionMethod, Literal(method)),
        (rendition, MEM.extractionVersion, Literal(version)),
    ):
        graph.add(triple)
    target = root / "memory" / "provenance" / "renditions" / (str(rendition).rsplit(":", 1)[-1] + ".ttl")
    if not target.exists():
        write_graph(target, graph)
    return rendition


def register_rendition(
    root: Path, source_relative: str, rendition_relative: str,
    method: str, version: str, corpus_root: Path | None = None,
    rendition_root: Path | None = None,
) -> URIRef:
    if not method.strip() or not version.strip():
        raise MemoryError("Extraction method and version are required")
    source_path = corpus_file(root, source_relative, corpus_root)
    source = document_iri(source_relative, digest(source_path))
    graph = merged(root)
    if (source, RDF.type, MEM.SourceDocument) not in graph:
        raise MemoryError("Inventory the original source before registering a rendition")
    rendition_path = rendition_file(root, rendition_relative, rendition_root)
    rendition = rendition_iri(source, rendition_relative, digest(rendition_path))
    if (rendition, RDF.type, MEM.TextRendition) in graph:
        if graph.value(rendition, MEM.extractionMethod) != Literal(method) or graph.value(rendition, MEM.extractionVersion) != Literal(version):
            raise MemoryError("Rendition content was already registered with different extraction metadata")
        return rendition
    return rendition_record(root, source, rendition_relative, rendition_path, method, version, "renditions")


def inventory(root: Path, batch_size: int = 100, corpus_root: Path | None = None) -> dict:
    if batch_size < 1:
        raise MemoryError("Batch size must be positive")
    canonical_files(root)
    existing = merged(root)
    version = ontology_version(existing)
    claimed_sources: dict[str, set[str]] = {}
    for accepted_claim in existing.subjects(RDF.type, MEM.Claim):
        prior_source = existing.value(accepted_claim, PROV.wasDerivedFrom)
        if prior_source is None:
            continue
        prior_relative = existing.value(prior_source, MEM.relativePath)
        prior_sha = existing.value(prior_source, MEM.sha256)
        if prior_relative is not None and prior_sha is not None:
            claimed_sources.setdefault(str(prior_relative), set()).add(str(prior_sha))
    corpus = corpus_root or root / "corpus"
    if not corpus.is_dir():
        raise MemoryError(f"Corpus directory missing: {corpus}")
    rows = []
    graph = Graph()
    graph.bind("mem", MEM)
    graph.bind("rdf", RDF)
    for path in sorted(corpus.rglob("*")):
        if not path.is_file() or path.is_symlink() or any(part.startswith(".") for part in path.relative_to(corpus).parts):
            continue
        relative = path.relative_to(corpus).as_posix()
        sha = digest(path)
        if any(prior != sha for prior in claimed_sources.get(relative, ())):
            raise MemoryError(f"Source version is used by an accepted claim; restore it, then add the revision under a distinct path: {relative}")
        source = document_iri(relative, sha)
        graph.add((source, RDF.type, MEM.SourceDocument))
        graph.add((source, MEM.relativePath, Literal(relative)))
        graph.add((source, MEM.sha256, Literal(sha)))
        graph.add((source, MEM.byteSize, Literal(path.stat().st_size, datatype=XSD.integer)))
        graph.add((source, MEM.mediaType, Literal(mimetypes.guess_type(path.name)[0] or "application/octet-stream")))
        rows.append({"source": relative, "document_id": str(source), "sha256": sha, "bytes": path.stat().st_size})
        historical = root / "memory" / "provenance" / "sources" / (str(source).rsplit(":", 1)[-1] + ".ttl")
        if not historical.exists():
            source_graph = Graph()
            for triple in graph.triples((source, None, None)):
                source_graph.add(triple)
            write_graph(historical, source_graph)
        if path.suffix.lower() in {".txt", ".md", ".csv", ".json", ".jsonl", ".ttl", ".html", ".xml"}:
            try:
                with path.open("r", encoding="utf-8") as stream:
                    for _ in stream:
                        pass
            except UnicodeDecodeError:
                pass
            else:
                rendition_record(root, source, relative, path, "identity", "1", "corpus")
    # This file marks current versions; immutable source-version records live in sources/.
    write_graph(root / "memory" / "provenance" / "current-sources.ttl", graph)
    batches = []
    queue = root / "work" / "queue"
    queue.mkdir(parents=True, exist_ok=True)
    for start in range(0, len(rows), batch_size):
        batch_id = f"batch-{len(batches) + 1:05d}"
        payload = {"batch_id": batch_id, "ontology_version": version, "documents": rows[start:start + batch_size]}
        write_text_atomic(queue / f"{batch_id}.json", json.dumps(payload, indent=2) + "\n")
        batches.append(batch_id)
    for stale in queue.glob("batch-*.json"):
        if stale.stem not in batches:
            stale.unlink()
    manifest = {"document_count": len(rows), "batch_size": batch_size, "ontology_version": version, "batches": batches}
    write_text_atomic(queue / "manifest.json", json.dumps(manifest, indent=2) + "\n")
    return manifest


def uri(value: str, field: str) -> URIRef:
    if not isinstance(value, str) or not value or ":" not in value or value.startswith("file:"):
        raise MemoryError(f"{field} must be an absolute non-file IRI")
    return URIRef(value)


def object_term(value: dict):
    if not isinstance(value, dict):
        raise MemoryError("object must be a mapping")
    if set(value) == {"uri"}:
        return uri(value["uri"], "object.uri")
    if "literal" in value and isinstance(value["literal"], str):
        if set(value) == {"literal"}:
            return Literal(value["literal"])
        if set(value) == {"literal", "datatype"}:
            return Literal(value["literal"], datatype=uri(value["datatype"], "object.datatype"))
        if set(value) == {"literal", "lang"} and isinstance(value["lang"], str) and re.fullmatch(r"[a-zA-Z]{2,8}(-[a-zA-Z0-9]{1,8})*", value["lang"]):
            return Literal(value["literal"], lang=value["lang"])
    raise MemoryError("object requires uri or literal, optionally with datatype or lang")


def declared_entities(row: dict, graph: Graph) -> list[tuple[URIRef, str]]:
    raw = row.get("entities", [])
    if not isinstance(raw, list):
        raise MemoryError("entities must be a list")
    entities = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"iri", "label"} or not isinstance(item["label"], str) or not item["label"].strip():
            raise MemoryError("Each entity requires iri and nonempty label")
        entities.append((uri(item["iri"], "entity.iri"), item["label"]))
    declared = {iri for iri, _ in entities}
    external = row.get("external_iris", [])
    if not isinstance(external, list):
        raise MemoryError("external_iris must be a list")
    external_set = {uri(value, "external_iris") for value in external}
    terms = [uri(row["subject"], "subject")]
    obj = object_term(row["object"])
    if isinstance(obj, URIRef):
        terms.append(obj)
    for term in terms:
        if term not in declared and term not in external_set and (term, RDF.type, None) not in graph:
            raise MemoryError(f"URI resource needs an entity declaration or external_iris entry: {term}")
    return entities


def candidate_rendition(row: dict, graph: Graph, source: URIRef, root: Path, corpus_root: Path | None, rendition_root: Path | None) -> tuple[URIRef, Path]:
    relative = row.get("rendition", row["source"])
    matches = []
    for rendition in graph.subjects(MEM.forSource, source):
        if (rendition, RDF.type, MEM.TextRendition) in graph and str(graph.value(rendition, MEM.relativePath)) == relative:
            matches.append(rendition)
    for rendition in matches:
        area = str(graph.value(rendition, MEM.storageArea))
        path = corpus_file(root, relative, corpus_root) if area == "corpus" else rendition_file(root, relative, rendition_root)
        if str(graph.value(rendition, MEM.sha256)) == digest(path):
            return rendition, path
    raise MemoryError(f"No current registered UTF-8 rendition for source: {relative}")


def validate_candidate(row: dict, graph: Graph, root: Path, corpus_root: Path | None = None, rendition_root: Path | None = None) -> dict:
    required = ("claim_id", "subject", "predicate", "object", "source", "locator", "quote", "ontology_version")
    missing = [key for key in required if key not in row]
    if missing:
        raise MemoryError(f"Candidate missing fields: {', '.join(missing)}")
    if row["ontology_version"] != ontology_version(graph):
        raise MemoryError("Candidate ontology version differs from current ontology")
    claim_id = row["claim_id"]
    if not isinstance(claim_id, str) or not ID_PATTERN.fullmatch(claim_id):
        raise MemoryError("claim_id must be a lowercase safe identifier")
    uri(row["subject"], "subject")
    predicate = uri(row["predicate"], "predicate")
    if (predicate, RDF.type, RDF.Property) not in graph:
        raise MemoryError(f"Predicate is not declared as rdf:Property in ontology: {predicate}")
    object_term(row["object"])
    declared_entities(row, graph)
    if not isinstance(row["locator"], str) or not LOCATOR_PATTERN.fullmatch(row["locator"]):
        raise MemoryError("locator must be line:N with a positive line number")
    if not isinstance(row["quote"], str) or not row["quote"].strip():
        raise MemoryError("quote must be nonempty")
    path = corpus_file(root, row["source"], corpus_root)
    source = document_iri(row["source"], digest(path))
    if (source, RDF.type, MEM.SourceDocument) not in graph:
        raise MemoryError(f"Source not inventoried: {row['source']}")
    recorded = graph.value(source, MEM.sha256)
    if recorded is None or str(recorded) != digest(path):
        raise MemoryError(f"Source changed since inventory: {row['source']}")
    candidate_rendition(row, graph, source, root, corpus_root, rendition_root)
    return dict(row)


def stage(root: Path, input_path: Path, corpus_root: Path | None = None, rendition_root: Path | None = None) -> list[str]:
    graph = merged(root)
    staged = []
    lines = input_path.read_text(encoding="utf-8").splitlines()
    candidates = []
    seen = set()
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            row = validate_candidate(json.loads(line), graph, root, corpus_root, rendition_root)
        except (json.JSONDecodeError, MemoryError) as exc:
            raise MemoryError(f"Candidate line {number}: {exc}") from exc
        claim_id = row["claim_id"]
        if claim_id in seen or (root / "work" / "staging" / f"{claim_id}.json").exists() or (claim_iri(claim_id), RDF.type, MEM.Claim) in graph:
            raise MemoryError(f"Duplicate claim_id: {claim_id}")
        seen.add(claim_id)
        candidates.append(row)
    for row in candidates:
        claim_id = row["claim_id"]
        write_text_atomic(root / "work" / "staging" / f"{claim_id}.json", json.dumps(row, indent=2) + "\n")
        staged.append(claim_id)
    return staged


def verify_quote(path: Path, locator: str, quote_text: str) -> None:
    number = int(LOCATOR_PATTERN.fullmatch(locator).group(1))
    try:
        with path.open("r", encoding="utf-8") as stream:
            for current, line in enumerate(stream, 1):
                if current == number:
                    if quote_text not in line:
                        raise MemoryError(f"Quote does not match source at {locator}")
                    return
    except UnicodeDecodeError as exc:
        raise MemoryError("Source is not UTF-8 text; extract a text rendition with source linkage first") from exc
    raise MemoryError(f"Quote does not match source at {locator}")


def promote(
    root: Path, claim_id: str, reviewer: str, rationale: str,
    corpus_root: Path | None = None, conflicts_with: list[str] | None = None,
    conflict_classification: str | None = None, conflict_note: str | None = None,
    rendition_root: Path | None = None, compatible_with: list[str] | None = None,
    compatibility_note: str | None = None,
) -> dict:
    if not ID_PATTERN.fullmatch(claim_id):
        raise MemoryError("Invalid claim_id")
    if not reviewer.strip() or not rationale.strip():
        raise MemoryError("Reviewer and rationale must be nonempty")
    stage_path = root / "work" / "staging" / f"{claim_id}.json"
    if not stage_path.is_file():
        raise MemoryError(f"Staged claim not found: {claim_id}")
    graph = merged(root)
    row = validate_candidate(json.loads(stage_path.read_text(encoding="utf-8")), graph, root, corpus_root, rendition_root)
    version = ontology_version(graph)
    if row.get("ontology_version") != version:
        raise MemoryError("Staged claim ontology version differs from the current ontology; restage and review")
    if row["claim_id"] != claim_id:
        raise MemoryError("Staging file claim_id mismatch")
    claim = claim_iri(claim_id)
    if (claim, RDF.type, MEM.Claim) in graph:
        raise MemoryError(f"Already promoted: {claim_id}")
    path = corpus_file(root, row["source"], corpus_root)
    rendition, text_path = candidate_rendition(row, graph, document_iri(row["source"], digest(path)), root, corpus_root, rendition_root)
    verify_quote(text_path, row["locator"], row["quote"])
    sha = digest(path)
    text_sha = digest(text_path)
    source = document_iri(row["source"], sha)
    subject = uri(row["subject"], "subject")
    predicate = uri(row["predicate"], "predicate")
    obj = object_term(row["object"])
    evidence = evidence_iri(claim_id)
    review = review_iri(claim_id)
    now = datetime.now(timezone.utc).isoformat()
    output = Graph()
    output.bind("mem", MEM)
    output.bind("prov", PROV)
    output.bind("rdf", RDF)
    for entity, label in declared_entities(row, graph):
        output.add((entity, RDF.type, MEM.Entity))
        output.add((entity, RDFS.label, Literal(label)))
    for external in row.get("external_iris", []):
        output.add((uri(external, "external_iris"), RDF.type, MEM.ExternalResource))
    for triple in (
        (claim, RDF.type, MEM.Claim), (claim, MEM.subject, subject),
        (claim, MEM.predicate, predicate), (claim, MEM.object, obj),
        (claim, PROV.wasDerivedFrom, source), (claim, MEM.evidence, evidence),
        (claim, MEM.review, review), (claim, MEM.verificationStatus, MEM.Verified),
        (claim, MEM.reviewedBy, Literal(reviewer)),
        (claim, MEM.ontologyVersion, Literal(version)),
        (evidence, RDF.type, MEM.Evidence), (evidence, MEM.sourceDocument, source),
        (evidence, MEM.textRendition, rendition),
        (evidence, MEM.evidenceLocator, Literal(row["locator"])),
        (evidence, MEM.evidenceQuote, Literal(row["quote"])),
        (evidence, MEM.sourceSha256, Literal(sha)),
        (evidence, MEM.renditionSha256, Literal(text_sha)),
        (review, RDF.type, MEM.Review), (review, MEM.reviewer, Literal(reviewer)),
        (review, MEM.reviewedAt, Literal(now, datatype=XSD.dateTime)),
        (review, MEM.decision, MEM.Accepted), (review, MEM.rationale, Literal(rationale)),
        (review, MEM.reviewedSourceSha256, Literal(sha)),
        (review, MEM.reviewedRenditionSha256, Literal(text_sha)),
    ):
        output.add(triple)
    potential = []
    for old in graph.subjects(RDF.type, MEM.Claim):
        if graph.value(old, MEM.subject) == subject and graph.value(old, MEM.predicate) == predicate and graph.value(old, MEM.object) != obj:
            potential.append(old)
    requested = conflicts_with or []
    compatible = compatible_with or []
    if set(requested) & set(compatible):
        raise MemoryError("A pair cannot be both a conflict and compatible")
    disposed = {claim_iri(item) for item in requested + compatible}
    if set(potential) != disposed:
        missing = sorted(str(item) for item in set(potential) - disposed)
        raise MemoryError(f"Give every differing accepted claim an explicit conflict or compatibility disposition: {missing}")
    if requested and (conflict_classification not in {"temporal", "scope", "definition", "unresolved"} or not conflict_note or not conflict_note.strip()):
        raise MemoryError("Explicit conflicts require classification and a nonempty review note")
    if compatible and (not compatibility_note or not compatibility_note.strip()):
        raise MemoryError("Compatible differing values require a nonempty rationale")
    conflict_graph = Graph()
    conflicts = []
    for other_id in requested:
        other = claim_iri(other_id)
        if other not in potential:
            raise MemoryError(f"Conflict target must be a differing accepted claim for the same subject and predicate: {other_id}")
        pair = "\n".join(sorted([str(claim), str(other)]))
        conflict_id = hashlib.sha256(pair.encode()).hexdigest()[:24]
        conflict = URIRef(f"urn:agent-memory:conflict:{conflict_id}")
        if (conflict, RDF.type, MEM.Conflict) in graph:
            raise MemoryError(f"Conflict already recorded: {other_id}")
        for triple in (
            (conflict, RDF.type, MEM.Conflict), (conflict, MEM.claimA, other),
            (conflict, MEM.claimB, claim),
            (conflict, MEM.classification, Literal(conflict_classification)),
            (conflict, MEM.reviewer, Literal(reviewer)),
            (conflict, MEM.rationale, Literal(conflict_note)),
            (conflict, MEM.reviewedAt, Literal(now, datatype=XSD.dateTime)),
        ):
            conflict_graph.add(triple)
        conflicts.append(str(conflict))
    compatibilities = []
    for other_id in compatible:
        other = claim_iri(other_id)
        if other not in potential:
            raise MemoryError(f"Compatibility target must be a differing accepted claim for the same subject and predicate: {other_id}")
        pair = "\n".join(sorted([str(claim), str(other)]))
        decision = URIRef(f"urn:agent-memory:compatibility:{hashlib.sha256(pair.encode()).hexdigest()[:24]}")
        for triple in (
            (decision, RDF.type, MEM.CompatibilityReview), (decision, MEM.claimA, other),
            (decision, MEM.claimB, claim),
            (decision, MEM.reviewer, Literal(reviewer)),
            (decision, MEM.rationale, Literal(compatibility_note)),
            (decision, MEM.reviewedAt, Literal(now, datatype=XSD.dateTime)),
        ):
            conflict_graph.add(triple)
        compatibilities.append(str(decision))
    index_path = root / "memory" / "index.ttl"
    index = Graph()
    index.parse(index_path, format="turtle", publicID="urn:agent-memory:base:")
    index.add((MEM.catalog, RDFS.seeAlso, claim))
    index.add((claim, MEM.storedAt, Literal(f"entities/{claim_id}.ttl")))
    claim_path = root / "memory" / "entities" / f"{claim_id}.ttl"
    if claim_path.exists():
        raise MemoryError(f"Claim file already exists; inspect possible interrupted promotion: {claim_path}")
    changes = {claim_path: output}
    if conflicts or compatibilities:
        changes[root / "memory" / "provenance" / f"pair-review-{claim_id}.ttl"] = conflict_graph
    changes[index_path] = index
    commit_graphs(changes)
    return {"claim": str(claim), "conflicts": conflicts, "compatibilities": compatibilities, "potential_differences": [str(item) for item in potential]}


def record_memory(root: Path, kind: str, record_id: str, value: str, recorder: str) -> URIRef:
    if kind not in {"rule", "session"} or not ID_PATTERN.fullmatch(record_id):
        raise MemoryError("Memory kind or ID invalid")
    if not value.strip() or not recorder.strip():
        raise MemoryError("Text and recorder must be nonempty")
    graph = merged(root)
    version = ontology_version(graph)
    resource = URIRef(f"urn:agent-memory:{kind}:{record_id}")
    if (resource, None, None) in graph:
        raise MemoryError(f"Memory record already exists: {record_id}")
    folder = "howto" if kind == "rule" else "sessions"
    relative = f"{folder}/{record_id}.ttl"
    path = root / "memory" / relative
    record = Graph()
    record.bind("mem", MEM)
    record.add((resource, RDF.type, MEM.StandingRule if kind == "rule" else MEM.SessionOutcome))
    record.add((resource, MEM.text, Literal(value)))
    record.add((resource, MEM.recordedBy, Literal(recorder)))
    record.add((resource, MEM.recordedAt, Literal(datetime.now(timezone.utc).isoformat(), datatype=XSD.dateTime)))
    record.add((resource, MEM.ontologyVersion, Literal(version)))
    index_path = root / "memory" / "index.ttl"
    index = Graph()
    index.parse(index_path, format="turtle", publicID="urn:agent-memory:base:")
    index.add((MEM.catalog, RDFS.seeAlso, resource))
    index.add((resource, MEM.storedAt, Literal(relative)))
    commit_graphs({path: record, index_path: index})
    return resource


def validate(root: Path, corpus_root: Path | None = None, rendition_root: Path | None = None) -> list[str]:
    errors: list[str] = []
    memory = root / "memory"
    for name in BOOTSTRAP:
        if not (memory / name).is_file():
            errors.append(f"Missing bootstrap file: {name}")
    try:
        graph = merged(root)
    except Exception as exc:
        return errors + [f"Turtle parse error: {exc}"]
    try:
        version = ontology_version(graph)
    except MemoryError as exc:
        errors.append(str(exc))
        version = None

    def one(resource, property_):
        values = list(graph.objects(resource, property_))
        if len(values) != 1:
            errors.append(f"Expected exactly one {property_} for {resource}; found {len(values)}")
            return None
        return values[0]

    for triple in graph:
        predicate = triple[1]
        if str(predicate).startswith(str(MEM)) and (predicate, RDF.type, RDF.Property) not in graph:
            errors.append(f"Undeclared memory predicate: {predicate}")
        if predicate == RDF.type and isinstance(triple[2], URIRef) and str(triple[2]).startswith(str(MEM)):
            type_iri = triple[2]
            if (type_iri, RDF.type, RDFS.Class) not in graph:
                errors.append(f"Undeclared memory class: {type_iri}")
        for term in triple:
            if isinstance(term, URIRef) and str(term).startswith("file:"):
                errors.append(f"Machine-specific file IRI: {term}")
    claims = set(graph.subjects(RDF.type, MEM.Claim))
    indexed = set(graph.objects(MEM.catalog, RDFS.seeAlso))
    for reference in indexed:
        if str(reference).startswith("urn:agent-memory:claim:") and reference not in claims:
            errors.append(f"Dangling claim index: {reference}")
    for kind in (MEM.StandingRule, MEM.SessionOutcome):
        for resource in set(graph.subjects(RDF.type, kind)):
            if resource not in indexed:
                errors.append(f"Memory record missing from index: {resource}")
            for field in (MEM.text, MEM.recordedBy, MEM.recordedAt, MEM.storedAt, MEM.ontologyVersion):
                one(resource, field)
            if version is not None and graph.value(resource, MEM.ontologyVersion) != Literal(version):
                errors.append(f"Memory record ontology version mismatch: {resource}")
            stored = graph.value(resource, MEM.storedAt)
            if stored is not None:
                target = (memory / str(stored)).resolve()
                if not target.is_relative_to(memory.resolve()) or not target.is_file():
                    errors.append(f"Memory record storedAt invalid: {resource}")
                else:
                    own = Graph()
                    own.parse(target, format="turtle", publicID="urn:agent-memory:base:")
                    if (resource, RDF.type, kind) not in own:
                        errors.append(f"Memory record index target mismatch: {resource}")
    for claim in sorted(claims, key=str):
        if claim not in indexed:
            errors.append(f"Claim missing from index: {claim}")
        stored_at = one(claim, MEM.storedAt)
        if stored_at is not None:
            relative_store = Path(str(stored_at))
            stored_file = (memory / relative_store).resolve()
            if relative_store.is_absolute() or not stored_file.is_relative_to(memory.resolve()) or not stored_file.is_file():
                errors.append(f"Invalid storedAt path for {claim}")
            else:
                own_graph = Graph()
                own_graph.parse(stored_file, format="turtle", publicID="urn:agent-memory:base:")
                if (claim, RDF.type, MEM.Claim) not in own_graph:
                    errors.append(f"Index target does not contain claim: {claim}")
        if one(claim, MEM.verificationStatus) != MEM.Verified:
            errors.append(f"Claim not verified: {claim}")
        claim_version = one(claim, MEM.ontologyVersion)
        if version is not None and claim_version != Literal(version):
            errors.append(f"Claim ontology version mismatch: {claim}")
        reviewer = one(claim, MEM.reviewedBy)
        if reviewer is not None and not str(reviewer).strip():
            errors.append(f"Claim reviewer empty: {claim}")
        subject = one(claim, MEM.subject)
        predicate = one(claim, MEM.predicate)
        obj = one(claim, MEM.object)
        if predicate is not None and (predicate, RDF.type, RDF.Property) not in graph:
            errors.append(f"Claim predicate not in ontology: {claim}")
        for term in (subject, obj):
            if isinstance(term, URIRef) and (term, RDF.type, None) not in graph:
                errors.append(f"Undeclared claim entity: {term}")
        source = one(claim, PROV.wasDerivedFrom)
        evidence = one(claim, MEM.evidence)
        review = one(claim, MEM.review)
        if source is None or (source, RDF.type, MEM.SourceDocument) not in graph:
            errors.append(f"Claim lacks inventoried provenance: {claim}")
            continue
        if evidence is None or (evidence, RDF.type, MEM.Evidence) not in graph:
            errors.append(f"Claim lacks evidence node: {claim}")
            continue
        if review is None or (review, RDF.type, MEM.Review) not in graph:
            errors.append(f"Claim lacks review node: {claim}")
            continue
        if one(evidence, MEM.sourceDocument) != source:
            errors.append(f"Evidence source mismatch: {claim}")
        rendition = one(evidence, MEM.textRendition)
        locator = one(evidence, MEM.evidenceLocator)
        quote_text = one(evidence, MEM.evidenceQuote)
        sha = one(source, MEM.sha256)
        relative = one(source, MEM.relativePath)
        if None in (rendition, locator, quote_text, sha, relative):
            continue
        if (rendition, RDF.type, MEM.TextRendition) not in graph or one(rendition, MEM.forSource) != source:
            errors.append(f"Rendition provenance mismatch: {claim}")
            continue
        rendition_sha = one(rendition, MEM.sha256)
        rendition_relative = one(rendition, MEM.relativePath)
        area = one(rendition, MEM.storageArea)
        for field in (MEM.extractionMethod, MEM.extractionVersion):
            value = one(rendition, field)
            if value is not None and not str(value).strip():
                errors.append(f"Empty rendition metadata for {claim}")
        if None in (rendition_sha, rendition_relative, area):
            continue
        if one(evidence, MEM.sourceSha256) != sha or one(review, MEM.reviewedSourceSha256) != sha:
            errors.append(f"Original source digest mismatch: {claim}")
        if one(evidence, MEM.renditionSha256) != rendition_sha or one(review, MEM.reviewedRenditionSha256) != rendition_sha:
            errors.append(f"Text rendition digest mismatch: {claim}")
        if one(review, MEM.decision) != MEM.Accepted:
            errors.append(f"Review not accepted: {claim}")
        if one(review, MEM.reviewer) != reviewer:
            errors.append(f"Reviewer mismatch: {claim}")
        for field in (MEM.reviewedAt, MEM.rationale):
            value = one(review, field)
            if value is not None and not str(value).strip():
                errors.append(f"Empty review field for {claim}")
        if not LOCATOR_PATTERN.fullmatch(str(locator)):
            errors.append(f"Invalid evidence locator: {claim}")
            continue
        try:
            original = corpus_file(root, str(relative), corpus_root)
            text = corpus_file(root, str(rendition_relative), corpus_root) if str(area) == "corpus" else rendition_file(root, str(rendition_relative), rendition_root)
            if digest(original) != str(sha) or document_iri(str(relative), str(sha)) != source:
                errors.append(f"Original source changed or identity invalid: {claim}")
            if digest(text) != str(rendition_sha) or rendition_iri(source, str(rendition_relative), str(rendition_sha)) != rendition:
                errors.append(f"Text rendition changed or identity invalid: {claim}")
            verify_quote(text, str(locator), str(quote_text))
        except MemoryError as exc:
            errors.append(f"Evidence invalid for {claim}: {exc}")

    pair_decisions = {}
    for decision_type in (MEM.Conflict, MEM.CompatibilityReview):
      for conflict in set(graph.subjects(RDF.type, decision_type)):
        first = one(conflict, MEM.claimA)
        second = one(conflict, MEM.claimB)
        classification = one(conflict, MEM.classification) if decision_type == MEM.Conflict else None
        for field in (MEM.reviewer, MEM.rationale, MEM.reviewedAt):
            value = one(conflict, field)
            if value is not None and not str(value).strip():
                errors.append(f"Empty pair review field: {conflict}")
        if first not in claims or second not in claims or first == second:
            errors.append(f"Pair review references invalid claims: {conflict}")
        elif graph.value(first, MEM.subject) != graph.value(second, MEM.subject) or graph.value(first, MEM.predicate) != graph.value(second, MEM.predicate) or graph.value(first, MEM.object) == graph.value(second, MEM.object):
            errors.append(f"Pair review is not a differing same-subject/predicate pair: {conflict}")
        if decision_type == MEM.Conflict and str(classification) not in {"temporal", "scope", "definition", "unresolved"}:
            errors.append(f"Invalid conflict classification: {conflict}")
        if first is not None and second is not None:
            pair_decisions.setdefault(frozenset((first, second)), []).append(conflict)
    ordered_claims = sorted(claims, key=str)
    for position, first in enumerate(ordered_claims):
        for second in ordered_claims[position + 1:]:
            if graph.value(first, MEM.subject) == graph.value(second, MEM.subject) and graph.value(first, MEM.predicate) == graph.value(second, MEM.predicate) and graph.value(first, MEM.object) != graph.value(second, MEM.object):
                decisions = pair_decisions.get(frozenset((first, second)), [])
                if len(decisions) != 1:
                    errors.append(f"Differing claim pair requires exactly one reviewed disposition: {first}, {second}")
    for left, right in graph.subject_objects(OWL.sameAs):
        reviews = [review for review in graph.subjects(RDF.type, MEM.IdentityReview)
                   if graph.value(review, MEM.leftIdentity) == left and graph.value(review, MEM.rightIdentity) == right]
        if len(reviews) != 1:
            errors.append(f"Identity equivalence requires exactly one matching review: {left}, {right}")
            continue
        review = reviews[0]
        evidence = one(review, MEM.identityEvidence)
        if evidence is None or (evidence, RDF.type, MEM.Evidence) not in graph:
            errors.append(f"Identity review lacks accepted evidence: {review}")
        for field in (MEM.reviewer, MEM.rationale, MEM.reviewedAt):
            value = one(review, field)
            if value is not None and not str(value).strip():
                errors.append(f"Empty identity review field: {review}")
    return sorted(set(errors))

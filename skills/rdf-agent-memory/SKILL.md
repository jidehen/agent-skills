---
name: rdf-agent-memory
description: Build, retrieve, validate, and query durable RDF and Turtle agent memory or an evidence-grounded document ontology. Use when asked to remember operating rules, turn a document collection into a knowledge graph, trace a claim to evidence, resolve entities, review differing claims, or answer a cross-document question with SPARQL.
license: MIT
metadata:
  version: "0.1.0"
  category: "knowledge-management"
  tags: "rdf, turtle, sparql, provenance, ontology, multi-agent"
---

# RDF Agent Memory

Use a project-local `memory/` tree of Turtle files for durable state. The tool repository and the project using it are separate: initialize a new project with `python3 scripts/memory.py init --memory-root /path/to/project/memory`. The project root is the parent directory of `memory/`; `corpus/`, `renditions/`, and `work/` default to sibling directories. Do not initialize over existing memory.

## Core invariants

1. The project's `memory/` directory is the canonical record. Chat history and summaries are not authoritative.
2. Before retrieving remembered context, list the tree and read `core.ttl`, `preferences.ttl`, `ontology.ttl`, and `index.ttl`, then follow relevant `rdfs:seeAlso` links.
3. Use Turtle for durable records and parse-validate edited Turtle before it is accepted.
4. Candidates live in `work/staging/` as JSON files and are excluded from the canonical query dataset. Never answer factual questions from staged candidates.
5. A promoted claim has a source-version link, registered text rendition, `line:N` locator, quotation, source and rendition digests, verification status, reviewer, review decision and rationale, and ontology version.
6. Never silently overwrite an accepted claim. For every already accepted different object with the same subject and predicate, promotion requires an explicit conflict classification and note or a compatibility note. Keep both claims and their review record.
7. Use local SPARQL `SELECT` queries for cross-file retrieval. The current command does not perform ontology reasoning or remote queries.

## Retrieval

1. List the project's `memory/` tree.
2. Read the four bootstrap files and any private overlay.
3. Classify the request using `memory/ontology.ttl` and follow `rdfs:seeAlso` to relevant rules, projects, entities, provenance, and sessions.
4. Query when an answer spans files. Include supporting claim, source, locator, review state, and conflicts; explain when evidence is missing or ambiguous.

## Document workflow

Use the roles in [references/agent-roles.md](references/agent-roles.md) and handoff process in [references/document-pipeline.md](references/document-pipeline.md). Initialize the project, define competency questions, and develop a small domain vocabulary in `memory/ontology.ttl`. Keep stable meanings, labels, classes, and predicates clear; declare each candidate predicate as an `rdf:Property` and update `mem:version` when a semantic vocabulary change affects interpretation.

Inventory sources with `scripts/memory.py inventory`. The command records source versions and writes JSON batch assignments under `work/queue/`, including the current ontology version. Plain UTF-8 files in supported formats receive an identity rendition. For binary documents, register a versioned UTF-8 rendition with `register-rendition`. Candidate handoffs are JSON Lines; each candidate must include the matching `ontology_version` from the queue manifest, source-relative path, positive `line:N` locator into a current registered rendition, a matching quotation, unique safe ID, subject, declared predicate, and object. Declare entity terms or mark external IRIs explicitly. Stage rejects a missing or stale ontology version; it never fills in the field.

Stage candidates using `scripts/memory.py stage handoff.jsonl`. A reviewer independently checks the original source, rendition, quote, scope, and interpretation before `scripts/memory.py promote CLAIM_ID --reviewer NAME --rationale TEXT`. Staging checks structure, ontology version, and source consistency; promotion additionally checks that the quote appears at the cited line and requires dispositions for all differing accepted values. Promotion is a review gate, not an automatic extraction-quality guarantee.

## Validation and scale

Use `scripts/memory.py validate --memory-root /path/to/project/memory` and `scripts/check_vendor_neutral.py` before sharing a project. For architecture comparisons, see [references/architecture-faq.md](references/architecture-faq.md). For a fresh ontology over thousands of long documents, follow [references/scaling-playbook.md](references/scaling-playbook.md): define questions, sample, version source and rendition inputs, shard extraction and review, bound concurrency, and measure quality and capacity. The included RDFLib query path reloads the accepted tree into memory per process; it is a prototype and not a scale guarantee. `scripts/benchmark_smoke.py` exercises inventory and query mechanics on synthetic files with one promoted claim; it is not a corpus-wide extraction or 10,000-document capacity test.

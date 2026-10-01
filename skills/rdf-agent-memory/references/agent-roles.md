# Agent roles and handoffs

The roles separate extraction, identity decisions, vocabulary maintenance, evidence review, and answering. One person can cover multiple roles in a small project, but an analyst should not verify and promote its own unreviewed candidate. For a large collection, use a coordinator to assign document batches and a single promotion writer per memory namespace; multiple workers should not concurrently edit the shared index or the same ontology/entity file.

## Coordinator

Run `scripts/memory.py inventory --memory-root PROJECT/memory --batch-size 100`. This records current source versions and writes `work/queue/batch-00001.json` and a manifest. Assign each batch, or a smaller page-range shard, to an analyst. Keep the source paths, document IDs, ontology version, and task boundaries in the assignment. Queue JSON files are assignments, not claim data; this tool does not launch agents or manage leases, retries, or concurrent writers. Track those operational states in the orchestration layer.

## Document analyst

Read only assigned sources or registered renditions. Return candidate assertions as UTF-8 JSON Lines. Use one JSON object per line with a unique lowercase `claim_id`, `ontology_version` copied from the assigned queue batch or manifest, absolute IRI `subject`, declared IRI `predicate`, `object` as `{"uri":"..."}` or `{"literal":"..."}` (optional language or datatype), corpus-relative `source`, positive `line:N` locator, exact nonempty `quote`, and optional `entities`, `external_iris`, or `rendition`. An entity declaration has `iri` and human-readable `label`. The quote must appear on that line of the current registered UTF-8 rendition; for a binary original, point `rendition` at its registered text file. Do not create canonical Turtle or assign a verified status.

Example handoff record (one line in a `.jsonl` file):

```json
{"claim_id":"policy-42-owner","ontology_version":"1.0.0","subject":"urn:example:policy:42","predicate":"urn:example:hasOwner","object":{"uri":"urn:example:team:security"},"source":"policies/control-handbook.pdf","rendition":"policies/control-handbook.txt","locator":"line:42","quote":"The Security team owns Policy 42.","entities":[{"iri":"urn:example:policy:42","label":"Policy 42"},{"iri":"urn:example:team:security","label":"Security team"}]}
```

The coordinator stages a complete handoff with:

```bash
python3 scripts/memory.py stage PROJECT/handoffs/policy-claims.jsonl --memory-root PROJECT/memory
```

The analyst copies the assigned ontology version into every candidate. Staging verifies that supplied version matches the current ontology and writes the candidate file under `work/staging/`; it does not add or repair the field. It rejects unknown predicates, missing source inventory, changed source digests, missing or stale renditions, bad locator formats, duplicate IDs, and undeclared URI terms. It does not check quote-to-meaning entailment; that is the reviewer's job.

## Entity resolver

Propose canonical identifiers and aliases with evidence from assigned source versions. Distinguish same-name entities by context and scope. For unresolved identity use `mem:possibleMatch` or a review handoff; do not force equivalence. The current `stage` interface accepts declared candidate entities but does not implement a complete alias-resolution queue, so send proposals to the ontology steward and promotion writer for the project's agreed review process.

## Ontology steward

Maintain the domain vocabulary in the project's `memory/ontology.ttl`. Define classes and predicates with stable meanings, labels, domains, ranges, and examples where useful. Candidate predicates must be declared as `rdf:Property`. Keep the required ontology resource `mem:ontology` with exactly one nonempty `mem:version`; bump the version when a semantic change affects interpretation. Inventory records this version in each batch, and staging records it on every claim; promotion rejects staged claims when the ontology version has changed. Recheck competency queries after vocabulary changes.

## Evidence reviewer and promotion writer

Independently compare each candidate with the original source and the linked rendition. Check the source and rendition digests, exact quoted line, claim meaning, scope, date, and entity identity. A successful promotion creates the verified claim, evidence, and review record. Invoke `promote CLAIM_ID --reviewer NAME --rationale TEXT` only after this review.

When a candidate has a different object from any accepted claim with the same subject and predicate, disposition every such accepted claim. Use `--conflicts-with CLAIM_ID --conflict-classification temporal|scope|definition|unresolved --conflict-note TEXT` for a reviewed contradiction. Use `--compatible-with CLAIM_ID --compatibility-note TEXT` when different values can coexist. The command requires all differing accepted claims to be covered; it does not decide automatically whether they conflict. A reviewer note should explain the basis. Serialize promotions through one writer per namespace to avoid concurrent updates to the shared index and review files.

## Query analyst

Use `scripts/memory.py query queries/claims-with-evidence.rq --memory-root PROJECT/memory --json` or a reviewed local `SELECT` query. Report the claim, source version, rendition locator, quote, reviewer, and review state. Also query `queries/reviewed-conflicts.rq` when a relationship may be disputed. The query command does not read staging, contact remote services, or infer facts from ontology declarations. Do not treat vector similarity, labels, or an unreviewed candidate as accepted evidence.

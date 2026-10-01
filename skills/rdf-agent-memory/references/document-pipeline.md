# Evidence-grounded document pipeline

This is a review workflow around the current local CLI. It does not perform OCR, extract claims from documents, schedule agents, or provide a multi-writer queue service. An orchestration layer may do those jobs, but its outputs must satisfy the local source and evidence gates described here.

## 1. Start a separate project and define the vocabulary

Clone the tool repository and initialize a new project directory, for example:

```bash
python3 scripts/memory.py init --memory-root ../policy-ontology/memory
```

This creates `memory/`, `corpus/`, `renditions/`, and `work/` under `policy-ontology/`. Keep the domain ontology in `memory/ontology.ttl`. Begin with questions and a representative sample; define stable classes and predicates, declare candidate predicates as `rdf:Property`, and maintain exactly one nonempty `mem:version` on `mem:ontology`. Version semantic changes so staged candidates can be checked against the vocabulary they used.

## 2. Inventory source versions and distribute batches

Put authorized source files under `corpus/`, then run:

```bash
python3 scripts/memory.py inventory --memory-root ../policy-ontology/memory --batch-size 100
```

Inventory records a source IRI derived from its corpus-relative path and SHA-256 digest, including path, digest, byte size, and media type. A changed file gets a different source IRI when inventoried; historical source records are retained. The command writes the current inventory, versioned provenance records, and batch assignment JSON in `work/queue/`, with ontology version and source metadata. It does not create a semantic revision relation between old and new source versions, capture all governance metadata, or assign work to agents. Maintain any additional custody, access, retention, revision, and task status in the project's approved orchestration layer.

Assign batches or page-range shards to analysts. Each handoff should identify source version, ontology version, task bounds, and a unique claim ID scheme. For 100–300 page documents, partition extraction by page range when useful, then reconcile cross-page references before returning candidates. Begin with small workloads that fit a worker and reviewer's capacity.

## 3. Create citable UTF-8 renditions

Inventory automatically registers an identity rendition for UTF-8 files with extensions `.txt`, `.md`, `.csv`, `.json`, `.jsonl`, `.ttl`, `.html`, and `.xml`. Binary documents need a UTF-8 text rendition linked to the inventoried original:

```bash
python3 scripts/memory.py register-rendition \
  --memory-root ../policy-ontology/memory \
  --source handbooks/control-handbook.pdf \
  --text handbooks/control-handbook.txt \
  --method approved-extractor --version 1
```

The tool records the rendition digest, extraction method and version, source link, relative path, and whether it is in the corpus or rendition area. It currently supports only a positive `line:N` locator into a UTF-8 rendition. The reviewer must be able to map the cited rendition line to the source page or location. The CLI does not itself record page boundaries or OCR quality, so include that information in a controlled companion manifest where needed. If extraction changes, register and review the new rendition; a stale rendition digest blocks validation and promotion.

## 4. Return candidate claims as JSON Lines

Analysts write one JSON object per line in a UTF-8 `.jsonl` handoff file. Required fields are `claim_id`, `ontology_version`, `subject`, `predicate`, `object`, `source`, `locator`, and `quote`. Copy `ontology_version` from the assigned batch or `work/queue/manifest.json`; staging verifies that it matches the current ontology and rejects missing or stale versions. Use a positive `line:N`; the quote must appear on that line of the registered rendition. For an identity rendition the path defaults to the source path. For a separate text rendition, include its relative path as `rendition`. URI terms need an `entities` declaration with `iri` and `label`, an `external_iris` declaration, or an existing declared resource. Keep one assertion per claim and include only source-supported meaning; write uncertainty and interpretation questions in handoff notes rather than as facts.

Example line:

```json
{"claim_id":"control17-owner-a","ontology_version":"1.0.0","subject":"urn:example:control:17","predicate":"urn:example:hasOwner","object":{"uri":"urn:example:team:atlas"},"source":"northstar/a.pdf","rendition":"northstar/a.txt","locator":"line:42","quote":"The Atlas team owns Control 17.","entities":[{"iri":"urn:example:control:17","label":"Control 17"},{"iri":"urn:example:team:atlas","label":"Atlas team"}]}
```

Stage a handoff with `python3 scripts/memory.py stage ../handoffs/claims.jsonl --memory-root ../policy-ontology/memory`. Staging checks JSON shape, required current ontology version, unique IDs, current source digest, registered rendition, locator form, vocabulary predicate declaration, and URI declarations. It writes candidate JSON objects under `work/staging/` with the supplied ontology version preserved. These are not canonical Turtle and are excluded from query results. Staging does not judge whether the claim is entailed by the quoted text.

## 5. Resolve entities and review evidence

Entity resolvers propose canonical IDs and aliases using context, scope, and source evidence. Similar labels do not establish identity. Keep uncertain matches separate and record them as pending review using the project's vocabulary. The current CLI does not include a separate alias resolution command.

An independent reviewer checks the original source and rendition, exact line and quote, digest, dates, qualifiers, and intended relationship. Check extraction quality and whether a paraphrase preserves the source's meaning. Do not use confidence scores as a substitute for this review. Record a concise, specific rationale when promoting:

```bash
python3 scripts/memory.py promote control17-owner-a \
  --memory-root ../policy-ontology/memory \
  --reviewer reviewer-1 --rationale 'Verified the quoted rendition line and source context.'
```

Promotion rejects a claim if its staged ontology version differs from the current ontology, the source or rendition has changed, or the quote is absent from the specified line. Accepted claims include a source-version link, rendition evidence, digests, verified status, reviewer, review decision and rationale, and ontology version. They are stored as Turtle and indexed. These checks establish traceability and review record completeness, not truth of the source itself.

## 6. Disposition different accepted values

Before promotion, the CLI compares accepted claims with the same subject and predicate. Every one with a different object needs an explicit disposition. For an actual contradiction, use `--conflicts-with CLAIM_ID`, one of `--conflict-classification temporal|scope|definition|unresolved`, and a nonempty `--conflict-note`. For a difference that can coexist, use `--compatible-with CLAIM_ID` and a nonempty `--compatibility-note`. Every differing accepted claim must be covered, even if some are conflicts and others are compatible. A claim ID cannot be both. A conflict is stored as a reviewed conflict record; compatible difference is stored as a compatibility review record. Do not assume that differing values conflict when the relation is multi-valued or applies at different times.

## 7. Query, validate, and scale with measurements

Run local read-only queries against accepted canonical files, for example:

```bash
python3 scripts/memory.py query queries/claims-with-evidence.rq --memory-root ../policy-ontology/memory --json
python3 scripts/memory.py query queries/reviewed-conflicts.rq --memory-root ../policy-ontology/memory --json
python3 scripts/memory.py validate --memory-root ../policy-ontology/memory
```

The query command accepts only local `SELECT` queries and loads canonical Turtle into an in-process dataset each run. It neither includes staging files nor runs inference. Return source path, source-version identifier, locator, quotation, reviewer, and conflict information with answers.

For a 10,000-document corpus of hundreds of pages each, use a representative sample to estimate source volume, rendition coverage, claim rate, review time, filesystem use, parse time, memory, and query latency before expanding. Bound parallel extraction, keep one promotion writer per namespace, make work restartable in the orchestration layer, and move to deterministic Turtle shards and a persistent query projection only after measurements show the local layout misses agreed targets. See [the scaling playbook](scaling-playbook.md) and [the architecture FAQ](architecture-faq.md) for the limits and comparison with vector and property graph approaches.

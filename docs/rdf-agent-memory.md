# RDF Agent Memory

RDF Agent Memory is a local-first pattern for durable agent memory and evidence-grounded document ontologies. Turtle files are the canonical record; the command line loads them into an RDFLib dataset for local SPARQL `SELECT` queries. The current prototype needs no graph server or network connection after its Python dependency is installed.

The project separates its own code from each user's project data. Clone or copy this repository as a reusable tool, then create a separate project directory containing `memory/`, `corpus/`, `renditions/`, and `work/`. Keep private corpora and generated memory in a private project location; do not add them to a public clone.

## What the prototype demonstrates

- Source files are inventoried by version and SHA-256 digest.
- Claims remain candidates until their quoted evidence is checked against a registered UTF-8 text rendition.
- Accepted claims retain their source version, evidence locator, review decision, reviewer, and ontology version.
- Different values for the same subject and predicate require an explicit compatibility or conflict disposition during promotion.
- Canonical Turtle files can be reviewed, versioned, and queried with local SPARQL.

The prototype does not infer facts merely because an ontology declares a relationship. Its query command runs local read-only `SELECT` queries over accepted Turtle files. See the [Architecture FAQ](../skills/rdf-agent-memory/references/architecture-faq.md) for RDF, Turtle, semantic knowledge graph, vector search, and property graph comparisons. See the [scaling playbook](../skills/rdf-agent-memory/references/scaling-playbook.md) for a measured plan for corpora such as 10,000 documents that are hundreds of pages each.

## Quick start

From the repository root, enter `skills/rdf-agent-memory`, install the package, initialize a project, and run the synthetic end-to-end demo in a separate project directory:

```bash
cd skills/rdf-agent-memory
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python scripts/memory.py init --memory-root /tmp/my-project/memory
.venv/bin/python scripts/run_demo.py --output /tmp/rdf-memory-demo
.venv/bin/python scripts/memory.py query queries/claims-with-evidence.rq --memory-root /tmp/rdf-memory-demo/memory --json
.venv/bin/python scripts/memory.py query queries/reviewed-conflicts.rq --memory-root /tmp/rdf-memory-demo/memory --json
.venv/bin/python scripts/memory.py validate --memory-root /tmp/rdf-memory-demo/memory
```

`init` creates `/tmp/my-project/{memory,corpus,renditions,work}`. The demo creates a separate project at `/tmp/rdf-memory-demo` with two synthetic documents, accepted claims, and one explicitly reviewed unresolved conflict. Each target directory must be new: initialization will not overwrite an existing `memory/`. The project root is inferred from the parent of `--memory-root`; corpus, rendition, and work paths default to sibling directories there.

The prototype CLI is `scripts/memory.py`. Its subcommands are `init`, `inventory`, `register-rendition`, `stage`, `promote`, `remember-rule`, `record-session`, `query`, `validate`, and `status`. The older one-command wrapper scripts remain available, but examples here use the unified CLI.

## Make the skill available to an agent

The `skills/rdf-agent-memory/` folder is the skill folder: its name matches the `name` in `SKILL.md`. If an agent runtime supports installed skills, copy or link that whole folder into its documented skill search directory. Point a project-level `AGENTS.md` or equivalent instruction file at the installed skill when the runtime supports that pattern. Installing the Python package above installs its command dependencies; it does not register the skill with an agent runtime.

If there is no skill installer, tell the agent to read the cloned repository's absolute `SKILL.md` path and use `scripts/memory.py` beside it. For example: “Read `/absolute/path/to/agent-skills/skills/rdf-agent-memory/SKILL.md`, then initialize `/absolute/path/to/my-project/memory` and follow that skill. Keep project data in `my-project/`, outside the tool clone.” The skill and CLI can be used without copying anything into a runtime-specific location.

## Build a document ontology

Start with questions the graph must answer and a bounded sample, then create domain classes and predicates in the new project's `memory/ontology.ttl`. The initialized vocabulary supplies generic claim, evidence, review, source, and memory terms; domain concepts should come from the questions and reviewed sample, not a blind extraction of every phrase in the corpus. Keep project-specific classes and predicates small, clearly defined, and versioned. Every candidate predicate must be declared as an `rdf:Property`; terms used as URI subjects or objects must be declared entities, explicitly listed external IRIs, or existing resources. Bump `mem:version` when a vocabulary change affects claim interpretation. Candidate handoffs carry that version and must be restaged if it changes before promotion.

For a source corpus already in `my-project/corpus/`, inventory files and create document work batches:

```bash
.venv/bin/python scripts/memory.py inventory --memory-root /tmp/my-project/memory --batch-size 100
```

The command writes versioned source records and JSON batch assignments under `my-project/work/queue/`. UTF-8 text files with supported extensions receive an identity rendition automatically. For binary documents such as PDF, keep the original in `corpus/`, create a UTF-8 text rendition under `renditions/`, then register the link after inventory:

```bash
.venv/bin/python scripts/memory.py register-rendition \
  --memory-root /tmp/my-project/memory \
  --source policies/control-handbook.pdf \
  --text policies/control-handbook.txt \
  --method approved-extractor --version 1
```

The queue JSON files are document assignments, not claim files. Analysts return candidate records as JSON Lines (`.jsonl`) handoffs; a person using the workflow can describe the job in ordinary language and ask an agent team to prepare that file. Each line has a unique `claim_id`, the `ontology_version` from the queue manifest, absolute IRIs for `subject` and `predicate`, an `object` mapping, a corpus-relative `source`, a locator such as `line:42`, a nonempty `quote`, and optional `entities`, `external_iris`, or `rendition` fields. `line:N` is currently the only supported locator, and it refers to a line in the current registered UTF-8 rendition. For an automatically registered text source, the rendition path defaults to the same relative path; for a PDF rendition, set `rendition` to its rendition-relative path.

Example handoff line:

```json
{"claim_id":"policy-42-owner","ontology_version":"1.0.0","subject":"urn:example:policy:42","predicate":"urn:example:hasOwner","object":{"uri":"urn:example:team:security"},"source":"policies/control-handbook.pdf","rendition":"policies/control-handbook.txt","locator":"line:42","quote":"The Security team owns Policy 42.","entities":[{"iri":"urn:example:policy:42","label":"Policy 42"},{"iri":"urn:example:team:security","label":"Security team"}]}
```

The JSONL is an agent-to-tool handoff; most users should ask for the work in natural language. For example:

> Initialize a fresh project called `my-project` with this tool. Help me define a small ontology for policy ownership, then ingest the next two inventory batches. Return candidate claims with source quotes and line locators, but leave them staged for my review.

> Answer which team owns Policy 42. Cite the original source version and exact evidence line, and show any reviewed conflict.

> Remember that I want conflict reports included in every policy ownership answer. Record that as a project rule.

For an explicit handoff path, save the records as UTF-8 JSON Lines in a `.jsonl` file, using the version from `work/queue/manifest.json`, and stage them:

```bash
.venv/bin/python scripts/memory.py stage /tmp/handoffs/policy-claims.jsonl --memory-root /tmp/my-project/memory
```

Staging validates the shape, required ontology version, source inventory and digest, rendition link, locator format, and declared terms. The submitted version must equal the current ontology version; staging does not add it. Staging does not decide whether a claim is true, and staged claims are excluded from queries. A reviewer checks the original source and rendition, then promotes each staged ID with a reviewer identity and rationale:

```bash
.venv/bin/python scripts/memory.py promote policy-42-owner \
  --memory-root /tmp/my-project/memory \
  --reviewer reviewer-1 --rationale 'Confirmed the quoted line and its scope.'
```

Promotion verifies that the quote appears on the specified `line:N`, records the source and rendition digests, and adds the accepted claim to canonical Turtle. If an accepted claim has a different object for the same subject and predicate, the new claim cannot be promoted until every such difference is explicitly classified as a conflict or reviewed as compatible. Conflicts require a classification (`temporal`, `scope`, `definition`, or `unresolved`) and note; compatible differences require a compatibility note. A different value is not automatically a contradiction: for example, a relation may permit multiple owners or describe different time periods.

## Working at larger scale

Ten thousand documents with hundreds of pages each represent roughly a million or more pages; the current prototype is not a one-command extraction or production-scale storage system. Use the [scaling playbook](../skills/rdf-agent-memory/references/scaling-playbook.md): define competency questions, evaluate a representative sample, inventory immutable source versions, create citable text renditions, shard work, review in a bounded queue, version the ontology, and measure throughput, quality, file count, memory, and query latency before expanding. The prototype's local query command reloads the accepted Turtle tree into memory for each process. If measured limits are exceeded, keep Turtle and provenance as the portable record and build a separately managed query index as a projection.

For distribution, share or clone the tool repository and create a fresh project directory for each corpus and memory space. The repository's MIT license covers this implementation. It uses general RDF, Turtle, SPARQL, provenance, and multi-agent workflow concepts; concepts and standards are not bundled as third-party code. Preserve the included license when redistributing this repository, and record separate licenses for any third-party code, vocabularies, or source documents you add.

## Useful commands

```bash
.venv/bin/python scripts/memory.py status --memory-root /tmp/my-project/memory
.venv/bin/python scripts/memory.py query queries/claims-with-evidence.rq --memory-root /tmp/my-project/memory --json
.venv/bin/python scripts/memory.py validate --memory-root /tmp/my-project/memory
.venv/bin/python scripts/check_vendor_neutral.py
```

The checked-in example queries are read-only. `query` accepts local `.rq` files containing `SELECT` only; remote clauses and updates are rejected. The validation and neutral-language scan can be run before sharing a clone:

```bash
.venv/bin/python scripts/memory.py validate --memory-root /tmp/rdf-memory-demo/memory
.venv/bin/python scripts/check_vendor_neutral.py
git status --short
```

Review the complete diff before publishing. The demo sources are synthetic; do not publish internal corpora, renditions, working handoffs, or project memory.

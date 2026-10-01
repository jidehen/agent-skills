# Scaling playbook: from a small POC to a million-page corpus

This is a rollout plan, not a claim that the current scripts can process the
entire target corpus in one run. Ten thousand documents at 100–300 pages each
mean roughly **1–3 million pages**. Total bytes, OCR demand, candidate claim
count, review workload, and graph size cannot be inferred from page count
alone. Measure them on a representative sample before setting capacity or
delivery dates.

## 1. Define useful questions before an ontology

Choose one bounded domain and write 5–10 competency questions with expected
answer forms. Include multi-document joins, a time-scoped question, a disputed
fact, an “unknown” case, and a source trace. Decide what a correct answer must
show: entity identifiers, relationship, source version, evidence locator,
review status, and any conflict. Collect a seed set of 50–200 documents that
varies in format, length, date, terminology, quality, and sensitivity. Have
domain reviewers create a small gold set of answers and entity matches. This
sample is the basis for the first ontology terms and evaluation; agents should
not invent a large vocabulary from a full corpus in one pass.

## 2. Inventory immutable source versions

Create a manifest for each input version: stable document ID, revision ID,
relative path or approved location, media type, byte size, SHA-256, capture
time, access classification, and processing status. Detect duplicates by hash
but retain distinct document identities when business context differs. Never
overwrite the manifest entry for bytes that support an accepted claim. Link a
new version to the old version, for example with `prov:wasRevisionOf`; the
[PROV ontology](https://www.w3.org/TR/prov-o/) defines that revision relation.
Record whether a source version is present, restricted, superseded, or removed.

Do not put confidential documents, their text renditions, or derived memory in
the public skill repository. The public repository contains the workflow and
synthetic fixtures; a corporate clone creates a separate local memory and
corpus under approved storage and access controls.

## 3. Turn binary pages into citable text

For each source, keep the original bytes and produce a versioned UTF-8 text
rendition. Record the original and rendition digests, extraction method and
version, page boundaries, section headings, and character or line offsets.
For scanned pages, record OCR quality and route poor renditions to correction.
Use a locator that can be checked against the exact rendition while preserving
the original page reference for a human reviewer. A quotation alone is not a
stable locator: the same sentence may recur. An untracked copied transcript
must not become the source of an accepted claim.

The current POC validates `line:N` evidence in UTF-8 text. Support for other
formats requires a rendition step and explicit source-to-rendition links before
such documents can pass the same evidence gate.

## 4. Partition work and bound parallel agents

Shard the manifest by source version, then by page range when a document is
large. Keep every shard's source ID, revision, page range, and an idempotency
key. Begin with small batches that fit one worker's context and memory; measure
before increasing them. A 300-page document may need several page-range tasks
plus a document-level reconciliation task for references crossing ranges.

Run document analysts in parallel on separate shards. Start with 2–4 workers
and increase only while throughput improves without causing resource pressure
or review backlog. Separate roles: analysts propose claims; entity resolvers
propose identity links; ontology stewards manage vocabulary; evidence reviewers
check support; query analysts evaluate answers. Every role writes a bounded
handoff artifact. No analyst can promote its own unreviewed extraction.

Use one promotion writer per memory namespace. Workers may prepare staging
artifacts concurrently; the writer verifies source hashes, schema version,
unique claim IDs, evidence, review decision, and file consistency before
committing accepted Turtle and updating the index. This avoids lost updates
when many workers modify the same index or entity record.

The POC's one-accepted-claim-per-file layout makes individual reviews easy at
small scale. Millions of claims would also create millions of files and inodes,
so do not extrapolate that layout. At scale, compact accepted claims into
deterministic, immutable Turtle shards partitioned by source version, batch,
or time. Keep each claim's logical IRI and provenance links unchanged when its
physical file changes. The promotion writer should build and validate a new
shard, then atomically replace a manifest containing that shard's digest so
readers see a complete generation. Benchmark shard size, file count, parse
time, and the cost of rebuilding one shard after a correction before choosing
partition boundaries.

## 5. Resolve entities without forced merges

Build candidate aliases from names, identifiers, context, and source scope.
Keep a registry of canonical entity IDs, observed labels, source mentions,
possible matches, accepted merges, and rejected merges. A matching name alone
is not identity. Use weak possible-match links until a reviewer can establish
identity; reserve `owl:sameAs` for identities that truly denote the same thing.
Maintain a reversible merge history so an erroneous merge can be corrected
without losing source claims. Review high-degree entities and cross-document
joins first because their mistakes propagate widely.

## 6. Version the ontology and claims

Use the competency questions to define a small vocabulary with clear class and
predicate meanings, domains, ranges, and examples. Record an ontology version
on each extraction batch and accepted claim. Changes to a predicate's meaning
need a migration plan and query update; a label change alone should not create
a new IRI. Validate required claim fields and allowed relation types before
promotion. A shape language can express structural constraints, but does not
decide whether a statement follows from a document
([SHACL specification](https://www.w3.org/TR/shacl/)).

Keep staging and accepted graphs separate. Preserve contrary source claims,
their scopes and effective dates, plus the review that classified the
disagreement. Do not assume that different objects for one subject/predicate
always conflict: a relation may be multivalued or true at different times.

## 7. Make every stage restartable

Track states such as `inventoried → rendered → staged → reviewed → promoted`
per source version and shard. Write each output to a temporary location,
validate it, then atomically publish it. Store input digests, ontology version,
worker role, output digests, and completion timestamp in a checkpoint. On
restart, skip an already completed shard only when all inputs and the output
digest still match. Requeue stale or partial work. Promotion must be
idempotent and recoverable across its claim file, conflict review, and index
update; a per-file atomic write alone is not a transaction across several
files.

Keep rejected candidates and reviewer reasons. They are useful for improving
extraction but must remain outside the accepted query dataset. Maintain
append-only audit events or versioned diffs so a correction can be traced.

## 8. Evaluate quality and capacity continuously

On the gold set, measure at least:

| Measure | Why it matters |
| --- | --- |
| Text coverage and locator validity | Establish whether evidence can be checked against source versions. |
| Claim precision and missed-claim rate | Detect unsupported assertions and omitted relationships. |
| Entity merge/split precision | Expose false joins and duplicate identities. |
| Provenance and review completeness | Ensure every promoted claim has a source version, locator, digest, and decision. |
| Conflict detection and answer abstention | Show whether disputes and unknowns reach the user. |
| Competency-question accuracy | Test the actual cross-document answers against reviewer judgments. |
| Pages/hour, review minutes/page, bytes/page | Size compute and human effort from observed data. |
| Files/inodes, shard size, rebuild time | Prevent filesystem overhead from dominating large runs. |
| Peak memory, parse time, query p50/p95 | Determine when the local query method stops meeting the target. |

Structural completeness for accepted claims should be 100%; a missing source
hash or evidence locator is a failed promotion. Set semantic precision and
latency targets with the domain owner before the test, then report confidence
intervals and sample composition. Do not infer full-corpus quality from a
clean synthetic fixture. Include deliberately changed sources, duplicate
names, ambiguous aliases, contradictory dates, and missing pages in the test.

## 9. Keep permissions attached to derived knowledge

Carry source classification and access scope into renditions, candidates,
claims, graph partitions, caches, and query results. Querying across documents
must not reveal a restricted claim through a join or count. Keep security
domains separated when the local query layer cannot enforce row-level access.
Apply the same retention and deletion rules to derivatives and backups.
Review any proposed public export independently from the internal corpus.

## 10. Choose a persistent query projection from measurements

The current local query command loads Turtle into memory for each process. That
is useful for a small POC but is not a capacity claim for 1–3 million pages.
Benchmark representative shards: triples and accepted claims per page, index
build time, incremental update time, peak RAM, storage overhead, and query
latency under the expected concurrency. Extrapolate using measured ranges,
then run a larger pilot to test the extrapolation.

When reload or query costs exceed the agreed targets, build a replaceable
persistent RDF index from the canonical, versioned Turtle files. Verify
index freshness against file digests and rerun the competency queries after
every rebuild. Keep the files, ontology, provenance, and query tests portable;
the index is an acceleration layer rather than the sole copy of memory.

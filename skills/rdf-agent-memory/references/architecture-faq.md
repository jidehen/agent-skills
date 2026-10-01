# Architecture FAQ

This FAQ explains what the local RDF memory POC demonstrates and where its
guarantees end. The portable contract is `SKILL.md`; the files under `memory/`
remain the canonical record.

## What are RDF, Turtle, and SPARQL?

RDF is a data model: a graph of subject–predicate–object statements. A subject
and predicate are identified by IRIs; an object can be an IRI or a literal.
Turtle is one text syntax for writing that graph. SPARQL queries RDF graphs and
can join relationships across files after they are loaded into a dataset. A
Turtle file is therefore neither a database nor a query language. See the
[RDF data model](https://www.w3.org/TR/rdf11-concepts/),
[Turtle specification](https://www.w3.org/TR/turtle/), and
[SPARQL query specification](https://www.w3.org/TR/sparql11-query/).

In this POC, Turtle files are the durable source of truth. The local query
command loads the accepted files into an embedded RDF dataset and runs a SPARQL
`SELECT`. Its transient in-memory dataset can be rebuilt from the files.

## What is a semantic knowledge graph here?

The graph gives entities, relationships, and vocabulary terms stable IRIs and
explicit meanings. A document mention, a candidate assertion, a reviewed
claim, and the underlying source document are distinct resources. A claim
records its subject, predicate, object, evidence, source, and review. This lets
a query cross documents while still showing why a result was accepted.

“Semantic” does not mean that an agent understands the corpus automatically.
The ontology states what terms mean and how they relate; extraction, entity
resolution, evidence review, and query design determine whether the graph is
useful. RDF itself permits inconsistent claims. The workflow must preserve and
surface disagreements rather than silently choosing one answer.

## How does this differ from a vectorized ontology or OpenSearch index?

“Vectorized ontology” is not a single standard data model. It often means
embedding documents, concepts, or graph descriptions so similarity search can
find likely relevant material. OpenSearch vector search, for example, uses
nearest-neighbor search over indexed vectors
([OpenSearch documentation](https://docs.opensearch.org/latest/vector-search/vector-search-techniques/index/)).
Similarity is valuable for discovery, including synonyms and paraphrases. It
does not by itself assert a typed relationship, distinguish two people with the
same name, prove that a source supports a claim, or decide which of two
conflicting statements applies at a given time.

This POC makes those relationships and evidence links explicit. Its SPARQL
queries can answer exact joins such as “Which controls are owned by teams named
in both documents, and what line supports each ownership claim?” A vector
index could first retrieve candidate passages; the RDF layer could then answer
from reviewed claims. This is a complementary design, not a claim that one
index is better for every search task.

## Is a property graph less capable because it is not RDF?

No. Property graphs also represent nodes and relationships and may be the right
operational choice for a workload. **ISO/IEC 39075:2024 GQL** standardizes a
language for creating, querying, and maintaining property graphs
([ISO standard abstract](https://www.iso.org/standard/76120.html)). The fair
distinction is in the models and interchange conventions: RDF has W3C-defined
IRIs, triples, datasets, serializations, SPARQL, and related vocabularies. A
property graph commonly places labels and properties on nodes and edges and
uses its own mapping choices when exchanging RDF. Neither model automatically
produces a correct ontology or reliable provenance.

The POC should compare concrete tasks: time to answer cross-document questions,
evidence trace completeness, handling of conflicting claims, query latency,
review effort, and maintenance after a source revision. Do not compare only a
diagram or a headline count of nodes and edges.

## Why keep a claim resource instead of writing only a direct triple?

A direct triple such as `:teamA :owns :controlB` loses the reason it was
asserted. A named claim can point to the exact source rendition and locator,
the source hash, a review decision, and other claims it potentially conflicts
with. Query authors must join through accepted claim records when presenting
factual answers. Direct triples, if later materialized for speed, should be a
rebuildable projection from accepted claims; they must not become a second
unreviewed source of truth. The [PROV ontology](https://www.w3.org/TR/prov-o/)
defines general derivation and revision relationships that can be reused in
this record.

## Does provenance prove that a statement is true?

No. A path, digest, quotation, and locator prove traceability and can show that
the quoted text exists in a particular source version. They do not prove the
source is accurate or that the asserted relationship follows from the quote.
Reviewers must check the claim's meaning, scope, and time against the original
source. Reviews should record a decision and rationale. Conflicting supported
claims can both remain visible.

## Does validation or SHACL solve the factual review problem?

No. Turtle parsing checks syntax. The POC's validator can check local structural
rules such as required evidence links, hashes, and locators. SHACL is a W3C
language for expressing further graph constraints such as cardinality and
datatypes, but passing a shape does not establish factual truth or source
entailment ([SHACL specification](https://www.w3.org/TR/shacl/)). A future SHACL
gate can supplement the present validator; it cannot replace evidence review.

## Does the local query automatically infer new facts?

No. The local query path matches graph data loaded from files. An ontology
declaration, such as a subclass or a symmetric property, does not guarantee
that this command materializes implied triples. SPARQL's usual basic graph
matching and additional entailment regimes are specified separately
([SPARQL entailment regimes](https://www.w3.org/TR/sparql11-entailment/)). Write
queries against asserted facts, explicitly compute the needed closure, or add
a tested reasoner as a separate component. Never attribute an inferred result
to the POC unless that component has actually run and its derivation is shown.

## How do security, deletion, and source revisions work?

The local filesystem and its access controls protect the files. The POC does
not provide row-level authorization, a multi-user query service, or automatic
redaction. A confidential source, its extracted text, candidate claims,
accepted claims, and query results must remain within the same authorized
boundary. Do not publish a corpus or generated memory containing internal
content to a personal repository.

Treat a changed source as a new version with a new digest and an explicit
revision link. Preserve the version supporting an existing accepted claim, or
mark that claim for re-review if the old version cannot be retained. RDF IRIs
should keep the same intended referent over time; a path reused for new bytes
must not silently change what a source-version IRI denotes
([RDF and change over time](https://www.w3.org/TR/rdf11-concepts/#section-rdf-concepts)).
Deletion and retention policies must cover source copies, text renditions,
staging, accepted Turtle, indexes, backups, and exported results together.

## When should an organization add a persistent index?

When measured parse time, memory use, query latency, or concurrent access makes
reloading the files impractical. Keep Turtle exports, stable IRIs, provenance,
and versioned queries as the portable contract. A persistent index is then a
replaceable projection of the canonical files, subject to the same permissions
and freshness checks. See `scaling-playbook.md` for a measurement-led rollout.

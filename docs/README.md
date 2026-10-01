# RDF Agent Memory: the bigger picture

This project explores a practical question: can an agent team turn a large, changing document collection into knowledge that is **queryable, reviewable, and traceable back to exact source versions**, while keeping its memory portable across agent runtimes and storage products?

The skill's answer is a workflow, not a claim that an LLM can reliably read every page and invent a perfect ontology in one pass. Documents are inventoried and rendered into citable text. Agents propose entities and claims in bounded batches. A reviewer checks evidence and interpretation before promotion. Accepted claims and operating rules are written as Turtle, with local SPARQL queries over the accepted graph. The source files, ontology, review decisions, and query tests remain inspectable and portable.

## Start here

| Read | What it answers |
| --- | --- |
| [Architecture FAQ](architecture-faq.md) | Why RDF and Turtle? What does “semantic knowledge graph” mean? How does this compare with vectorized OpenSearch and property graphs? What do provenance, validation, and reasoning actually guarantee? |
| [Scaling playbook](scaling-playbook.md) | How would we approach 10,000 documents of hundreds of pages each? How do agents partition work, review claims, resolve entities, and know when the local query path has reached its limit? |
| [Usage guide](rdf-agent-memory.md) | How do I install the skill, run the synthetic demo, define an ontology, stage claims, and query accepted memory? |
| [Skill instructions](../skills/rdf-agent-memory/SKILL.md) | What operating contract should an agent follow? |

## The end-to-end idea

1. **Define questions.** Write the questions the graph must answer before creating a large vocabulary. Include ambiguous, conflicting, and unanswered cases.
2. **Version sources.** Inventory original files and digests. For binary files, register a citable text rendition without discarding the original.
3. **Propose, then review.** Agents return candidate claims with source quotes and locators. Staged candidates are not answers. Promotion requires a reviewer and an explicit disposition for differing values.
4. **Persist accepted knowledge.** Turtle holds the durable ontology, claims, provenance, rules, and session records. The local query dataset is rebuilt from those files.
5. **Answer with evidence.** SPARQL joins accepted claims across documents and returns source versions and review state; unresolved conflicts remain visible.
6. **Measure before scaling.** Use a representative gold set to measure extraction quality, reviewer effort, file count, query latency, and memory. A persistent index can later accelerate queries without replacing the portable record.

The included implementation is a **small, local proof of concept**. It supports UTF-8 text evidence with `line:N` locators and local read-only `SELECT` queries. It does not provide PDF extraction, automatic factual verification, inference, fine-grained multi-user authorization, or a demonstrated million-page capacity. The [scaling playbook](scaling-playbook.md) separates the architecture needed for that target from what the current scripts actually do.

## Why this is not just retrieval

Similarity search is useful for finding likely relevant passages. This workflow adds a separately reviewed statement layer: stable entity identifiers, typed relationships, source-version links, exact evidence, and recorded disagreements. The graph does not make a source true; it makes the basis and limitations of an answer inspectable. The [FAQ](architecture-faq.md) gives the fair comparison and cases where a hybrid design is preferable.

Keep confidential documents and generated project memory outside this public repository. A corporate deployment should use its approved storage, access controls, and review policy.

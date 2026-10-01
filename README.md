# Agent Skills

Practical, portable skills for agents doing real project work. Each skill combines clear operating instructions with the scripts, examples, and reference material needed to use it.

The collection starts with **RDF Agent Memory**: durable project memory and document knowledge graphs whose accepted claims retain their evidence and review history. More skills can join the same layout as they become useful and tested.

## Skill catalog

| Skill | Use it for | Status |
| --- | --- | --- |
| [RDF Agent Memory](skills/rdf-agent-memory/SKILL.md) | Remember project rules, build a document ontology, retrieve accepted claims with citations, review differing values | Working prototype; synthetic demo and automated tests |

## Try RDF Agent Memory

Requires Python 3.10 or newer. From the repository root:

```bash
cd skills/rdf-agent-memory
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python scripts/run_demo.py --output /tmp/rdf-memory-demo
.venv/bin/python scripts/memory.py query queries/claims-with-evidence.rq --memory-root /tmp/rdf-memory-demo/memory --json
.venv/bin/python scripts/memory.py validate --memory-root /tmp/rdf-memory-demo/memory
.venv/bin/python -m pytest
```

Choose a new demo output directory each time; initialization refuses to overwrite existing memory. The demo uses synthetic source documents and records accepted claims plus one reviewed unresolved conflict. After installing its Python dependency, this workflow runs locally without a graph server or network connection.

For your own data, initialize a separate project:

```bash
.venv/bin/python scripts/memory.py init --memory-root /absolute/path/to/my-project/memory
```

Keep project corpora, renditions, staged handoffs, and generated memory outside this repository.

## Use a skill with your agent

Copy or link the complete `skills/<skill-name>/` directory into your agent runtime's documented skill directory. Installing a Python package supplies code dependencies; it does not register a skill with a runtime. Installation and automatic discovery differ between runtimes.

You can also ask an agent to read the absolute path to `skills/rdf-agent-memory/SKILL.md` and follow it without installing the folder:

> Read the RDF Agent Memory skill. Initialize a fresh project outside the tool repository. Help me define a small ontology for policy ownership, then stage candidate claims with exact source quotes and line locators for review.

> Which team owns Policy 42? Cite the accepted claim's source version and evidence line, and include any reviewed conflict.

See the [usage guide](docs/rdf-agent-memory.md) for the full document workflow, [architecture FAQ](skills/rdf-agent-memory/references/architecture-faq.md) for design choices, and [scaling playbook](skills/rdf-agent-memory/references/scaling-playbook.md) for larger corpora.

## Repository layout

```text
skills/
  rdf-agent-memory/
    SKILL.md          # Agent instructions and activation description
    scripts/          # Local workflow tools
    assets/           # Initial memory templates
    examples/         # Synthetic sources and candidate handoffs
    queries/          # Read-only SPARQL examples
    references/       # Architecture and workflow details
    tests/            # Functional regression checks
docs/                 # Guides for people using the collection
```

Each skill is self-contained. Human-facing collection and installation information lives here; detailed skill guidance stays with its skill.

## What to expect

The RDF tool is a prototype, not a production capacity promise or an automatic fact-checker. Staging checks structure and consistency; a reviewer checks evidence and interpretation before promotion. Queries use accepted Turtle records, exclude staged candidates, and support local `SELECT` only. Ontology declarations do not automatically infer new facts.

Contributions are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md). Report vulnerabilities using [SECURITY.md](SECURITY.md). The implementation and instructions are [MIT licensed](LICENSE); source documents and any third-party additions need their own license checks.

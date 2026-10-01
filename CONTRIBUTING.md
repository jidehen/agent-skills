# Contributing

Start an issue describing the use case, expected result, and relevant constraints, or submit a focused pull request. Use synthetic examples that another person can run from a fresh clone.

## Add a skill

Create `skills/<kebab-case-name>/SKILL.md` with YAML `name` and `description` fields. The folder and name should match. Describe when the skill applies, its inputs, concrete workflow, failure handling, and how to verify its output. Bundle required scripts, references, and templates within that folder; keep human-facing setup documentation in `docs/` and add a catalog entry to the root README.

Keep instructions concise and link detailed references. Declare dependencies and distinguish demonstrated behavior from untested claims. Avoid assuming a particular agent vendor, proprietary service, or installed integration unless the skill actually requires it and documents that requirement.

The public FAQ and scaling playbook in `docs/` are mirrored under `skills/rdf-agent-memory/references/` so an installed skill remains self-contained. Update both copies together when changing those explanations.

## Check RDF Agent Memory changes

From `skills/rdf-agent-memory/`, after installing `.[dev]` in a virtual environment:

```bash
.venv/bin/python -m pytest
.venv/bin/python scripts/check_vendor_neutral.py
.venv/bin/python scripts/run_demo.py --output /tmp/rdf-memory-contribution-demo
.venv/bin/python scripts/memory.py validate --memory-root /tmp/rdf-memory-contribution-demo/memory
```

Use a new demo directory. Include relevant validation results and limitations in the pull request. Never include private source documents, generated project memory, credentials, or local machine paths in contributed examples.

By contributing, you agree to license your contributions under this repository's MIT license. Preserve attribution and document licenses for third-party material.

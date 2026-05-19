# Agent Harness

This repository uses an agent harness: a small set of committed instruction files that help Codex and similar coding agents understand the project, choose the right architecture, and run the right checks.

For Codex-oriented workflows, `AGENTS.md` is the canonical project instruction file: a predictable place to put project-specific instructions, conventions, and test commands.

## Files

| File | Purpose |
|---|---|
| `AGENTS.md` | Canonical project-wide instructions for coding agents |

## Maintenance Rules

- Keep `AGENTS.md` as the source of truth.
- Do not duplicate long architecture rationale in multiple instruction files.
- Update the harness when project commands, stack decisions, or repository structure change.
- Prefer stable instructions over volatile task notes.

## What Belongs Here

- Project mission and non-goals.
- Required technology choices.
- Commands for tests, linting, formatting, and builds.
- Safety rules around secrets and external systems.
- Architecture invariants that agents must preserve.
- Pointers to detailed docs.

## What Does Not Belong Here

- Long product requirements.
- Full API documentation.
- One-off task plans.
- Credentials, tokens, hostnames, or private deployment details.
- Instructions that conflict with committed architecture docs.

## References

- OpenAI `AGENTS.md` format: https://github.com/openai/agents.md

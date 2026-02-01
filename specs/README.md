# Specs

Specs define **target state** for capabilities. They stay ahead of code, serving as north stars for development. Specs are written in **present tense** as if the target state already exists.

## Purpose

- **Clarify intent** before writing code
- **Align stakeholders** on what "done" means
- **Prevent scope creep** with explicit non-goals
- **Track progress** via acceptance criteria

## Spec IDs

Each spec has a unique ID in the format `SPEC-XXX` (e.g., `SPEC-001`). When creating a new spec, assign the next available ID.

| ID | Capability |
|----|------------|
| [SPEC-001](SPEC-001/SPEC.md) | Configuration-Driven Strategies |

## Creating a New Spec

1. Copy `_TEMPLATE/SPEC.md` to a new directory named for your capability
2. Assign the next available spec ID
3. Fill in each section in present tense (describe how it *works*, not how it *will work*)
4. Commit and open for review

```bash
cp -r specs/_TEMPLATE specs/SPEC-XXX
# Edit specs/SPEC-XXX/SPEC.md
```

## Lifecycle

| Stage | Description |
|-------|-------------|
| **Aspirational** | Spec exists, no implementation started |
| **In Progress** | Issues linked, work underway |
| **Achieved** | All acceptance criteria met |

## Relationship to GitHub Issues

Specs are not issues. They describe *what* we're building; issues describe *how* we're building it.

- A single spec may require multiple issues to implement
- Issues reference their parent spec
- Specs link to implementing issues in their "Implementing Issues" table

## Guidelines

- **Be specific** — vague specs lead to vague implementations
- **Stay outcome-focused** — describe behavior, not implementation details
- **Update when learning** — specs evolve as understanding deepens
- **Archive, don't delete** — achieved specs document decisions made

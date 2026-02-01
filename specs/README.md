# Specs

Specs define **target state** for capabilities before implementation begins. They stay ahead of code, serving as north stars for development.

## Purpose

- **Clarify intent** before writing code
- **Align stakeholders** on what "done" means
- **Prevent scope creep** with explicit non-goals
- **Track progress** via acceptance criteria

## Creating a New Spec

1. Copy `_TEMPLATE/SPEC.md` to a new directory named for your capability
2. Fill in each section thoughtfully
3. Commit and open for review

```bash
cp -r specs/_TEMPLATE specs/my-capability
# Edit specs/my-capability/SPEC.md
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

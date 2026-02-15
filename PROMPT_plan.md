# Ralph Planning Phase

## Context Loading

0a. Study `specs/*` using parallel subagents to learn project specifications.
0b. Study @IMPLEMENTATION_PLAN.md to understand current progress and completed work.
0c. Study the project structure to understand the codebase.

## Planning Task

Your job is to create or update IMPLEMENTATION_PLAN.md with a detailed task list.

### Requirements

1. **Analyze the spec files** in `specs/` to understand what needs to be built
2. **Review existing code** to understand current state
3. **Create atomic tasks** - each task should be completable in one iteration
4. **Order tasks by dependency** - things that must be done first go first
5. **Mark completed tasks** with `[x]` and pending with `[ ]`

### Output Format

Update IMPLEMENTATION_PLAN.md with this structure:

```markdown
# Implementation Plan

## Completed

- [x] Task that was finished (iteration N)
- [x] Another completed task (iteration M)

## In Progress

- [ ] Current task being worked on

## Pending

- [ ] Next task to do
- [ ] Following task
- [ ] etc.

## Blocked

- [ ] Task waiting on external dependency (reason)
```

### Rules

1. Tasks must be ATOMIC - one clear action per task
2. Tasks must be TESTABLE - how do we know it's done?
3. Tasks must be ORDERED - dependencies resolved
4. Include test tasks for each feature task

### Exit Condition

When the plan is complete and ready for building:

1. Write "Planning complete. Ready for build phase."
2. Write "EXIT_SIGNAL" on its own line

If more planning iterations are needed, do NOT write EXIT_SIGNAL.

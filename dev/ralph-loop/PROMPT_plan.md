# Ralph Planning Phase

## Context Loading

0a. Study `specs/*` using parallel subagents to learn project specifications.
0b. Study @IMPLEMENTATION_PLAN.md to understand current progress and completed work.
0c. Study `src/` to understand the application source code structure.
0d. Study shared utilities in `shared/` or `src/lib/` if they exist.

## Planning Task

1. Using up to 100 parallel subagents, study both the specifications and existing code.
   Compare them to identify gaps between what's specified and what's implemented.

2. Create or update @IMPLEMENTATION_PLAN.md with:
   - A prioritized bullet-point list of tasks
   - Each task should be atomic and implementable in one iteration
   - Sort by priority (most critical first)
   - Include context on WHY each task matters

3. For each potential task, CONFIRM via code search that functionality is actually missing.
   Do NOT assume something is missing - search first.

## Output Format

Update IMPLEMENTATION_PLAN.md with the following structure:

```markdown
# Implementation Plan

## Completed

- [x] Task that was completed (brief description)

## In Progress

- [ ] Current task being worked on

## Pending (Priority Order)

- [ ] HIGH: Critical task description
- [ ] HIGH: Another critical task
- [ ] MEDIUM: Important but not blocking
- [ ] LOW: Nice to have improvements
```

## Critical Rules

- **PLAN ONLY** - Do NOT implement any code in this phase
- **VERIFY FIRST** - Search codebase before assuming functionality is missing
- **BE SPECIFIC** - Each task should be clear enough for another agent to implement
- **CAPTURE WHY** - Include reasoning for priority decisions
- **STAY FOCUSED** - Only plan for what's in the specifications

When planning is complete, commit the updated IMPLEMENTATION_PLAN.md with message:
"chore: update implementation plan"

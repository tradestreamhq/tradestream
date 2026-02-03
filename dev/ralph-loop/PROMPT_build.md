# Ralph Building Phase

## Context Loading

0a. Study `specs/*` using parallel subagents to understand specifications.
0b. Study @IMPLEMENTATION_PLAN.md to see the current task list and priorities.
0c. Application source code is in `src/`.
0d. Study any shared utilities in `shared/` or `src/lib/`.

## Building Task

1. Choose the MOST IMPORTANT incomplete task from @IMPLEMENTATION_PLAN.md
   - Select the highest priority item that is not marked complete
   - If blocked, choose the next available task

2. Before implementing, SEARCH the codebase to confirm the functionality doesn't already exist.
   - Don't assume something is not implemented
   - Check for similar patterns or partial implementations

3. Implement the task according to specifications:
   - Use up to 50 parallel subagents for reading/research
   - Use only 1 subagent for actual code changes and tests
   - Follow existing code patterns and conventions
   - Keep changes minimal and focused

4. Run tests after implementing:
   - Execute the project's test suite
   - If tests fail, fix the issues before proceeding
   - Add new tests if the feature requires them

5. Update @IMPLEMENTATION_PLAN.md:
   - Mark the completed task with [x]
   - Add any new discoveries or follow-up tasks
   - Update priorities if needed

6. When tests pass:
   - Stage relevant files (avoid staging secrets or large binaries)
   - Commit with a descriptive message
   - Push to the current branch

## Commit Message Format

```
type(scope): brief description

- Detail about what changed
- Why it changed

Co-Authored-By: Ralph Wiggum <ralph@example.com>
```

Types: feat, fix, refactor, test, docs, chore

## Critical Rules

- **ONE TASK PER ITERATION** - Complete one task fully before stopping
- **TESTS MUST PASS** - Never commit with failing tests
- **UPDATE THE PLAN** - Always reflect progress in IMPLEMENTATION_PLAN.md
- **SEARCH FIRST** - Verify functionality is missing before implementing
- **SINGLE SOURCE OF TRUTH** - Don't duplicate code or configurations
- **MINIMAL CHANGES** - Only change what's necessary for the task

## Completion Signals

When ALL tasks in IMPLEMENTATION_PLAN.md are complete, output:

```
RALPH_STATUS: complete
EXIT_SIGNAL: true
All tasks completed - project implementation finished.
```

This signals the loop to stop.

# Ralph Building Phase

## Context Loading

0a. Study `specs/*` using parallel subagents to understand specifications.
0b. Study @IMPLEMENTATION_PLAN.md to see the current task list and priorities.
0c. Study the project source code structure.

## Building Task

Your job is to implement the NEXT pending task from IMPLEMENTATION_PLAN.md.

### Workflow

1. **Read IMPLEMENTATION_PLAN.md** to find the next `[ ]` task
2. **Implement the task** - write code, create files, etc.
3. **Run tests** to verify the implementation works
4. **Update IMPLEMENTATION_PLAN.md** - mark task as `[x]` completed
5. **Commit changes** with a descriptive message

### Rules

1. **ONE TASK PER ITERATION** - do not try to do multiple tasks
2. **ALWAYS RUN TESTS** - verify before marking complete
3. **ALWAYS COMMIT** - each iteration should produce a commit
4. **UPDATE THE PLAN** - mark completed tasks with `[x]`

### Commit Message Format

```
feat/fix/test: Brief description of what was done

- Detail 1
- Detail 2

Iteration: N
```

### Error Handling

If you encounter an error:

1. Try to fix it in this iteration
2. If you cannot fix it, document the error in IMPLEMENTATION_PLAN.md
3. Move on - the next iteration will see the error and can try again

### Exit Conditions

When ALL tasks are complete:

1. Verify all tests pass
2. Write "All tasks complete. Implementation finished."
3. Write "EXIT_SIGNAL" on its own line

If there are still pending tasks, do NOT write EXIT_SIGNAL.

### Progress Indicators

At the end of each iteration, summarize:

- Task completed: [description]
- Tests status: PASS/FAIL
- Remaining tasks: N
- Next task: [description]

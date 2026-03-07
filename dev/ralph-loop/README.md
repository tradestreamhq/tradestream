# Ralph Wiggum Loop

Autonomous AI development loop based on [Geoffrey Huntley's technique](https://ghuntley.com/ralph/).

> "Ralph is a bash loop that feeds an AI's output (errors and all) back into itself until it dreams up the correct answer. It is brute force meets persistence."

## Quick Start

```bash
# 1. Copy files to your project
cp -r dev/ralph-loop/* /path/to/your/project/

# 2. Make executable
chmod +x ralph.sh

# 3. Create your specs in specs/ directory

# 4. Run planning phase first
./ralph.sh plan 5

# 5. Run build phase
./ralph.sh build 20
```

## How It Works

### Three Phases, Two Prompts, One Loop

1. **Define Requirements** - Create specification files in `specs/`
2. **Planning** - Run `./ralph.sh plan` to generate prioritized task list
3. **Building** - Run `./ralph.sh build` to implement tasks iteratively

### The Loop Cycle

```
┌─────────────────────────────────────────────────────────┐
│  1. Bash loop runs → feeds PROMPT.md to Claude          │
│  2. Claude studies IMPLEMENTATION_PLAN.md               │
│  3. Claude picks highest priority task                  │
│  4. Claude implements, tests, commits                   │
│  5. Claude updates IMPLEMENTATION_PLAN.md               │
│  6. Loop restarts with fresh context                    │
│  7. Repeat until all tasks complete                     │
└─────────────────────────────────────────────────────────┘
```

## Usage

```bash
# Planning mode - analyze specs and create task list
./ralph.sh plan           # Unlimited iterations
./ralph.sh plan 5         # Max 5 iterations

# Build mode - implement tasks from the plan
./ralph.sh build          # Unlimited iterations
./ralph.sh build 20       # Max 20 iterations

# Default (no args) = build mode, unlimited
./ralph.sh
```

## Configuration

Create `.ralphrc` in your project root:

```bash
# Model selection
CLAUDE_MODEL=opus         # sonnet (default), opus, haiku

# Rate limiting
MAX_RATE_PER_HOUR=100     # API calls per hour

# Circuit breaker thresholds
CIRCUIT_BREAKER_THRESHOLD=5   # Stop after N identical errors
NO_PROGRESS_THRESHOLD=3       # Stop after N loops with no progress

# Git behavior
ENABLE_GIT_PUSH=true      # Auto-push after commits

# Debugging
VERBOSE=true              # Enable detailed logging
```

## Reliability Features

### Rate Limiting

- Configurable calls per hour (default: 100)
- Automatic hourly reset
- Graceful waiting when limit reached

### Circuit Breaker

- Detects repeated identical errors
- Detects lack of progress (no commits/changes)
- Automatically stops to prevent runaway costs

### Exit Detection (Dual-Condition Gate)

Requires BOTH conditions to stop:

1. Multiple completion indicators in output
2. Explicit `EXIT_SIGNAL: true` from Claude

### Session Management

- Context preserved across iterations via session IDs
- Configurable session timeout

## Project Structure

```
your-project/
├── ralph.sh                  # Main loop script
├── PROMPT_plan.md           # Planning phase instructions
├── PROMPT_build.md          # Building phase instructions
├── IMPLEMENTATION_PLAN.md   # Task list (managed by Ralph)
├── .ralphrc                 # Configuration (optional)
├── specs/                   # Your specification files
│   ├── feature-a.md
│   └── feature-b.md
├── src/                     # Your source code
└── .ralph-logs/             # Iteration logs
```

## Writing Good Specs

Place specification files in `specs/`. Good specs include:

- Clear requirements (what, not how)
- Acceptance criteria
- Edge cases to handle
- Examples of expected behavior

## Tips for Success

1. **Start with planning** - Always run `plan` mode first
2. **Review the plan** - Check IMPLEMENTATION_PLAN.md before building
3. **Small specs** - Keep individual spec files focused
4. **Trust the loop** - Let Ralph iterate; don't micromanage
5. **Watch the logs** - Check `.ralph-logs/` if things go wrong
6. **Regenerate when stuck** - Delete IMPLEMENTATION_PLAN.md and re-plan

## Stopping the Loop

- `Ctrl+C` - Graceful stop
- `git reset --hard` - Revert all changes
- Delete IMPLEMENTATION_PLAN.md - Force re-planning

## Security

The script uses `--dangerously-skip-permissions` for autonomous operation.
Run in isolated environments:

- Use minimal API keys
- No access to sensitive data
- Restricted network where possible
- Consider Docker sandboxes

## References

- [Geoffrey Huntley - Ralph](https://ghuntley.com/ralph/)
- [Geoffrey Huntley - Everything is a Ralph Loop](https://ghuntley.com/loop/)
- [GitHub - how-to-ralph-wiggum](https://github.com/ghuntley/how-to-ralph-wiggum)
- [Frank Bria - ralph-claude-code](https://github.com/frankbria/ralph-claude-code)

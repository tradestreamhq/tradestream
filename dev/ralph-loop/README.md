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
CLAUDE_MODEL=opus         # opus (default), sonnet, haiku

# Rate limiting
MAX_RATE_PER_HOUR=100     # API calls per hour

# Circuit breaker thresholds
CIRCUIT_BREAKER_THRESHOLD=5   # Stop after N identical errors
NO_PROGRESS_THRESHOLD=3       # Stop after N loops with no progress

# Git behavior
ENABLE_GIT_PUSH=false     # Auto-push after commits

# Debugging
VERBOSE=false             # Enable detailed logging

# Timing
SLEEP_BETWEEN_ITERATIONS=5    # Seconds between iterations

# Continuous mode (unattended operation)
CONTINUOUS_MODE=true      # Run forever, ignore EXIT_SIGNAL
```

## Reliability Features

### Rate Limiting
- Configurable calls per hour (default: 100)
- **Persistent across restarts** - state saved to `.ralph-logs/.rate_limit`
- Automatic waiting when limit reached (sleeps until next hour)

### Circuit Breaker
- Detects repeated identical errors (via hash comparison)
- **Persistent error tracking** - hashes saved to `.ralph-logs/.error_hashes`
- Automatically stops to prevent runaway costs

### Progress Detection
- Tracks git commit count, file changes, and IMPLEMENTATION_PLAN.md hash
- **Persistent across restarts** - state saved to `.ralph-logs/.progress_tracker`
- Stops after N iterations with no detectable progress

### Continuous Mode
- When `CONTINUOUS_MODE=true` (default), loop runs forever
- Ignores EXIT_SIGNAL from Claude output
- Ideal for unattended operation - requires manual `Ctrl+C` to stop
- Set `CONTINUOUS_MODE=false` for legacy behavior (stops on completion)

### Real-Time Streaming
- Uses `--output-format stream-json` for real-time output
- See Claude's responses as they're generated (not buffered)
- Full output captured to `.ralph-logs/iteration_N.log`

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
    ├── iteration_1.log      # Text output
    ├── iteration_1.log.json # Full JSON stream
    ├── .rate_limit          # Rate limit state
    ├── .error_hashes        # Error hash history
    └── .progress_tracker    # Progress state
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
7. **Use continuous mode** - Set `CONTINUOUS_MODE=true` for fire-and-forget

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

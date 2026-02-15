#!/usr/bin/env bash
#
# Ralph Wiggum Loop - Autonomous AI Development Loop
# Based on Geoffrey Huntley's technique: https://ghuntley.com/ralph/
#
# Usage:
#   ./ralph.sh              # Build mode, unlimited iterations
#   ./ralph.sh plan         # Planning mode, unlimited
#   ./ralph.sh plan 5       # Planning mode, max 5 iterations
#   ./ralph.sh build 20     # Build mode, max 20 iterations
#   ./ralph.sh --help       # Show help
#
set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(pwd)}"

# Load project-specific config if exists
[[ -f "${PROJECT_ROOT}/.ralphrc" ]] && source "${PROJECT_ROOT}/.ralphrc"
[[ -f "${SCRIPT_DIR}/.ralphrc" ]] && source "${SCRIPT_DIR}/.ralphrc"

# Defaults (can be overridden in .ralphrc)
: "${CLAUDE_MODEL:=sonnet}"
: "${MAX_RATE_PER_HOUR:=100}"
: "${CIRCUIT_BREAKER_THRESHOLD:=5}"
: "${NO_PROGRESS_THRESHOLD:=3}"
: "${SESSION_TIMEOUT_HOURS:=24}"
: "${PROMPT_PLAN_FILE:=PROMPT_plan.md}"
: "${PROMPT_BUILD_FILE:=PROMPT_build.md}"
: "${IMPLEMENTATION_PLAN:=IMPLEMENTATION_PLAN.md}"
: "${LOG_DIR:=${PROJECT_ROOT}/.ralph-logs}"
: "${ENABLE_GIT_PUSH:=true}"
: "${VERBOSE:=false}"

# =============================================================================
# State tracking
# =============================================================================

ITERATION=0
CALLS_THIS_HOUR=0
HOUR_START=$(date +%s)
CONSECUTIVE_NO_PROGRESS=0
CONSECUTIVE_SAME_ERROR=0
LAST_ERROR_HASH=""
SESSION_ID=""

# =============================================================================
# Helpers
# =============================================================================

log() {
    local level="$1"
    shift
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $*"
    [[ -d "$LOG_DIR" ]] && echo "[$timestamp] [$level] $*" >> "${LOG_DIR}/ralph.log"
}

log_info()  { log "INFO" "$@"; }
log_warn()  { log "WARN" "$@"; }
log_error() { log "ERROR" "$@"; }
log_debug() { [[ "$VERBOSE" == "true" ]] && log "DEBUG" "$@" || true; }

print_banner() {
    cat << 'EOF'
    ____        __      __       _       ___
   / __ \____ _/ /___  / /_     | |     / (_)___ _____ ___  ______ ___
  / /_/ / __ `/ / __ \/ __ \    | | /| / / / __ `/ __ `/ / / / __ `__ \
 / _, _/ /_/ / / /_/ / / / /    | |/ |/ / / /_/ / /_/ / /_/ / / / / / /
/_/ |_|\__,_/_/ .___/_/ /_/     |__/|__/_/\__, /\__, /\__,_/_/ /_/ /_/
             /_/                         /____//____/
                                                          Loop v1.0
EOF
    echo ""
}

show_help() {
    cat << EOF
Ralph Wiggum Loop - Autonomous AI Development

USAGE:
    ./ralph.sh [MODE] [MAX_ITERATIONS]

MODES:
    plan        Run in planning mode (gap analysis, create TODO list)
    build       Run in build mode (implement tasks from plan) [default]

OPTIONS:
    MAX_ITERATIONS    Maximum loop iterations (0 = unlimited) [default: 0]
    --help, -h        Show this help message

EXAMPLES:
    ./ralph.sh                  # Build mode, unlimited
    ./ralph.sh plan             # Plan mode, unlimited
    ./ralph.sh plan 5           # Plan mode, max 5 iterations
    ./ralph.sh build 20         # Build mode, max 20 iterations

CONFIGURATION:
    Create a .ralphrc file in your project root to customize settings:

    CLAUDE_MODEL=opus           # Model: sonnet, opus, haiku
    MAX_RATE_PER_HOUR=100       # Rate limit per hour
    ENABLE_GIT_PUSH=true        # Auto-push after commits
    VERBOSE=true                # Enable debug logging

REQUIRED FILES:
    PROMPT_plan.md              # Planning phase prompt
    PROMPT_build.md             # Building phase prompt

See: https://ghuntley.com/ralph/ for more information
EOF
}

# =============================================================================
# Rate Limiting & Circuit Breaker
# =============================================================================

check_rate_limit() {
    local now=$(date +%s)
    local elapsed=$((now - HOUR_START))

    # Reset counter every hour
    if [[ $elapsed -ge 3600 ]]; then
        HOUR_START=$now
        CALLS_THIS_HOUR=0
        log_debug "Rate limit counter reset"
    fi

    if [[ $CALLS_THIS_HOUR -ge $MAX_RATE_PER_HOUR ]]; then
        local wait_time=$((3600 - elapsed))
        log_warn "Rate limit reached ($MAX_RATE_PER_HOUR/hour). Waiting ${wait_time}s..."
        sleep "$wait_time"
        HOUR_START=$(date +%s)
        CALLS_THIS_HOUR=0
    fi

    ((CALLS_THIS_HOUR++))
}

check_circuit_breaker() {
    # Check for repeated identical errors
    if [[ $CONSECUTIVE_SAME_ERROR -ge $CIRCUIT_BREAKER_THRESHOLD ]]; then
        log_error "Circuit breaker: $CONSECUTIVE_SAME_ERROR identical errors detected"
        log_error "Last error hash: $LAST_ERROR_HASH"
        return 1
    fi

    # Check for no progress
    if [[ $CONSECUTIVE_NO_PROGRESS -ge $NO_PROGRESS_THRESHOLD ]]; then
        log_error "Circuit breaker: $CONSECUTIVE_NO_PROGRESS iterations with no progress"
        return 1
    fi

    return 0
}

detect_progress() {
    local output="$1"

    # Check for git commits (strong progress indicator)
    if git log -1 --oneline 2>/dev/null | grep -q "$(date +%Y-%m-%d)" || \
       echo "$output" | grep -qiE "(committed|commit.*successfully|pushed|task.*completed|implemented)"; then
        CONSECUTIVE_NO_PROGRESS=0
        log_debug "Progress detected: commits or completions"
        return 0
    fi

    # Check for file modifications
    if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
        CONSECUTIVE_NO_PROGRESS=0
        log_debug "Progress detected: file modifications"
        return 0
    fi

    ((CONSECUTIVE_NO_PROGRESS++))
    log_warn "No progress detected (count: $CONSECUTIVE_NO_PROGRESS)"
    return 1
}

detect_error_loop() {
    local output="$1"

    # Extract error messages (filter out JSON false positives)
    local errors=$(echo "$output" | grep -iE "^(error|fatal|exception|failed):" | head -5 || true)

    if [[ -z "$errors" ]]; then
        CONSECUTIVE_SAME_ERROR=0
        LAST_ERROR_HASH=""
        return 0
    fi

    local error_hash=$(echo "$errors" | md5sum | cut -d' ' -f1)

    if [[ "$error_hash" == "$LAST_ERROR_HASH" ]]; then
        ((CONSECUTIVE_SAME_ERROR++))
        log_warn "Same error repeated (count: $CONSECUTIVE_SAME_ERROR)"
    else
        CONSECUTIVE_SAME_ERROR=1
        LAST_ERROR_HASH="$error_hash"
    fi
}

# =============================================================================
# Exit Detection (Dual-Condition Gate)
# =============================================================================

detect_completion() {
    local output="$1"
    local completion_score=0

    # Completion indicator phrases
    local -a completion_phrases=(
        "all tasks completed"
        "project complete"
        "implementation complete"
        "nothing left to implement"
        "no remaining tasks"
        "plan is empty"
        "EXIT_SIGNAL.*true"
        "RALPH_STATUS.*complete"
    )

    for phrase in "${completion_phrases[@]}"; do
        if echo "$output" | grep -qiE "$phrase"; then
            ((completion_score++))
            log_debug "Completion indicator found: $phrase"
        fi
    done

    # Require at least 2 indicators for exit
    if [[ $completion_score -ge 2 ]]; then
        log_info "Completion detected (score: $completion_score)"
        return 0
    fi

    return 1
}

# =============================================================================
# Claude Execution
# =============================================================================

run_claude() {
    local prompt_file="$1"
    local output_file="${LOG_DIR}/iteration_${ITERATION}.log"

    log_info "Executing Claude with prompt: $prompt_file"

    local claude_args=(
        "-p"
        "--dangerously-skip-permissions"
    )

    # Add model flag if specified
    [[ -n "$CLAUDE_MODEL" ]] && claude_args+=("--model" "$CLAUDE_MODEL")

    # Add session resume if we have one
    [[ -n "$SESSION_ID" ]] && claude_args+=("--resume" "$SESSION_ID")

    # Add verbose flag
    [[ "$VERBOSE" == "true" ]] && claude_args+=("--verbose")

    # Execute Claude
    local output
    if ! output=$(cat "$prompt_file" | claude "${claude_args[@]}" 2>&1 | tee "$output_file"); then
        log_error "Claude execution failed"
        echo "$output"
        return 1
    fi

    # Extract session ID if present (for session continuity)
    local new_session=$(echo "$output" | grep -oE "session_id[\"': ]+([a-zA-Z0-9_-]+)" | head -1 | grep -oE "[a-zA-Z0-9_-]{20,}" || true)
    [[ -n "$new_session" ]] && SESSION_ID="$new_session"

    echo "$output"
}

# =============================================================================
# Git Operations
# =============================================================================

git_push_if_enabled() {
    if [[ "$ENABLE_GIT_PUSH" != "true" ]]; then
        log_debug "Git push disabled"
        return 0
    fi

    local current_branch=$(git branch --show-current 2>/dev/null || echo "")

    if [[ -z "$current_branch" ]]; then
        log_warn "Not in a git repository or no branch"
        return 0
    fi

    log_info "Pushing to origin/$current_branch..."

    if ! git push origin "$current_branch" 2>/dev/null; then
        log_warn "Push failed, trying with -u flag..."
        git push -u origin "$current_branch" || {
            log_error "Failed to push to remote"
            return 1
        }
    fi

    log_info "Push successful"
}

# =============================================================================
# Main Loop
# =============================================================================

main() {
    local mode="build"
    local max_iterations=0
    local prompt_file=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            plan)
                mode="plan"
                shift
                ;;
            build)
                mode="build"
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            [0-9]*)
                max_iterations="$1"
                shift
                ;;
            *)
                log_error "Unknown argument: $1"
                show_help
                exit 1
                ;;
        esac
    done

    # Set prompt file based on mode
    if [[ "$mode" == "plan" ]]; then
        prompt_file="${PROJECT_ROOT}/${PROMPT_PLAN_FILE}"
    else
        prompt_file="${PROJECT_ROOT}/${PROMPT_BUILD_FILE}"
    fi

    # Validation
    if [[ ! -f "$prompt_file" ]]; then
        log_error "Prompt file not found: $prompt_file"
        log_error "Create $prompt_file with your project instructions"
        exit 1
    fi

    # Setup
    mkdir -p "$LOG_DIR"
    print_banner

    local current_branch=$(git branch --show-current 2>/dev/null || echo "N/A")

    cat << EOF
Configuration:
  Mode:             $mode
  Prompt:           $prompt_file
  Model:            $CLAUDE_MODEL
  Branch:           $current_branch
  Max iterations:   $([ "$max_iterations" -eq 0 ] && echo "unlimited" || echo "$max_iterations")
  Rate limit:       $MAX_RATE_PER_HOUR/hour
  Git push:         $ENABLE_GIT_PUSH
  Log directory:    $LOG_DIR

Press Ctrl+C to stop at any time
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EOF

    # Main loop
    while true; do
        # Check iteration limit
        if [[ $max_iterations -gt 0 && $ITERATION -ge $max_iterations ]]; then
            log_info "Reached maximum iterations: $max_iterations"
            break
        fi

        ((ITERATION++))
        echo ""
        echo "════════════════════════ ITERATION $ITERATION ════════════════════════"
        echo ""

        # Rate limiting
        check_rate_limit

        # Circuit breaker check
        if ! check_circuit_breaker; then
            log_error "Circuit breaker tripped. Stopping loop."
            log_error "Review logs at: $LOG_DIR"
            exit 1
        fi

        # Run Claude
        local output
        if ! output=$(run_claude "$prompt_file"); then
            log_error "Claude execution failed on iteration $ITERATION"
            detect_error_loop "$output"
            continue
        fi

        # Detect errors and progress
        detect_error_loop "$output"
        detect_progress "$output"

        # Check for completion
        if detect_completion "$output"; then
            log_info "Completion detected. Stopping loop."
            break
        fi

        # Push if enabled
        git_push_if_enabled || true

        # Brief pause between iterations
        sleep 2
    done

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "Ralph loop completed after $ITERATION iterations"
    log_info "Logs available at: $LOG_DIR"
}

# Trap for clean exit
trap 'echo ""; log_info "Interrupted by user"; exit 130' INT TERM

main "$@"

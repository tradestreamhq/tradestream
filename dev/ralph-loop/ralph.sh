#!/usr/bin/env bash
#
# Ralph Wiggum Loop - Autonomous AI Development Loop
# Based on Geoffrey Huntley's technique: https://ghuntley.com/ralph/
#
# The core idea: feed an AI's output (errors and all) back into itself
# until it dreams up the correct answer. Brute force meets persistence.
#
# Usage:
#   ./ralph.sh              # Build mode, unlimited iterations
#   ./ralph.sh plan         # Planning mode, unlimited
#   ./ralph.sh plan 5       # Planning mode, max 5 iterations
#   ./ralph.sh build 20     # Build mode, max 20 iterations
#

set -euo pipefail

# ============================================================================
# CONFIGURATION (override via .ralphrc in project root)
# ============================================================================

CLAUDE_MODEL="${CLAUDE_MODEL:-opus}"
MAX_RATE_PER_HOUR="${MAX_RATE_PER_HOUR:-100}"
CIRCUIT_BREAKER_THRESHOLD="${CIRCUIT_BREAKER_THRESHOLD:-5}"
NO_PROGRESS_THRESHOLD="${NO_PROGRESS_THRESHOLD:-3}"
ENABLE_GIT_PUSH="${ENABLE_GIT_PUSH:-false}"
VERBOSE="${VERBOSE:-false}"
SLEEP_BETWEEN_ITERATIONS="${SLEEP_BETWEEN_ITERATIONS:-5}"
# CONTINUOUS_MODE: When true, loop runs forever (ignores EXIT_SIGNAL)
# Used for unattended operation - requires manual stop (Ctrl+C)
CONTINUOUS_MODE="${CONTINUOUS_MODE:-true}"

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(pwd)}"
LOG_DIR="${PROJECT_ROOT}/.ralph-logs"
RATE_LIMIT_FILE="${LOG_DIR}/.rate_limit"
ERROR_HASH_FILE="${LOG_DIR}/.error_hashes"
PROGRESS_FILE="${LOG_DIR}/.progress_tracker"

# ============================================================================
# COLORS AND LOGGING
# ============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*"; }
log_debug()   { [[ "$VERBOSE" == "true" ]] && echo -e "${CYAN}[DEBUG]${NC} $*" || true; }

# ============================================================================
# BANNER
# ============================================================================

print_banner() {
    echo -e "${CYAN}"
    cat << 'EOF'
    ____        __      __       _       ___
   / __ \____ _/ /___  / /_     | |     / (_)___ _____ ___  ______ ___
  / /_/ / __ `/ / __ \/ __ \    | | /| / / / __ `/ __ `/ / / / __ `__ \
 / _, _/ /_/ / / /_/ / / / /    | |/ |/ / / /_/ / /_/ / /_/ / / / / / /
/_/ |_|\__,_/_/ .___/_/ /_/     |__/|__/_/\__, /\__,_/\__,_/_/ /_/ /_/
             /_/                         /____/

Loop v1.0
EOF
    echo -e "${NC}"
}

# ============================================================================
# RELIABILITY: Rate Limiting
# ============================================================================

check_rate_limit() {
    mkdir -p "$LOG_DIR"
    local current_hour=$(date +%Y%m%d%H)
    local count=0

    if [[ -f "$RATE_LIMIT_FILE" ]]; then
        local stored_hour=$(head -1 "$RATE_LIMIT_FILE" 2>/dev/null || echo "")
        if [[ "$stored_hour" == "$current_hour" ]]; then
            count=$(tail -1 "$RATE_LIMIT_FILE" 2>/dev/null || echo "0")
        fi
    fi

    if (( count >= MAX_RATE_PER_HOUR )); then
        log_error "Rate limit reached ($MAX_RATE_PER_HOUR/hour). Waiting for next hour..."
        local minutes_left=$(( 60 - $(date +%M) ))
        log_info "Sleeping for $minutes_left minutes..."
        sleep $((minutes_left * 60))
        count=0
    fi

    echo "$current_hour" > "$RATE_LIMIT_FILE"
    echo "$((count + 1))" >> "$RATE_LIMIT_FILE"
    log_debug "Rate: $((count + 1))/$MAX_RATE_PER_HOUR this hour"
}

# ============================================================================
# RELIABILITY: Circuit Breaker (detect stuck error loops)
# ============================================================================

check_circuit_breaker() {
    local error_output="$1"
    local error_hash=$(echo "$error_output" | grep -i "error\|fail\|exception" | md5sum | cut -d' ' -f1)

    mkdir -p "$LOG_DIR"
    touch "$ERROR_HASH_FILE"

    local consecutive_same=0
    if [[ -n "$error_hash" ]] && grep -q "$error_hash" "$ERROR_HASH_FILE" 2>/dev/null; then
        consecutive_same=$(grep -c "$error_hash" "$ERROR_HASH_FILE" || echo "0")
    fi

    if (( consecutive_same >= CIRCUIT_BREAKER_THRESHOLD )); then
        log_error "Circuit breaker triggered: Same error $consecutive_same times"
        log_error "Error pattern hash: $error_hash"
        return 1
    fi

    echo "$error_hash" >> "$ERROR_HASH_FILE"
    # Keep only last 20 hashes
    tail -20 "$ERROR_HASH_FILE" > "${ERROR_HASH_FILE}.tmp" && mv "${ERROR_HASH_FILE}.tmp" "$ERROR_HASH_FILE"
    return 0
}

# ============================================================================
# RELIABILITY: Progress Detection
# ============================================================================

track_progress() {
    mkdir -p "$LOG_DIR"

    # Track git commits
    local commit_count=$(git rev-list --count HEAD 2>/dev/null || echo "0")

    # Track file changes (staged + unstaged)
    local changed_files=$(git diff --name-only 2>/dev/null | wc -l || echo "0")
    local staged_files=$(git diff --cached --name-only 2>/dev/null | wc -l || echo "0")

    # Track IMPLEMENTATION_PLAN.md changes
    local plan_hash=""
    if [[ -f "${PROJECT_ROOT}/IMPLEMENTATION_PLAN.md" ]]; then
        plan_hash=$(md5sum "${PROJECT_ROOT}/IMPLEMENTATION_PLAN.md" | cut -d' ' -f1)
    fi

    local current_state="${commit_count}:${changed_files}:${staged_files}:${plan_hash}"

    if [[ -f "$PROGRESS_FILE" ]]; then
        local last_state=$(cat "$PROGRESS_FILE")
        if [[ "$current_state" == "$last_state" ]]; then
            local no_progress_count=$(cat "${PROGRESS_FILE}.count" 2>/dev/null || echo "0")
            no_progress_count=$((no_progress_count + 1))
            echo "$no_progress_count" > "${PROGRESS_FILE}.count"

            if (( no_progress_count >= NO_PROGRESS_THRESHOLD )); then
                log_error "No progress detected for $no_progress_count iterations"
                return 1
            fi
            log_warn "No progress detected (${no_progress_count}/${NO_PROGRESS_THRESHOLD})"
        else
            echo "0" > "${PROGRESS_FILE}.count"
            log_success "Progress detected!"
        fi
    fi

    echo "$current_state" > "$PROGRESS_FILE"
    return 0
}

# ============================================================================
# EXIT DETECTION (CONTINUOUS_MODE: never exit, for unattended operation)
# ============================================================================

check_exit_conditions() {
    local output="$1"

    # In CONTINUOUS_MODE, never exit - loop runs forever for unattended operation
    if [[ "$CONTINUOUS_MODE" == "true" ]]; then
        # Log status but DON'T exit
        if echo "$output" | grep -q "EXIT_SIGNAL"; then
            log_info "EXIT_SIGNAL detected but CONTINUOUS_MODE=true - ignoring"
            log_info "Loop will continue for unattended operation (Ctrl+C to stop)"
        fi

        # Check IMPLEMENTATION_PLAN.md status (informational only)
        if [[ -f "${PROJECT_ROOT}/IMPLEMENTATION_PLAN.md" ]]; then
            local pending=$(grep -c "^\s*-\s*\[ \]" "${PROJECT_ROOT}/IMPLEMENTATION_PLAN.md" 2>/dev/null || echo "0")
            local completed=$(grep -c "^\s*-\s*\[x\]" "${PROJECT_ROOT}/IMPLEMENTATION_PLAN.md" 2>/dev/null || echo "0")
            local blocked=$(grep -c "BLOCKED" "${PROJECT_ROOT}/IMPLEMENTATION_PLAN.md" 2>/dev/null || echo "0")

            log_info "Gate status: $completed completed, $pending pending, $blocked blocked"

            if (( pending == 0 && completed > 0 )); then
                log_info "All non-blocked gates completed - starting new verification cycle"
            fi
        fi

        return 1  # ALWAYS continue looping in continuous mode
    fi

    # Legacy mode (CONTINUOUS_MODE=false): Check for explicit EXIT_SIGNAL
    if echo "$output" | grep -q "EXIT_SIGNAL"; then
        log_success "EXIT_SIGNAL detected"

        # Verify completion markers exist too
        local completion_markers=0
        echo "$output" | grep -qi "all.*complete\|implementation.*complete\|task.*complete" && ((completion_markers++)) || true
        echo "$output" | grep -qi "no.*remaining\|nothing.*left\|finished" && ((completion_markers++)) || true

        if (( completion_markers >= 1 )); then
            log_success "Completion markers confirmed ($completion_markers)"
            return 0  # Exit the loop
        else
            log_warn "EXIT_SIGNAL found but no completion markers - continuing"
        fi
    fi

    # Check IMPLEMENTATION_PLAN.md for completion
    if [[ -f "${PROJECT_ROOT}/IMPLEMENTATION_PLAN.md" ]]; then
        local pending=$(grep -c "^\s*-\s*\[ \]" "${PROJECT_ROOT}/IMPLEMENTATION_PLAN.md" 2>/dev/null || echo "0")
        local completed=$(grep -c "^\s*-\s*\[x\]" "${PROJECT_ROOT}/IMPLEMENTATION_PLAN.md" 2>/dev/null || echo "0")

        if (( pending == 0 && completed > 0 )); then
            log_success "All tasks in IMPLEMENTATION_PLAN.md completed ($completed tasks)"
            return 0
        fi
        log_debug "Tasks: $completed completed, $pending pending"
    fi

    return 1  # Continue looping
}

# ============================================================================
# MAIN LOOP
# ============================================================================

run_loop() {
    local mode="${1:-build}"
    local max_iterations="${2:-0}"  # 0 = unlimited
    local iteration=0

    local prompt_file="${PROJECT_ROOT}/PROMPT_${mode}.md"
    if [[ ! -f "$prompt_file" ]]; then
        prompt_file="${SCRIPT_DIR}/PROMPT_${mode}.md"
    fi

    if [[ ! -f "$prompt_file" ]]; then
        log_error "Prompt file not found: PROMPT_${mode}.md"
        log_info "Create it in project root or ${SCRIPT_DIR}/"
        exit 1
    fi

    log_info "Mode: $mode"
    log_info "Prompt: $prompt_file"
    log_info "Max iterations: ${max_iterations:-unlimited}"
    log_info "Model: $CLAUDE_MODEL"
    log_info "Continuous mode: $CONTINUOUS_MODE"
    echo ""

    # Clean up old logs
    rm -f "${LOG_DIR}/.error_hashes" "${PROGRESS_FILE}.count" 2>/dev/null || true

    while true; do
        iteration=$((iteration + 1))

        # Check iteration limit
        if (( max_iterations > 0 && iteration > max_iterations )); then
            log_warn "Max iterations ($max_iterations) reached"
            break
        fi

        echo ""
        log_info "========== ITERATION $iteration =========="

        # Rate limiting
        check_rate_limit

        # Run Claude with the prompt
        local log_file="${LOG_DIR}/iteration_${iteration}.log"
        local output=""
        local exit_code=0

        log_info "Running Claude..."

        # Run claude with stream-json for real-time output
        # --include-partial-messages streams text chunks as they arrive
        # --verbose is required for stream-json with --print mode
        # -j flag joins output without adding newlines between values
        set +e
        cat "$prompt_file" | claude -p --dangerously-skip-permissions --model "$CLAUDE_MODEL" \
            --output-format stream-json --include-partial-messages --verbose 2>&1 | \
            tee "${log_file}.json" | \
            jq -j --unbuffered 'select(.type == "stream_event" and .event.type == "content_block_delta") | .event.delta.text // empty' 2>/dev/null | \
            tee "$log_file"
        exit_code=${PIPESTATUS[1]}
        # Add final newline after streaming output
        echo "" | tee -a "$log_file"
        set -e

        # Read captured output for exit condition checking
        output=$(cat "$log_file")

        # Check for Claude CLI errors
        if (( exit_code != 0 )); then
            log_error "Claude exited with code $exit_code"
            if ! check_circuit_breaker "$output"; then
                log_error "Circuit breaker tripped - stopping loop"
                exit 1
            fi
        fi

        # Check exit conditions
        if check_exit_conditions "$output"; then
            log_success "Exit conditions met - stopping loop"
            break
        fi

        # Track progress
        if ! track_progress; then
            log_error "No progress detected - stopping loop"
            exit 1
        fi

        # Circuit breaker check
        if ! check_circuit_breaker "$output"; then
            log_error "Circuit breaker tripped - stopping loop"
            exit 1
        fi

        # Optional: push changes
        if [[ "$ENABLE_GIT_PUSH" == "true" ]]; then
            git push 2>/dev/null || true
        fi

        log_info "Sleeping ${SLEEP_BETWEEN_ITERATIONS}s before next iteration..."
        sleep "$SLEEP_BETWEEN_ITERATIONS"
    done

    echo ""
    log_success "========== LOOP COMPLETE =========="
    log_info "Total iterations: $iteration"
    log_info "Logs available in: $LOG_DIR"
}

# ============================================================================
# USAGE
# ============================================================================

usage() {
    cat << EOF
Ralph Wiggum Loop - Autonomous AI Development

USAGE:
    $0 [mode] [max_iterations]

MODES:
    plan    - Planning phase (uses PROMPT_plan.md)
    build   - Building phase (uses PROMPT_build.md) [default]

OPTIONS:
    max_iterations  - Stop after N iterations (default: unlimited)

EXAMPLES:
    $0                  # Build mode, unlimited
    $0 plan             # Planning mode, unlimited
    $0 plan 5           # Planning mode, max 5 iterations
    $0 build 20         # Build mode, max 20 iterations

CONFIGURATION:
    Create .ralphrc in project root to override defaults:

    CLAUDE_MODEL=sonnet          # sonnet, opus, or haiku
    MAX_RATE_PER_HOUR=100        # Rate limit
    CIRCUIT_BREAKER_THRESHOLD=5  # Stop after N identical errors
    NO_PROGRESS_THRESHOLD=3      # Stop after N iterations with no progress
    ENABLE_GIT_PUSH=false        # Auto-push commits
    VERBOSE=false                # Debug logging
    SLEEP_BETWEEN_ITERATIONS=5   # Seconds between iterations
    CONTINUOUS_MODE=true         # Run forever (ignore EXIT_SIGNAL)

FILES:
    PROMPT_plan.md         - Planning phase prompt
    PROMPT_build.md        - Building phase prompt
    IMPLEMENTATION_PLAN.md - Task tracking (managed by Ralph)
    .ralph-logs/           - Iteration logs

EOF
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    # Load config if exists
    if [[ -f "${PROJECT_ROOT}/.ralphrc" ]]; then
        log_info "Loading config from .ralphrc"
        source "${PROJECT_ROOT}/.ralphrc"
    fi

    # Create log directory
    mkdir -p "$LOG_DIR"

    # Parse args
    case "${1:-}" in
        -h|--help|help)
            usage
            exit 0
            ;;
        plan|build)
            run_loop "$1" "${2:-0}"
            ;;
        "")
            run_loop "build" "0"
            ;;
        *)
            if [[ "$1" =~ ^[0-9]+$ ]]; then
                run_loop "build" "$1"
            else
                log_error "Unknown mode: $1"
                usage
                exit 1
            fi
            ;;
    esac
}

print_banner
trap 'echo ""; log_info "Interrupted by user"; exit 130' INT TERM
main "$@"

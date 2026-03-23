#!/usr/bin/env bash
# kill-browser-zombies.sh — Kills orphaned OpenClaw gateway and browser processes
# that hold ports and cause PortInUseError on next launch.
#
# Usage:
#   ./scripts/kill-browser-zombies.sh          # interactive (asks before killing)
#   ./scripts/kill-browser-zombies.sh --force   # non-interactive (kills immediately)
#
# What it cleans up:
#   - openclaw-gateway processes (browser automation gateway)
#   - Orphaned chromium/chrome processes spawned by automation
#   - OpenClaw webhook-proxy and dashboard server processes

set -euo pipefail

FORCE=false
if [[ "${1:-}" == "--force" ]]; then
    FORCE=true
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Collect PIDs of browser-related processes (owned by current user only)
collect_pids() {
    local pids=()

    # OpenClaw gateway processes
    while IFS= read -r pid; do
        [[ -n "$pid" ]] && pids+=("$pid")
    done < <(pgrep -u "$(id -u)" -f 'openclaw-gateway' 2>/dev/null || true)

    # OpenClaw webhook-proxy
    while IFS= read -r pid; do
        [[ -n "$pid" ]] && pids+=("$pid")
    done < <(pgrep -u "$(id -u)" -f 'openclaw.*webhook-proxy' 2>/dev/null || true)

    # OpenClaw dashboard server
    while IFS= read -r pid; do
        [[ -n "$pid" ]] && pids+=("$pid")
    done < <(pgrep -u "$(id -u)" -f 'openclaw.*server\.js' 2>/dev/null || true)

    # Orphaned chromium processes from automation (headless or remote-debugging)
    while IFS= read -r pid; do
        [[ -n "$pid" ]] && pids+=("$pid")
    done < <(pgrep -u "$(id -u)" -f 'chrom.*--remote-debugging-port' 2>/dev/null || true)

    # Deduplicate
    printf '%s\n' "${pids[@]}" | sort -un
}

kill_processes() {
    local pids=("$@")

    if [[ ${#pids[@]} -eq 0 ]]; then
        log_info "No browser zombie processes found. Ports are clear."
        return 0
    fi

    log_warn "Found ${#pids[@]} browser-related process(es):"
    for pid in "${pids[@]}"; do
        local cmdline
        cmdline=$(ps -p "$pid" -o args= 2>/dev/null | head -c 120) || cmdline="(already exited)"
        echo "  PID $pid: $cmdline"
    done

    if [[ "$FORCE" != true ]]; then
        echo ""
        read -rp "Kill these processes? [y/N] " answer
        if [[ ! "$answer" =~ ^[Yy]$ ]]; then
            log_info "Aborted."
            return 1
        fi
    fi

    # Graceful SIGTERM first
    for pid in "${pids[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    log_info "Sent SIGTERM to ${#pids[@]} process(es). Waiting 3s for graceful shutdown..."
    sleep 3

    # Force-kill survivors
    local survivors=()
    for pid in "${pids[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            survivors+=("$pid")
        fi
    done

    if [[ ${#survivors[@]} -gt 0 ]]; then
        log_warn "${#survivors[@]} process(es) still alive. Sending SIGKILL..."
        for pid in "${survivors[@]}"; do
            kill -9 "$pid" 2>/dev/null || true
        done
        sleep 1
    fi

    log_info "Cleanup complete. Browser ports should now be free."
}

# Verify ports are actually free after cleanup
verify_ports_free() {
    local blocked=false
    while IFS= read -r line; do
        if [[ -n "$line" ]]; then
            log_warn "Port still in use: $line"
            blocked=true
        fi
    done < <(ss -tlnp 2>/dev/null | grep 'openclaw' || true)

    if [[ "$blocked" == true ]]; then
        log_error "Some ports are still held. You may need to wait or check manually."
        return 1
    fi
    log_info "All OpenClaw ports verified free."
}

main() {
    log_info "Scanning for browser zombie processes..."
    mapfile -t pids < <(collect_pids)
    kill_processes "${pids[@]}"
    verify_ports_free
}

main

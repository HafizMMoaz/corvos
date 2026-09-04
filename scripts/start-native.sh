#!/usr/bin/env bash
# =============================================================================
# Corvos – Native Start Script (macOS & Linux)
# =============================================================================
# Starts the Corvos stack natively (no Docker) against a local PostgreSQL +
# Redis installation. Mirrors the roles in the Windows start-native.ps1.
#
# Usage:
#   ./start-native.sh              # api + worker + beat + zero + web
#   ./start-native.sh --api        # just the API server
#   ./start-native.sh --web        # just the Next.js dev server
#   ./start-native.sh --all        # all services (default)
#
# Logs are written to scripts/logs/<service>.{out,err}.
# A PID file is written for each service so you can stop them individually:
#   kill $(cat scripts/logs/<service>.pid)
#
# Or stop everything at once:
#   ./start-native.sh --stop
# =============================================================================
set -euo pipefail

# Resolve the repo root relative to this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOGS="$ROOT/scripts/logs"
mkdir -p "$LOGS"

# ── Colour helpers ──────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Colour

info()  { printf "${GREEN}[✓]${NC} %s\n" "$*"; }
warn()  { printf "${YELLOW}[!]${NC} %s\n" "$*"; }
err()   { printf "${RED}[✗]${NC} %s\n" "$*" >&2; }

# ── Service selection ───────────────────────────────────────────────────────
RUN_ALL=false; RUN_API=false; RUN_WORKER=false; RUN_BEAT=false
RUN_ZERO=false; RUN_WEB=false; STOP_ALL=false

if [[ $# -eq 0 ]]; then
  RUN_ALL=true
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)     RUN_ALL=true ;;
    --api)     RUN_API=true ;;
    --worker)  RUN_WORKER=true ;;
    --beat)    RUN_BEAT=true ;;
    --zero)    RUN_ZERO=true ;;
    --web)     RUN_WEB=true ;;
    --stop)    STOP_ALL=true ;;
    -h|--help)
      echo "Usage: $0 [--all|--api|--worker|--beat|--zero|--web|--stop]"
      exit 0
      ;;
    *)
      err "Unknown option: $1"
      echo "Usage: $0 [--all|--api|--worker|--beat|--zero|--web|--stop]"
      exit 1
      ;;
  esac
  shift
done

# ── Stop all running services ──────────────────────────────────────────────
stop_services() {
  local found=false
  for pidfile in "$LOGS"/*.pid; do
    [[ -f "$pidfile" ]] || continue
    local pid
    pid=$(cat "$pidfile")
    local name
    name=$(basename "$pidfile" .pid)
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null && info "Stopped $name (pid $pid)" || warn "Failed to stop $name (pid $pid)"
      found=true
    fi
    rm -f "$pidfile"
  done
  if [[ "$found" == false ]]; then
    warn "No running services found."
  else
    info "All services stopped."
  fi
}

if [[ "$STOP_ALL" == true ]]; then
  stop_services
  exit 0
fi

# ── Prerequisite checks ────────────────────────────────────────────────────
check_cmd() {
  if ! command -v "$1" &>/dev/null; then
    err "'$1' not found on PATH. $2"
    exit 1
  fi
}

check_cmd uv "Install uv: https://docs.astral.sh/uv/getting-started/installation/"
check_cmd pnpm "Install pnpm: https://pnpm.io/installation"

# ── Helper: start a service in the background ──────────────────────────────
start_svc() {
  local name="$1"; shift
  local workdir="$1"; shift
  local cmd=("$@")

  local out="$LOGS/$name.out"
  local errlog="$LOGS/$name.err"
  local pidfile="$LOGS/$name.pid"

  # Kill any previous instance
  if [[ -f "$pidfile" ]]; then
    local old_pid
    old_pid=$(cat "$pidfile")
    if kill -0 "$old_pid" 2>/dev/null; then
      kill "$old_pid" 2>/dev/null
      sleep 1
    fi
    rm -f "$pidfile"
  fi

  # Truncate old logs
  : > "$out"
  : > "$errlog"

  printf "${CYAN}[→]${NC} Starting %-10s in %s\n" "$name" "$workdir"

  (cd "$workdir" && "${cmd[@]}" >> "$out" 2>> "$errlog") &
  local pid=$!
  echo "$pid" > "$pidfile"

  # Quick liveness check
  sleep 1
  if kill -0 "$pid" 2>/dev/null; then
    info "Started $name (pid $pid)  logs: $out"
  else
    err "Failed to start $name – check $errlog"
    rm -f "$pidfile"
    return 1
  fi
}

# ── Backend API ─────────────────────────────────────────────────────────────
if [[ "$RUN_ALL" == true || "$RUN_API" == true ]]; then
  start_svc "api" "$ROOT/backend" uv run python main.py
  sleep 5  # let the API settle before the worker connects
fi

# ── Celery Worker ───────────────────────────────────────────────────────────
# On Linux/macOS the default prefork pool works fine (fork() is available).
# --autoscale dynamically scales between min and max workers.
if [[ "$RUN_ALL" == true || "$RUN_WORKER" == true ]]; then
  QUEUE="corvos"
  start_svc "worker" "$ROOT/backend" \
    uv run celery -A app.celery_app worker \
    --loglevel=info \
    --autoscale=4,1 \
    --prefetch-multiplier=1 \
    -Ofair \
    --queues="$QUEUE,$QUEUE.connectors,$QUEUE.gateway"
  sleep 3
fi

# ── Celery Beat ─────────────────────────────────────────────────────────────
if [[ "$RUN_ALL" == true || "$RUN_BEAT" == true ]]; then
  start_svc "beat" "$ROOT/backend" \
    uv run celery -A app.celery_app beat --loglevel=info
fi

# ── Zero-cache (real-time sync) ────────────────────────────────────────────
if [[ "$RUN_ALL" == true || "$RUN_ZERO" == true ]]; then
  # Read DATABASE_URL from web/.env (the connection string stays out of this
  # script and the process table).
  WEB_ENV="$ROOT/web/.env"
  if [[ ! -f "$WEB_ENV" ]]; then
    err "zero: web/.env not found – create it from web/.env.example"
  else
    PG_URL=$(grep '^DATABASE_URL=' "$WEB_ENV" | head -1 | cut -d= -f2-)
    if [[ -z "$PG_URL" ]]; then
      err "zero: DATABASE_URL not found in web/.env"
    else
      export ZERO_UPSTREAM_DB="${PG_URL}?sslmode=disable"
      export ZERO_CVR_DB="${PG_URL}?sslmode=disable"
      export ZERO_CHANGE_DB="${PG_URL}?sslmode=disable"
      export ZERO_REPLICA_FILE="$LOGS/zero.db"
      export ZERO_PORT="${ZERO_PORT:-4848}"
      export ZERO_APP_PUBLICATIONS="${ZERO_APP_PUBLICATIONS:-zero_publication}"
      export ZERO_AUTO_RESET="${ZERO_AUTO_RESET:-true}"
      export ZERO_ADMIN_PASSWORD="${ZERO_ADMIN_PASSWORD:-corvos-zero-admin}"
      export ZERO_QUERY_URL="${ZERO_QUERY_URL:-http://localhost:3000/api/zero/query}"
      export ZERO_MUTATE_URL="${ZERO_MUTATE_URL:-http://localhost:3000/api/zero/mutate}"
      export ZERO_QUERY_FORWARD_COOKIES="${ZERO_QUERY_FORWARD_COOKIES:-true}"

      start_svc "zero" "$ROOT/web" pnpm exec zero-cache
    fi
  fi
fi

# ── Web (Next.js dev) ──────────────────────────────────────────────────────
if [[ "$RUN_ALL" == true || "$RUN_WEB" == true ]]; then
  start_svc "web" "$ROOT/web" pnpm dev
fi

# ── Summary ─────────────────────────────────────────────────────────────────
echo ""
printf "${GREEN}═══════════════════════════════════════════════════════════${NC}\n"
printf "${GREEN} Corvos is starting natively${NC}\n"
printf "${GREEN}═══════════════════════════════════════════════════════════${NC}\n"
echo ""
echo "  Web app:     http://localhost:3000"
echo "  Backend API: http://localhost:8000"
echo "  Zero-cache:  http://localhost:${ZERO_PORT:-4848}"
echo "  Logs:        $LOGS/"
echo ""
echo "  Stop all:    $0 --stop"
echo "  Tail a log:  tail -f $LOGS/api.out"
echo ""

#!/usr/bin/env bash
# ui-tests-interactive.sh — Interactive host Playwright runner for test authoring.

set -Eeuo pipefail

usage() {
  cat <<'USAGE'
Usage: ui-tests-interactive.sh [OPTIONS] [-- <extra playwright args>]

Run Playwright in local interactive UI mode against a running rmlocal/rmdev stack.

Options:
  --screenshots      Enable screenshot-capture specs.
  --product NAME     Restrict suite to product(s) discovered by tests/ui/playwright.config.ts.
                     Comma-separated values are supported (e.g. takintegration,uiv2).
  --project NAME     Force compose project (rmlocal|rmdev).
  --base-url URL     Override UI base URL.
  --username NAME    Admin callsign to create.
                     Default: playwright-<unix timestamp>
  --skip-install     Skip npm/playwright install and reuse local setup.
  -y, --yes          Skip confirmation prompt.
  -h, --help         Show this help.

Any arguments after `--` are forwarded to `playwright test`.
USAGE
}

if [[ -t 1 ]]; then
  BOLD=$'\033[1m'    DIM=$'\033[2m'   RESET=$'\033[0m'
  GREEN=$'\033[32m'  RED=$'\033[31m'  CYAN=$'\033[36m' YELLOW=$'\033[33m'
else
  BOLD='' DIM='' RESET='' GREEN='' RED='' CYAN='' YELLOW=''
fi

info()  { printf '%s\n' "${DIM}│${RESET} $*"; }
step()  { printf '\n%s\n' "${CYAN}${BOLD}━━━ $*${RESET}"; }
ok()    { printf '%s\n' "${GREEN}${BOLD}✔ $*${RESET}"; }
warn()  { printf '%s\n' "${YELLOW}${BOLD}! $*${RESET}"; }
die()   { printf '%s\n' "${RED}${BOLD}✘ $*${RESET}" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
UI_DIR="$PROJECT_DIR/tests/ui"

FORCE_PROJECT=""
BASE_URL_OVERRIDE=""
USERNAME="playwright-$(date +%s)"
SCREENSHOTS=0
SKIP_INSTALL=0
AUTO_YES=0
EXTRA_ARGS=()
THEME="${RM_THEME:-default}"
PRODUCT_FILTER="${RM_UI_PRODUCTS:-${RM_UI_PRODUCT:-}}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --screenshots)  SCREENSHOTS=1; shift ;;
    --product)      PRODUCT_FILTER="${2:-}"; shift 2 ;;
    --project)      FORCE_PROJECT="${2:-}"; shift 2 ;;
    --base-url)     BASE_URL_OVERRIDE="${2:-}"; shift 2 ;;
    --username)     USERNAME="${2:-}"; shift 2 ;;
    --skip-install) SKIP_INSTALL=1; shift ;;
    -y|--yes)       AUTO_YES=1; shift ;;
    -h|--help)      usage; exit 0 ;;
    --)             shift; EXTRA_ARGS=("$@"); break ;;
    *)              die "Unknown argument: $1 (use --help)" ;;
  esac
done

command -v docker >/dev/null 2>&1 || die "docker is required"
command -v python3 >/dev/null 2>&1 || die "python3 is required"
command -v npm >/dev/null 2>&1 || die "npm is required"

OUTDIR="$(mktemp -d "${TMPDIR:-/tmp}/rm-ui-test.XXXXXX")"
cleanup() {
  rm -rf "$OUTDIR"
}
trap cleanup EXIT

provision_args=("$USERNAME" "$OUTDIR")
[[ -n "$FORCE_PROJECT" ]] && provision_args=(--project "$FORCE_PROJECT" "${provision_args[@]}")
[[ -n "$BASE_URL_OVERRIDE" ]] && provision_args=(--base-url "$BASE_URL_OVERRIDE" "${provision_args[@]}")

step "Step 1/3 · Creating test admin"
"$SCRIPT_DIR/create-admin.sh" "${provision_args[@]}"

META="$OUTDIR/admin.json"
PFX="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["pfx_path"],end="")' "$META")"
ADMIN_BASE_URL="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("base_url",""),end="")' "$META")"
[[ -s "$PFX" ]] || die "Expected certificate at $PFX but file is missing or empty"

if [[ -n "$BASE_URL_OVERRIDE" ]]; then
  TEST_BASE_URL="$BASE_URL_OVERRIDE"
else
  TEST_BASE_URL="$ADMIN_BASE_URL"
fi

step "Step 2/3 · Installing Playwright dependencies"
if [[ $SKIP_INSTALL -eq 0 ]]; then
  info "Directory: $UI_DIR"
  warn "Use --skip-install to reuse cached local dependencies."

  if [[ $AUTO_YES -eq 0 ]]; then
    warn "The following commands will be ran:"
    info "- npm install"
    info "- npx playwright install chromium"
    read -r -p "${DIM}│${RESET} Proceed? [y/N] " answer
    [[ "$answer" =~ ^[yY](es)?$ ]] || die "Cancelled by user"
  fi

  (cd "$UI_DIR" && npm install --no-audit --no-fund --silent)
  (cd "$UI_DIR" && npx playwright install chromium)
  ok "Dependencies installed."
else
  info "Skipping install (--skip-install)"
  ok "Using cached dependencies."
fi

export RM_ADMIN_META="$META"
export RM_ADMIN_PFX="$PFX"
export RM_THEME="$THEME"
export RM_BASE_URL="$TEST_BASE_URL"
[[ -n "$PRODUCT_FILTER" ]] && export RM_UI_PRODUCTS="$PRODUCT_FILTER"
[[ "${SCREENSHOTS:-0}" == "1" ]] && export SCREENSHOTS=1

PLAYWRIGHT_OUTPUT_DIR="$OUTDIR/test-results"
mkdir -p "$PLAYWRIGHT_OUTPUT_DIR"

HAS_OUTPUT_ARG=0
HAS_REPORTER_ARG=0
for arg in "${EXTRA_ARGS[@]}"; do
  [[ "$arg" == --output || "$arg" == --output=* ]] && HAS_OUTPUT_ARG=1
  [[ "$arg" == --reporter || "$arg" == --reporter=* ]] && HAS_REPORTER_ARG=1
done

playwright_args=(--ui --config "$UI_DIR/playwright.config.ts")
[[ "$HAS_OUTPUT_ARG" == "0" ]] && playwright_args+=(--output "$PLAYWRIGHT_OUTPUT_DIR")
[[ "$HAS_REPORTER_ARG" == "0" ]] && playwright_args+=(--reporter list)
playwright_args+=("${EXTRA_ARGS[@]}")

step "Step 3/3 · Running Playwright (interactive UI mode)"
if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
  info "Args: ${EXTRA_ARGS[*]}"
fi
if [[ -n "$PRODUCT_FILTER" ]]; then
  info "Product filter: $PRODUCT_FILTER"
fi

cd "$UI_DIR"
set +e
npx playwright test "${playwright_args[@]}"
PLAYWRIGHT_EXIT_CODE=$?
set -e

printf "\n"
[[ "${SCREENSHOTS:-0}" == "1" ]] && info "Screenshots: $UI_DIR/screenshots/$THEME/"
if [[ "$HAS_REPORTER_ARG" == "0" ]]; then
  info "Report: not generated (interactive mode uses --reporter list)"
else
  info "Report: $UI_DIR/playwright-report/index.html"
fi

if [[ $PLAYWRIGHT_EXIT_CODE -eq 0 ]]; then
  ok "All tests passed."
else
  die "Playwright tests failed (exit code $PLAYWRIGHT_EXIT_CODE)"
fi

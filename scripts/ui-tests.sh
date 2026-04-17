#!/usr/bin/env bash
# ui-tests.sh — Docker-first Playwright runner.

set -Eeuo pipefail

usage() {
  cat <<'USAGE'
Usage: ui-tests.sh [OPTIONS] [-- <extra playwright args>]

Run Playwright UI tests in Docker against a running rmlocal/rmdev stack.

Options:
  --screenshots      Enable screenshot-capture specs.
  --theme NAME       Theme label for screenshot output.
                     Default: $RM_THEME or "default"
  --langs LIST       Languages to capture in screenshot specs.
                     "all" or unset captures en,fi,sv. Pass a comma-separated
                     subset (e.g. "en" or "en,fi") to narrow.
                     Default: $SCREENSHOT_LANGS or "all"
  --product NAME     Restrict suite to product(s) discovered by tests/ui/playwright.config.ts.
                     Comma-separated values are supported (e.g. takintegration,uiv2).
  --project NAME     Force compose project (rmlocal|rmdev).
  --base-url URL     Override UI base URL.
  --username NAME    Admin callsign to create.
                     Default: playwright-<unix timestamp>
  --skip-build       Skip docker image build and reuse local image.
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
TEST_RESULTS_DIR="$UI_DIR/test-results"
REPORT_DIR="$UI_DIR/playwright-report"
SCREENSHOT_ROOT="$UI_DIR/screenshots"

FORCE_PROJECT=""
BASE_URL_OVERRIDE=""
USERNAME="playwright-$(date +%s)"
SCREENSHOTS=0
SKIP_BUILD=0
AUTO_YES=0
EXTRA_ARGS=()
UI_TEST_IMAGE="${RM_UI_TEST_IMAGE:-rasenmaeher-uitests}"
THEME="${RM_THEME:-default}"
PRODUCT_FILTER="${RM_UI_PRODUCTS:-${RM_UI_PRODUCT:-}}"
SCREENSHOT_LANGS="${SCREENSHOT_LANGS:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --screenshots) SCREENSHOTS=1; shift ;;
    --theme)      THEME="${2:-}"; shift 2 ;;
    --langs)      SCREENSHOT_LANGS="${2:-}"; shift 2 ;;
    --product)    PRODUCT_FILTER="${2:-}"; shift 2 ;;
    --project)    FORCE_PROJECT="${2:-}"; shift 2 ;;
    --base-url)   BASE_URL_OVERRIDE="${2:-}"; shift 2 ;;
    --username)   USERNAME="${2:-}"; shift 2 ;;
    --skip-build) SKIP_BUILD=1; shift ;;
    -y|--yes)     AUTO_YES=1; shift ;;
    -h|--help)    usage; exit 0 ;;
    --)           shift; EXTRA_ARGS=("$@"); break ;;
    *)            die "Unknown argument: $1 (use --help)" ;;
  esac
done

command -v docker >/dev/null 2>&1 || die "docker is required"
command -v python3 >/dev/null 2>&1 || die "python3 is required"

OUTDIR="$(mktemp -d "${TMPDIR:-/tmp}/rm-ui-test.XXXXXX")"
trap 'rm -rf "$OUTDIR"' EXIT

provision_args=("$USERNAME" "$OUTDIR")
[[ -n "$FORCE_PROJECT" ]] && provision_args=(--project "$FORCE_PROJECT" "${provision_args[@]}")
[[ -n "$BASE_URL_OVERRIDE" ]] && provision_args=(--base-url "$BASE_URL_OVERRIDE" "${provision_args[@]}")

step "Step 1/3 · Creating test admin"
"$SCRIPT_DIR/create-admin.sh" "${provision_args[@]}"

META="$OUTDIR/admin.json"
PFX="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["pfx_path"],end="")' "$META")"
COMPOSE_PROJECT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("compose_project",""),end="")' "$META")"
[[ -s "$PFX" ]] || die "Expected certificate at $PFX but file is missing or empty"
[[ -n "$COMPOSE_PROJECT" ]] || die "admin.json is missing compose_project"

# The provision script writes a host-absolute pfx_path into admin.json.
# Playwright runs inside Docker, so rewrite pfx_path to the mounted container path.
CONTAINER_META="$OUTDIR/admin.docker.json"
python3 - "$META" "$(basename "$PFX")" "$CONTAINER_META" <<'PY'
import json
import pathlib
import sys

src = pathlib.Path(sys.argv[1])
pfx_name = sys.argv[2]
dst = pathlib.Path(sys.argv[3])

meta = json.loads(src.read_text())
meta["pfx_path"] = f"/tmp/admin/{pfx_name}"
dst.write_text(json.dumps(meta))
PY

if [[ -n "$BASE_URL_OVERRIDE" ]]; then
  TEST_BASE_URL="$BASE_URL_OVERRIDE"
else
  TEST_BASE_URL="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("base_url",""),end="")' "$META")"
  [[ -n "$TEST_BASE_URL" ]] || TEST_BASE_URL="https://localmaeher.dev.pvarki.fi:4439"
fi

BASE_HOST="$(python3 -c 'import sys,urllib.parse as u; print((u.urlparse(sys.argv[1]).hostname or ""),end="")' "$TEST_BASE_URL")"
MTLS_HOST="mtls.$BASE_HOST"
[[ -n "$BASE_HOST" ]] || die "Could not parse hostname from base URL: $TEST_BASE_URL"

step "Step 2/3 · Building Playwright image"
if [[ $SKIP_BUILD -eq 0 ]]; then
  info "Image:  $UI_TEST_IMAGE"
  info "Source: $UI_DIR/Dockerfile"
  warn "Use --skip-build to reuse a cached image."

  if [[ $AUTO_YES -eq 0 ]]; then
    read -r -p "${DIM}│${RESET} Proceed? [y/N] " answer
    [[ "$answer" =~ ^[yY](es)?$ ]] || die "Cancelled by user"
  fi

  docker build -t "$UI_TEST_IMAGE" -f "$UI_DIR/Dockerfile" "$PROJECT_DIR"
  ok "Image built: $UI_TEST_IMAGE"
else
  info "Skipping build (--skip-build)"
  docker image inspect "$UI_TEST_IMAGE" >/dev/null 2>&1 || die "Image not found: $UI_TEST_IMAGE (run once without --skip-build)"
  ok "Using cached image: $UI_TEST_IMAGE"
fi

playwright_args=("${EXTRA_ARGS[@]}")

step "Step 3/3 · Running Playwright tests"
if [[ ${#playwright_args[@]} -gt 0 ]]; then
  info "Args: ${playwright_args[*]}"
fi

info "Resetting Playwright output directories"
docker run --rm --entrypoint /bin/sh \
  -e "SCREENSHOTS=$SCREENSHOTS" \
  -e "RM_THEME=$THEME" \
  -v "$UI_DIR:/workspace/tests/ui" \
  "$UI_TEST_IMAGE" -c '
    set -e
    rm -rf /workspace/tests/ui/test-results /workspace/tests/ui/playwright-report
    mkdir -p /workspace/tests/ui/test-results /workspace/tests/ui/playwright-report /workspace/tests/ui/screenshots
    if [ "${SCREENSHOTS:-0}" = "1" ]; then
      rm -rf "/workspace/tests/ui/screenshots/${RM_THEME:-default}"
      mkdir -p "/workspace/tests/ui/screenshots/${RM_THEME:-default}"
    fi
  '

docker_args=(
  --rm
  -v "$OUTDIR:/tmp/admin"
  -v "$TEST_RESULTS_DIR:/workspace/tests/ui/test-results"
  -v "$REPORT_DIR:/workspace/tests/ui/playwright-report"
  -v "$SCREENSHOT_ROOT:/workspace/tests/ui/screenshots"
  -e "RM_ADMIN_META=/tmp/admin/$(basename "$CONTAINER_META")"
  -e "RM_ADMIN_PFX=/tmp/admin/$(basename "$PFX")"
  -e "RM_THEME=$THEME"
  -e "RM_BASE_URL=$TEST_BASE_URL"
)

if [[ -n "$PRODUCT_FILTER" ]]; then
  docker_args+=( -e "RM_UI_PRODUCTS=$PRODUCT_FILTER" )
  info "Product filter: $PRODUCT_FILTER"
fi

if [[ ! "$BASE_HOST" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ && "$BASE_HOST" != "localhost" && "$BASE_HOST" != "::1" ]]; then
  docker_args+=(
    --add-host "$BASE_HOST:host-gateway"
    --add-host "$MTLS_HOST:host-gateway"
  )
fi

for proxy_var in HTTP_PROXY HTTPS_PROXY http_proxy https_proxy NO_PROXY no_proxy; do
  docker_args+=( -e "${proxy_var}=" )
done

[[ "$SCREENSHOTS" == "1" ]] && docker_args+=(-e "SCREENSHOTS=1")
if [[ "$SCREENSHOTS" == "1" && -n "$SCREENSHOT_LANGS" ]]; then
  docker_args+=(-e "SCREENSHOT_LANGS=$SCREENSHOT_LANGS")
  info "Screenshot languages: $SCREENSHOT_LANGS"
fi

set +e
docker run "${docker_args[@]}" "$UI_TEST_IMAGE" "${playwright_args[@]}"
PLAYWRIGHT_EXIT_CODE=$?
set -e

info "Normalizing artifact ownership to host user"
docker run --rm --entrypoint /bin/sh \
  -v "$UI_DIR:/workspace/tests/ui" \
  "$UI_TEST_IMAGE" -c "chown -R $(id -u):$(id -g) /workspace/tests/ui/test-results /workspace/tests/ui/playwright-report /workspace/tests/ui/screenshots"

printf "\n"
[[ "$SCREENSHOTS" == "1" ]] && info "Screenshots: $UI_DIR/screenshots/$THEME/"
info "Report:      $UI_DIR/playwright-report/index.html"

if [[ $PLAYWRIGHT_EXIT_CODE -eq 0 ]]; then
  ok "All tests passed."
else
  die "Playwright tests failed (exit code $PLAYWRIGHT_EXIT_CODE)"
fi

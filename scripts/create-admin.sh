#!/usr/bin/env bash
# create-admin.sh — Create a test admin user in a running
# rmlocal / rmdev stack. Writes a client certificate and a metadata
# JSON for downstream consumers (Playwright, dev scripts).

set -Eeuo pipefail

# --- helpers ---

usage() {
  cat <<'USAGE'
Usage: create-admin.sh [OPTIONS] <username> <outdir>

Create an admin user in the running stack and write:
  <outdir>/<username>.pfx   — client certificate (password: <username>)
  <outdir>/admin.json       — metadata: base_url, pfx_path, ui_login_code, …

Options:
  -p, --project NAME     Force compose project (rmlocal|rmdev). Auto-detect if unset.
  -b, --base-url URL     Override base URL (default: https://localmaeher.dev.pvarki.fi:4439).
  -h, --help             Show this help.
USAGE
}

if [[ -t 1 ]]; then
  BOLD=$'\033[1m'    DIM=$'\033[2m'   RESET=$'\033[0m'
  GREEN=$'\033[32m'  RED=$'\033[31m'  CYAN=$'\033[36m'
else
  BOLD='' DIM='' RESET='' GREEN='' RED='' CYAN=''
fi

info()  { printf '%s\n' "${DIM}│${RESET} $*"; }
step()  { printf '%s\n' "${CYAN}${BOLD}▸ $*${RESET}"; }
ok()    { printf '%s\n' "${GREEN}${BOLD}✔ $*${RESET}"; }
die()   { printf '%s\n' "${RED}${BOLD}✘ $*${RESET}" >&2; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

json_field() {
  python3 -c \
    'import json, sys; print(json.load(sys.stdin).get(sys.argv[1], ""))' \
    "$1" 2>/dev/null
}

api_post_json() {
  local endpoint="$1"
  local payload="$2"
  local auth_token="${3:-}"
  local response_file http_status
  local -a auth_args=()

  response_file="$(mktemp "$TMPDIR_WORK/api-response.XXXXXX.json")"

  if [[ -n "$auth_token" ]]; then
    auth_args=(-H "Authorization: Bearer $auth_token")
  fi

  http_status="$(curl "${CURL_COMMON[@]}" -o "$response_file" -w '%{http_code}' -X POST \
    "$BASE_URL$endpoint" \
    -H 'Content-Type: application/json' \
    "${auth_args[@]}" \
    -d "$payload")" || die "Request failed: POST $endpoint"

  if [[ ! "$http_status" =~ ^2[0-9][0-9]$ ]]; then
    die "POST $endpoint failed (HTTP $http_status): $(cat "$response_file")"
  fi

  cat "$response_file"
}

# --- argument parsing ---

USERNAME=""
OUTDIR=""
FORCE_PROJECT=""
BASE_URL_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--project)   FORCE_PROJECT="${2:-}"; shift 2 ;;
    -b|--base-url)  BASE_URL_OVERRIDE="${2:-}"; shift 2 ;;
    -h|--help)      usage; exit 0 ;;
    -*)             die "Unknown option: $1" ;;
    *)
      if [[ -z "$USERNAME" ]]; then
        USERNAME="$1"
      elif [[ -z "$OUTDIR" ]]; then
        OUTDIR="$1"
      else
        die "Unexpected positional argument: $1"
      fi
      shift
      ;;
  esac
done

[[ -n "$USERNAME" && -n "$OUTDIR" ]] || { usage; exit 1; }
[[ "$USERNAME" =~ ^[A-Za-z0-9._-]+$ ]] || die "Invalid username (allowed: A-Z a-z 0-9 . _ -)"

# --- command checks ---

for cmd in docker curl python3 stat mktemp; do
  require_cmd "$cmd"
done

# --- project + paths ---

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

mkdir -p "$OUTDIR"
OUTDIR="$(cd "$OUTDIR" && pwd)"

TMPDIR_WORK="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_WORK"' EXIT

detect_project() {
  if [[ -n "$FORCE_PROJECT" ]]; then
    case "$FORCE_PROJECT" in
      rmlocal) COMPOSE_PROJECT=rmlocal; COMPOSE_FILES=(-f "$PROJECT_DIR/docker-compose-local.yml") ;;
      rmdev)   COMPOSE_PROJECT=rmdev;   COMPOSE_FILES=(-f "$PROJECT_DIR/docker-compose-local.yml" -f "$PROJECT_DIR/docker-compose-dev.yml") ;;
      *)       die "Unknown --project: $FORCE_PROJECT (expected rmlocal|rmdev)" ;;
    esac
    return
  fi

  if docker compose -p rmlocal ps --format '{{.Name}}' 2>/dev/null | grep -q rmapi; then
    COMPOSE_PROJECT=rmlocal
    COMPOSE_FILES=(-f "$PROJECT_DIR/docker-compose-local.yml")
  elif docker compose -p rmdev ps --format '{{.Name}}' 2>/dev/null | grep -q rmapi; then
    COMPOSE_PROJECT=rmdev
    COMPOSE_FILES=(-f "$PROJECT_DIR/docker-compose-local.yml" -f "$PROJECT_DIR/docker-compose-dev.yml")
  else
    die "No running stack found (looked for rmlocal / rmdev)"
  fi
}

detect_project
dc() { docker compose -p "$COMPOSE_PROJECT" "${COMPOSE_FILES[@]}" "$@"; }

BASE_URL="${BASE_URL_OVERRIDE:-https://localmaeher.dev.pvarki.fi:4439}"
CURL_COMMON=(
  --silent
  --show-error
  --insecure
  --retry 5
  --retry-connrefused
  --retry-delay 2
  --connect-timeout 5
  --max-time 60
)

info "Stack:    $COMPOSE_PROJECT"
info "Base URL: $BASE_URL"
info "User:     $USERNAME"

new_code() {
  dc exec -T rmapi /bin/bash -c \
    'rasenmaeher_api addcode || /.venv/bin/rasenmaeher_api addcode' 2>/dev/null \
    | tr -d '[:space:]'
}

step "Generating first admin code …"
setup_code="$(new_code)"
[[ -n "$setup_code" ]] || die "Could not generate code from rmapi container"

step "Exchanging code for admin token …"
resp="$(api_post_json "/api/v1/token/code/exchange" "{\"code\":\"$setup_code\"}")"
admin_jwt="$(json_field jwt <<<"$resp")"
[[ -n "$admin_jwt" ]] || die "Admin token exchange failed: $resp"

step "Creating user '$USERNAME' …"
_admin_resp_file="$(mktemp "$TMPDIR_WORK/admin-resp.XXXXXX.json")"
_admin_status="$(curl "${CURL_COMMON[@]}" -o "$_admin_resp_file" -w '%{http_code}' -X POST \
  "$BASE_URL/api/v1/firstuser/add-admin" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $admin_jwt" \
  -d "{\"callsign\":\"$USERNAME\"}")" || die "Request failed: POST /api/v1/firstuser/add-admin"
if [[ "$_admin_status" == "403" ]]; then
  die "Username '$USERNAME' is likely already taken (HTTP 403). Try using --username to choose a different name."
elif [[ ! "$_admin_status" =~ ^2[0-9][0-9]$ ]]; then
  die "POST /api/v1/firstuser/add-admin failed (HTTP $_admin_status): $(cat "$_admin_resp_file")"
fi
resp="$(cat "$_admin_resp_file")"
user_exchange_code="$(json_field jwt_exchange_code <<<"$resp")"
[[ -n "$user_exchange_code" ]] || die "User creation failed: $resp"

resp="$(api_post_json "/api/v1/token/code/exchange" "{\"code\":\"$user_exchange_code\"}")"
user_jwt="$(json_field jwt <<<"$resp")"
[[ -n "$user_jwt" ]] || die "User token exchange failed: $resp"

step "Downloading client certificate …"
pfx_path="$OUTDIR/${USERNAME}.pfx"
http_status="$(curl "${CURL_COMMON[@]}" \
  -o "$pfx_path" -w '%{http_code}' \
  -H "Authorization: Bearer $user_jwt" \
  "$BASE_URL/api/v1/enduserpfx/${USERNAME}.pfx")" || die "Certificate download failed"

[[ "$http_status" == "200" ]] || { cat "$pfx_path" >&2; die "Certificate download failed (HTTP $http_status)"; }
pfx_size="$(stat -c%s "$pfx_path" 2>/dev/null || stat -f%z "$pfx_path")"
[[ "$pfx_size" -gt 0 ]] || die "Certificate download was empty"
info "Certificate: $pfx_size bytes"

# The first admin code was consumed above. Generate a second code for the UI
# login form so Playwright can use it.
ui_login_code="$(new_code)"
[[ -n "$ui_login_code" ]] || die "Could not generate UI login code"

cat > "$OUTDIR/admin.json" <<JSON
{
  "username": "$USERNAME",
  "pfx_path": "$pfx_path",
  "pfx_passphrase": "$USERNAME",
  "base_url": "$BASE_URL",
  "ui_login_code": "$ui_login_code",
  "compose_project": "$COMPOSE_PROJECT"
}
JSON

ok "User '$USERNAME' created."

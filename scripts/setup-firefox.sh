#!/usr/bin/env bash
# setup-firefox.sh — Create a first admin in a rmlocal/rmdev and
# install the certificate to firefox profiles

set -Eeuo pipefail

# --- helpers ---

usage() {
  cat <<'USAGE'
Usage: setup-firefox.sh [OPTIONS] <username>

Create a user in the local Rasenmaeher stack and import their client
certificate into Firefox.

Options:
  -y, --yes       Skip the confirmation prompt
  --no-open       Don't open Firefox after import
  -h, --help      Show this help
USAGE
}

info() { printf '[INFO] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }
die()  { printf '[ERROR] %s\n' "$*" >&2; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

json_file_field() {
  python3 -c \
    'import json, sys; print(json.load(open(sys.argv[1])).get(sys.argv[2], ""))' \
    "$1" "$2" 2>/dev/null
}

nss_db_prefix() {
  local profile="$1"
  if [[ -f "$profile/cert9.db" ]]; then
    printf 'sql:'
  elif [[ -f "$profile/cert8.db" ]]; then
    printf 'dbm:'
  else
    return 1
  fi
}

# --- argument parsing ---

AUTO_YES=0
OPEN_BROWSER=1
USERNAME=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -y|--yes)      AUTO_YES=1 ;;
    --no-open)     OPEN_BROWSER=0 ;;
    -h|--help)     usage; exit 0 ;;
    -*)            die "Unknown option: $1" ;;
    *)
      [[ -z "$USERNAME" ]] || die "Only one username allowed"
      USERNAME="$1"
      ;;
  esac
  shift
done

if [[ -z "$USERNAME" ]]; then
  usage
  exit 1
fi

[[ "$USERNAME" =~ ^[A-Za-z0-9._-]+$ ]] || die "Invalid username (allowed: A-Z a-z 0-9 . _ -)"

# --- command checks ---

for cmd in docker python3 find stat certutil pk12util pgrep; do
  require_cmd "$cmd"
done

if [[ $OPEN_BROWSER -eq 1 ]] && ! command -v firefox >/dev/null 2>&1; then
  warn "firefox not found in PATH — skipping auto-open"
  OPEN_BROWSER=0
fi

# --- project + paths ---

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

TMPDIR_WORK="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_WORK"' EXIT

if docker compose -p rmlocal ps --format '{{.Name}}' 2>/dev/null | grep -q rmapi; then
  COMPOSE_PROJECT=rmlocal
elif docker compose -p rmdev ps --format '{{.Name}}' 2>/dev/null | grep -q rmapi; then
  COMPOSE_PROJECT=rmdev
else
  die "No running stack found (looked for rmlocal / rmdev)"
fi

BASE_URL="https://localmaeher.dev.pvarki.fi:4439"
CERT_NICKNAME="rasenmaeher-${USERNAME}"

# --- firefox profiles ---

FIREFOX_PROFILES=()
for dir in \
  "$HOME/.mozilla/firefox" \
  "$HOME/.config/mozilla/firefox" \
  "$HOME/snap/firefox/common/.mozilla/firefox"
do
  [[ -d "$dir" ]] || continue
  while IFS= read -r -d '' profile; do
    if [[ -f "$profile/cert9.db" || -f "$profile/cert8.db" ]]; then
      FIREFOX_PROFILES+=("$profile")
    fi
  done < <(find "$dir" -mindepth 1 -maxdepth 1 -type d -print0)
done

[[ ${#FIREFOX_PROFILES[@]} -gt 0 ]] || die "No Firefox profiles with a certificate store found"

if pgrep -x firefox >/dev/null 2>&1; then
  warn "Firefox appears to be running; certificate DBs may be locked during import"
fi

# --- confirmation ---

info "Stack:    $COMPOSE_PROJECT"
info "Base URL: $BASE_URL"
info "User:     $USERNAME"
info ""
info "Certificate '$CERT_NICKNAME' will be installed into:"
for profile in "${FIREFOX_PROFILES[@]}"; do
  info "  $(basename "$profile")"
done
info ""
info "Any existing certificate with the same name will be removed first."

if [[ $AUTO_YES -eq 0 ]]; then
  read -r -p "[INFO] Proceed? [y/N] " answer
  [[ "$answer" =~ ^[yY](es)?$ ]] || die "Cancelled by user"
fi

info "[1/3] Creating admin and client certificate ..."
"$SCRIPT_DIR/create-admin.sh" \
  --project "$COMPOSE_PROJECT" \
  --base-url "$BASE_URL" \
  "$USERNAME" "$TMPDIR_WORK" >/dev/null

meta_path="$TMPDIR_WORK/admin.json"
pfx_path="$(json_file_field "$meta_path" pfx_path)"
[[ -s "$pfx_path" ]] || die "create-admin.sh did not produce a certificate"
pfx_size="$(stat -c%s "$pfx_path" 2>/dev/null || stat -f%z "$pfx_path")"
info "  Certificate: $pfx_size bytes"

# --- import into Firefox ---

info "[2/3] Importing certificate into Firefox profiles ..."

for profile in "${FIREFOX_PROFILES[@]}"; do
  profile_name="$(basename "$profile")"
  db_prefix="$(nss_db_prefix "$profile")" || die "Unsupported Firefox cert DB format in profile $profile_name"
  db_spec="${db_prefix}${profile}"

  # Remove any previous certs with the same nicknames to avoid duplicates.
  for nick in "$USERNAME" "$CERT_NICKNAME"; do
    while certutil -L -d "$db_spec" -n "$nick" >/dev/null 2>&1; do
      certutil -F -d "$db_spec" -n "$nick" 2>/dev/null || \
        certutil -D -d "$db_spec" -n "$nick" 2>/dev/null || break
    done
  done

  pk12util -i "$pfx_path" -d "$db_spec" -n "$CERT_NICKNAME" \
    -W "$USERNAME" -K "" >/dev/null 2>&1 \
    || die "Certificate import failed in profile $profile_name"

  certutil -L -d "$db_spec" -n "$USERNAME" >/dev/null 2>&1 \
    || certutil -L -d "$db_spec" -n "$CERT_NICKNAME" >/dev/null 2>&1 \
    || die "Certificate verification failed in profile $profile_name"

  info "  Imported into $profile_name"
done

# --- open browser ---

if [[ $OPEN_BROWSER -eq 1 ]]; then
  info "[3/3] Opening Firefox ..."
  firefox "$BASE_URL" &>/dev/null &
  disown
else
  info "[3/3] Skipped opening Firefox (--no-open)"
fi

info "Done. User '$USERNAME' is enrolled."

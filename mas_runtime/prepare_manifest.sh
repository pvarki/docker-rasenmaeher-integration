#!/bin/bash
set -euo pipefail

# Miniwerk's Matrix manifest predates MAS's Keycloak registration fields.
manifest=/pvarki/kraftwerk-init.json
tmp=$(mktemp /pvarki/.mas-manifest.XXXXXX)
jq --arg base "https://${KCDOMAIN}:9443" --arg realm "$KCREALM" \
  '.rasenmaeher.kc.base_uri //= $base | .rasenmaeher.kc.realm //= $realm | .oidc.client_registration.client_name //= "mas"' \
  "$manifest" > "$tmp"
jq -e '.rasenmaeher.kc.base_uri and .rasenmaeher.kc.realm and .oidc.client_registration.client_name' "$tmp" > /dev/null
mv "$tmp" "$manifest"
exec /usr/bin/tini -- /opt/mas/scripts/mas-entrypoint.sh

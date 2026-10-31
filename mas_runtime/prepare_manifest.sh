#!/bin/bash
set -euo pipefail

# MAS registers as part of the Matrix product, using its existing mTLS identity.
if [[ ! -s /matrix_data/public/mtlsclient.pem || ! -s /matrix_data/private/mtlsclient.key ]]; then
  echo "Matrix mTLS identity is not ready; retrying on container restart." >&2
  exit 1
fi
mkdir -p /data/public /data/private
ln -sf /matrix_data/public/mtlsclient.pem /data/public/mtlsclient.pem
ln -sf /matrix_data/private/mtlsclient.key /data/private/mtlsclient.key

# Miniwerk's Matrix manifest predates MAS's Keycloak registration fields.
manifest=/pvarki/kraftwerk-init.json
tmp=$(mktemp /pvarki/.mas-manifest.XXXXXX)
jq --arg base "https://${KCDOMAIN}:9443" --arg realm "$KCREALM" \
  '.rasenmaeher.kc.base_uri //= $base | .rasenmaeher.kc.realm //= $realm | .oidc.client_registration.client_name //= "mas"' \
  "$manifest" > "$tmp"
jq -e '.rasenmaeher.kc.base_uri and .rasenmaeher.kc.realm and .oidc.client_registration.client_name' "$tmp" > /dev/null
mv "$tmp" "$manifest"
exec /usr/bin/tini -- /opt/mas/scripts/mas-entrypoint.sh

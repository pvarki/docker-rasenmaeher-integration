#!/bin/bash
set -euo pipefail

# MAS registers as part of the Matrix product, using its existing mTLS identity.
# matrixrmapi creates it after MAS starts. Wait instead of exiting: Docker reports an exited
# container as unhealthy, and "docker compose up" then does not start the remaining services.
if [[ ! -s /matrix_data/public/mtlsclient.pem || ! -s /matrix_data/private/mtlsclient.key ]]; then
  echo "Matrix mTLS identity is not ready; waiting for matrixrmapi to create it." >&2
  until [[ -s /matrix_data/public/mtlsclient.pem && -s /matrix_data/private/mtlsclient.key ]]; do sleep 1; done
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

# Local environment fix: trust the mkcert CA that signs Keycloak's certificate.
if [[ -s /ca_public/miniwerk_ca.pem ]]; then
  cp /ca_public/miniwerk_ca.pem /usr/local/share/ca-certificates/miniwerk_ca.crt
  update-ca-certificates
fi
exec /usr/bin/tini -- /opt/mas/scripts/mas-entrypoint.sh

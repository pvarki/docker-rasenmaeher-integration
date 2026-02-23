#!/usr/bin/env bash
set -euo pipefail

CERT_DIR="${CERT_DIR:-/data/certs}"

# LE certs
LE_CERT="/le_certs/rasenmaeher/fullchain.pem"
LE_KEY="/le_certs/rasenmaeher/privkey.pem"

mkdir -p "$CERT_DIR"

SERVER_CRT="$CERT_DIR/${SERVER_DOMAIN}.crt"
SERVER_KEY="$CERT_DIR/${SERVER_DOMAIN}.key"

# Only copy if missing
if [[ ! -f "$SERVER_CRT" || ! -f "$SERVER_KEY" ]]; then
    echo "Copying LE certs for $SERVER_DOMAIN..."
    cp "$LE_CERT" "$SERVER_CRT"
    cp "$LE_KEY" "$SERVER_KEY"
fi

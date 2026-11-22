#!/usr/bin/env bash
# Validate the shipped RMAPI templates and their request limits in a disposable proxy.
set -euo pipefail

repo=$(cd "$(dirname "$0")/.." && pwd)
scratch=$(mktemp -d "${TMPDIR:-/tmp}/rmapi-nginx-test.XXXXXXXX")
container=""
cleanup() {
    if [[ -n "$container" ]]; then
        docker stop "$container" >/dev/null 2>&1 || true
        docker rm "$container" >/dev/null
    fi
    rm -r "$scratch"
}
trap cleanup EXIT

openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=rmapi.test \
    -addext subjectAltName=DNS:rmapi.test -keyout "$scratch/privkey.pem" \
    -out "$scratch/fullchain.pem" 2>"$scratch/openssl.log"

cat >"$scratch/nginx.conf" <<'EOF'
worker_processes 2;
events { worker_connections 256; }
http {
    access_log off;
    # Model distinct clients at the test ingress. No test header is trusted in the shipped templates.
    set_real_ip_from 0.0.0.0/0;
    real_ip_header X-Test-Client;
    add_header X-Test-Worker $pid always;
    add_header_inherit merge;
    server {
        listen 127.0.0.1:18080;
        location /api/v1/acme/ { return 400 'test upstream'; }
        location / { return 200 'test upstream'; }
    }
    include /etc/nginx/conf.d/default.conf;
}
EOF

cat >"$scratch/start.sh" <<'EOF'
set -eu
export NGINX_HOST=rmapi.test NGINX_CERT_NAME=test NGINX_HTTP_PORT=18081 NGINX_HTTPS_PORT=18443
export NGINX_UPSTREAM=127.0.0.1 NGINX_UPSTREAM_PORT=18080 NGINX_PRODUCTAPI_PORT=18444
export NGINX_UI_UPSTREAM=127.0.0.1 NGINX_UI_UPSTREAM_PORT=18080
export NGINX_OCSP_UPSTREAM=127.0.0.1 CFSSL_OCSP_BIND_PORT=18080 DNS_RESOLVER_IP=127.0.0.11
export NGINX_SYNAPSE_UPSTREAM=127.0.0.1 NGINX_SYNAPSE_UPSTREAM_PORT=18080
export NGINX_MAS_UPSTREAM=127.0.0.1 NGINX_MAS_UPSTREAM_PORT=18080
export NGINX_MATRIX_UPSTREAM=127.0.0.1 NGINX_MATRIX_UPSTREAM_PORT=18080
variables=$(env | sed -n 's/^\(NGINX_[A-Z_]*\|CFSSL_OCSP_BIND_PORT\|DNS_RESOLVER_IP\)=.*/${\1}/p')
for template in /nginx/templates_rasenmaeher /nginx/templates_rasenmaeher_uidev /nginx/templates_nomtls \
    /mas_nginx/templates_rasenmaeher_uidev /mas_nginx/templates_rasenmaeher; do
    echo "Validating $template"
    envsubst "$variables" <"$template/default.conf.template" >/etc/nginx/conf.d/default.conf
    nginx -t -c /fixtures/nginx.conf
done
# Distribute the short test burst across both workers.
awk '!configured && /listen 18443 ssl;/ {sub(/ssl;/, "ssl reuseport;"); configured=1} {print}' \
    /etc/nginx/conf.d/default.conf >/etc/nginx/conf.d/test.conf
mv /etc/nginx/conf.d/test.conf /etc/nginx/conf.d/default.conf
exec nginx -c /fixtures/nginx.conf -g 'daemon off;'
EOF

container=$(docker run -d --publish 127.0.0.1::18443 \
    --volume "$repo/nginx:/nginx:ro" --volume "$repo/mas_nginx:/mas_nginx:ro" \
    --volume "$repo/nginx/includes:/etc/nginx/includes:ro" \
    --volume "$scratch:/fixtures:ro" --volume "$scratch:/le_certs/test:ro" \
    --volume "$scratch/fullchain.pem:/ca_public/ca_chain.pem:ro" \
    --entrypoint sh nginx:1.31.8-alpine /fixtures/start.sh)
address=$(docker port "$container" 18443/tcp)
port=${address##*:}
curl_args=(--silent --show-error --noproxy '*' --cacert "$scratch/fullchain.pem" \
    --resolve "rmapi.test:$port:127.0.0.1" --max-time 3)
origin="https://rmapi.test:$port"
if ! curl "${curl_args[@]}" --fail --retry 5 --retry-all-errors --retry-delay 1 "$origin/api/docs" \
    >/dev/null 2>"$scratch/ready.log"; then
    cat "$scratch/ready.log"
    docker logs "$container"
    exit 1
fi

request() {
    local name=$1 path=$2
    shift 2
    curl "${curl_args[@]}" "$@" --dump-header "$scratch/$name.headers" --output "$scratch/$name.body" \
        --write-out '%{http_code}\n' "$origin$path" >"$scratch/$name.status"
}

burst() {
    local name=$1 count=$2 path=$3 client=$4
    shift 4
    local i address pid
    local pids=()
    for ((i = 1; i <= count; i++)); do
        address=$client
        if [[ -z "$address" ]]; then address="192.0.2.$i"; fi
        request "$name-$i" "$path" --header "X-Test-Client: $address" "$@" &
        pids+=("$!")
    done
    for pid in "${pids[@]}"; do wait "$pid"; done
}

register=/api/v1/acme/new-account
registration_args=(--header 'Content-Type: application/jose+json' --data 'malformed test request')
burst register-address 7 "$register" 198.51.100.1 "${registration_args[@]}"
[[ $(cat "$scratch"/register-address-*.status | awk '$0 == 400 { count++ } END { print count+0 }') == 5 ]]
burst register-service 16 "$register" "" "${registration_args[@]}"
[[ $(cat "$scratch"/register-service-*.status | awk '$0 == 429 { count++ } END { print count+0 }') -ge 3 ]]
burst acme 24 /api/v1/acme/new-nonce 198.51.100.2 --head
[[ $(cat "$scratch"/acme-*.status | awk '$0 == 429 { count++ } END { print count+0 }') -gt 0 ]]
burst acme-service 70 /api/v1/acme/new-nonce "" --head
[[ $(cat "$scratch"/acme-service-*.status | awk '$0 == 429 { count++ } END { print count+0 }') -gt 0 ]]

for status_file in "$scratch"/*.status; do
    if [[ $(cat "$status_file") == 429 ]]; then
        grep -qi '^Retry-After: 10' "${status_file%.status}.headers"
        grep -q 'urn:ietf:params:acme:error:rateLimited' "${status_file%.status}.body" || [[ $status_file == */acme-*.status ]]
    fi
done
[[ $(awk 'tolower($1) == "x-test-worker:" { print $2 }' "$scratch"/register-*.headers | sort -u | wc -l) -eq 2 ]]

burst ordinary 18 /api/docs 198.51.100.1
[[ $(cat "$scratch"/ordinary-*.status | sort -u) == 200 ]]
echo 'Validated five templates, shared worker limits, retry responses and unaffected ordinary traffic.'

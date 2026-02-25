#!/usr/bin/env bash
set -euo pipefail

OUTPUT_DIR="${OUTPUT_DIR:-syft_scans}"
mkdir -p "$OUTPUT_DIR"
MANIFEST_PATH="${MANIFEST_PATH:-$OUTPUT_DIR/manifest.tsv}"
SYFT_OUTPUT_FORMAT="${SYFT_OUTPUT_FORMAT:-cyclonedx-json@1.5}"
printf 'image\tsbom_file\n' > "$MANIFEST_PATH"

if docker image ls >/dev/null 2>&1; then
  docker_cmd=(docker)
else
  docker_cmd=(sudo docker)
fi

if syft version >/dev/null 2>&1; then
  syft_cmd=(syft)
else
  syft_cmd=(sudo syft)
fi

is_allowed_image() {
  local image="$1"
  local repo="${image%%:*}"

  case "$repo" in
    ghcr.io/pvarki/*|postgis/postgis|bluenviron/mediamtx|adorsys/keycloak-config-cli)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

sanitize_filename() {
  local image="$1"
  # Replace separators to produce stable filesystem-safe report names.
  echo "$image" | tr '/:@' '___' | tr -cd '[:alnum:]_.-'
}

scan_count=0
skip_count=0

while IFS= read -r image; do
  [[ -z "$image" ]] && continue
  [[ "$image" == "<none>:<none>" ]] && continue

  if ! is_allowed_image "$image"; then
    echo "Skipping $image (not in allowlist)"
    skip_count=$((skip_count + 1))
    continue
  fi

  echo "Scanning $image..."
  filename="$(sanitize_filename "$image").json"
  sbom_path="$OUTPUT_DIR/$filename"
  "${syft_cmd[@]}" "$image" -o "$SYFT_OUTPUT_FORMAT" > "$sbom_path"
  printf '%s\t%s\n' "$image" "$sbom_path" >> "$MANIFEST_PATH"
  scan_count=$((scan_count + 1))
done < <("${docker_cmd[@]}" image ls --format '{{.Repository}}:{{.Tag}}')

echo "Success! Generated $scan_count SBOM file(s) in '$OUTPUT_DIR' using format '$SYFT_OUTPUT_FORMAT'. Skipped $skip_count image(s)."
echo "Manifest written to '$MANIFEST_PATH'."

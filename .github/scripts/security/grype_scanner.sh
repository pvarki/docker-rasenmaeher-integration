#!/usr/bin/env bash
set -euo pipefail

INPUT_DIR="${INPUT_DIR:-syft_scans}"
OUTPUT_DIR="${OUTPUT_DIR:-grype_scans}"
mkdir -p "$OUTPUT_DIR"
INPUT_MANIFEST="${INPUT_MANIFEST:-$INPUT_DIR/manifest.tsv}"
OUTPUT_MANIFEST="${OUTPUT_MANIFEST:-$OUTPUT_DIR/manifest.tsv}"
printf 'image\treport_file\n' > "$OUTPUT_MANIFEST"

if grype version >/dev/null 2>&1; then
  grype_cmd=(grype)
else
  grype_cmd=(sudo grype)
fi

if ! compgen -G "$INPUT_DIR/*.json" >/dev/null; then
  echo "No SBOM files found in '$INPUT_DIR'. Nothing to scan."
  exit 0
fi

echo "Updating Grype vulnerability database..."
"${grype_cmd[@]}" db update

resolve_manifest_file_path() {
  local manifest_file="$1"
  local listed_path="$2"

  if [[ "$listed_path" = /* ]]; then
    printf '%s\n' "$listed_path"
    return
  fi

  local manifest_dir
  manifest_dir="$(dirname "$manifest_file")"

  local primary="$manifest_dir/$listed_path"
  if [[ -f "$primary" ]]; then
    printf '%s\n' "$primary"
    return
  fi

  local manifest_dir_name
  manifest_dir_name="$(basename "$manifest_dir")"
  if [[ "$listed_path" == "$manifest_dir_name/"* ]]; then
    local stripped="${listed_path#"$manifest_dir_name/"}"
    local deduplicated="$manifest_dir/$stripped"
    if [[ -f "$deduplicated" ]]; then
      printf '%s\n' "$deduplicated"
      return
    fi
  fi

  local fallback
  fallback="$(dirname "$manifest_dir")/$listed_path"
  if [[ -f "$fallback" ]]; then
    printf '%s\n' "$fallback"
    return
  fi

  printf '%s\n' "$primary"
}

run_grype_scan() {
  local sbom_file="$1"
  local report_path="$2"
  local tmp_report
  local tmp_stderr
  tmp_report="$(mktemp)"
  tmp_stderr="$(mktemp)"

  if ! "${grype_cmd[@]}" "sbom:$sbom_file" --output json > "$tmp_report" 2> "$tmp_stderr"; then
    if [[ -s "$tmp_stderr" ]]; then
      cat "$tmp_stderr" >&2
    fi
    rm -f "$tmp_report"
    rm -f "$tmp_stderr"
    return 1
  fi

  if [[ ! -s "$tmp_report" ]]; then
    if [[ -s "$tmp_stderr" ]]; then
      echo "Grype stderr output:" >&2
      cat "$tmp_stderr" >&2
    fi
    rm -f "$tmp_report"
    rm -f "$tmp_stderr"
    echo "Grype produced an empty report for $sbom_file" >&2
    return 1
  fi

  rm -f "$tmp_stderr"
  mv "$tmp_report" "$report_path"
}

scan_count=0
if [[ -f "$INPUT_MANIFEST" ]]; then
  while IFS=$'\t' read -r image sbom_file; do
    [[ "$image" == "image" ]] && continue
    [[ -z "$image" || -z "$sbom_file" ]] && continue

    resolved_sbom_file="$(resolve_manifest_file_path "$INPUT_MANIFEST" "$sbom_file")"

    if [[ ! -f "$resolved_sbom_file" ]]; then
      echo "Skipping missing SBOM from manifest: $sbom_file"
      continue
    fi

    echo "Scanning $resolved_sbom_file with Grype..."
    base_name="$(basename "$resolved_sbom_file" .json)"
    report_path="$OUTPUT_DIR/${base_name}_grype.json"
    run_grype_scan "$resolved_sbom_file" "$report_path"
    printf '%s\t%s\n' "$image" "$(basename "$report_path")" >> "$OUTPUT_MANIFEST"
    scan_count=$((scan_count + 1))
  done < "$INPUT_MANIFEST"
else
  for sbom_file in "$INPUT_DIR"/*.json; do
    [[ -f "$sbom_file" ]] || continue

    echo "Scanning $sbom_file with Grype..."
    base_name="$(basename "$sbom_file" .json)"
    report_path="$OUTPUT_DIR/${base_name}_grype.json"
    run_grype_scan "$sbom_file" "$report_path"
    printf '\t%s\n' "$(basename "$report_path")" >> "$OUTPUT_MANIFEST"
    scan_count=$((scan_count + 1))
  done
fi

echo "Success! All vulnerability reports are saved in '$OUTPUT_DIR' ($scan_count file(s))."
echo "Manifest written to '$OUTPUT_MANIFEST'."

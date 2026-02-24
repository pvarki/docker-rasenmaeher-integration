#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

ALLOWED_EXACT_REPOS = {
    "postgis/postgis",
    "bluenviron/mediamtx",
    "adorsys/keycloak-config-cli",
}
ALLOWED_PREFIX_REPOS = ("ghcr.io/pvarki/",)
SCAN_TYPE = "Anchore Grype"


@dataclass(frozen=True)
class UploadEntry:
    image_ref: str
    product_name: str
    report_path: Path


@dataclass(frozen=True)
class UploadConfig:
    base_url: str
    api_token: str
    product_type_name: str
    engagement_name: str
    verify_ssl: bool
    dry_run: bool


@dataclass
class UploadSummary:
    uploaded: int = 0
    failed: int = 0
    skipped: int = 0


Uploader = Callable[[UploadConfig, UploadEntry], tuple[int, str]]


def _parse_dotenv_assignment(line: str) -> Optional[tuple[str, str]]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].strip()

    if "=" not in stripped:
        return None

    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None

    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]

    return key, value


def load_dotenv_file(path: Path, override: bool = False) -> dict[str, str]:
    loaded: dict[str, str] = {}
    if not path.is_file():
        return loaded

    for line in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_dotenv_assignment(line)
        if not parsed:
            continue

        key, value = parsed
        if not override and key in os.environ:
            continue

        os.environ[key] = value
        loaded[key] = value

    return loaded


def image_repo_from_image_ref(image_ref: str) -> str:
    normalized = image_ref.strip()
    if not normalized:
        raise ValueError("Image reference cannot be empty")

    if "@" in normalized:
        return normalized.split("@", 1)[0]

    if ":" in normalized:
        return normalized.rsplit(":", 1)[0]

    return normalized


def is_allowed_repo(repo_name: str) -> bool:
    return repo_name in ALLOWED_EXACT_REPOS or repo_name.startswith(ALLOWED_PREFIX_REPOS)


def infer_repo_from_report_filename(filename: str) -> Optional[str]:
    stem = filename
    if stem.endswith(".json"):
        stem = stem[:-5]
    if stem.endswith("_grype"):
        stem = stem[:-6]

    if stem.startswith("ghcr.io_pvarki_"):
        remaining = stem[len("ghcr.io_pvarki_") :]
        image_name = remaining.split("_", 1)[0]
        if image_name:
            return f"ghcr.io/pvarki/{image_name}"

    if stem.startswith("postgis_postgis_"):
        return "postgis/postgis"

    if stem.startswith("bluenviron_mediamtx_"):
        return "bluenviron/mediamtx"

    if stem.startswith("adorsys_keycloak-config-cli_"):
        return "adorsys/keycloak-config-cli"

    return None


def resolve_report_path_from_manifest(manifest_path: Path, report_file: str) -> Path:
    report_path = Path(report_file)
    if report_path.is_absolute():
        return report_path

    primary = (manifest_path.parent / report_path).resolve()
    if primary.exists():
        return primary

    # Backward compatibility: older manifests may include output-dir prefixes
    # (e.g. grype_scans/file.json inside grype_scans/manifest.tsv).
    parts = report_path.parts
    if parts and parts[0] == manifest_path.parent.name:
        deduplicated = (manifest_path.parent / Path(*parts[1:])).resolve()
        if deduplicated.exists():
            return deduplicated

    fallback = (manifest_path.parent.parent / report_path).resolve()
    if fallback.exists():
        return fallback

    return primary


def read_manifest_entries(manifest_path: Path) -> list[UploadEntry]:
    entries: list[UploadEntry] = []
    if not manifest_path.exists():
        return entries

    for raw_line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue

        columns = raw_line.split("\t")
        if len(columns) < 2:
            continue

        image_ref = columns[0].strip()
        report_file = columns[1].strip()

        if image_ref == "image" and report_file == "report_file":
            continue

        if not report_file:
            continue

        report_path = resolve_report_path_from_manifest(manifest_path, report_file)

        if image_ref:
            try:
                repo_name = image_repo_from_image_ref(image_ref)
            except ValueError:
                continue
        else:
            repo_name = infer_repo_from_report_filename(report_path.name)
            image_ref = report_path.name

        if not repo_name or not is_allowed_repo(repo_name):
            continue

        entries.append(
            UploadEntry(
                image_ref=image_ref,
                product_name=repo_name,
                report_path=report_path,
            )
        )

    return entries


def discover_report_entries(reports_dir: Path, manifest_path: Optional[Path]) -> list[UploadEntry]:
    if manifest_path and manifest_path.exists():
        entries = read_manifest_entries(manifest_path)
        if entries:
            return entries

    entries: list[UploadEntry] = []
    for report_path in sorted(reports_dir.glob("*_grype.json")):
        repo_name = infer_repo_from_report_filename(report_path.name)
        if not repo_name or not is_allowed_repo(repo_name):
            continue

        image_ref = report_path.name.replace("_grype.json", "")
        entries.append(
            UploadEntry(
                image_ref=image_ref,
                product_name=repo_name,
                report_path=report_path,
            )
        )

    return entries


def build_multipart_payload(fields: dict[str, str], file_path: Path) -> tuple[str, bytes]:
    boundary = f"----DefectDojoBoundary{uuid.uuid4().hex}"
    body = io.BytesIO()

    for key, value in fields.items():
        body.write(f"--{boundary}\r\n".encode("utf-8"))
        body.write(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        body.write(str(value).encode("utf-8"))
        body.write(b"\r\n")

    body.write(f"--{boundary}\r\n".encode("utf-8"))
    body.write(
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'.encode(
            "utf-8"
        )
    )
    body.write(b"Content-Type: application/json\r\n\r\n")
    body.write(file_path.read_bytes())
    body.write(b"\r\n")
    body.write(f"--{boundary}--\r\n".encode("utf-8"))

    return boundary, body.getvalue()


def reimport_scan(config: UploadConfig, entry: UploadEntry) -> tuple[int, str]:
    endpoint = f"{config.base_url.rstrip('/')}/api/v2/reimport-scan/"
    test_title = f"Grype {entry.image_ref}"

    fields = {
        "scan_type": SCAN_TYPE,
        "product_type_name": config.product_type_name,
        "product_name": entry.product_name,
        "engagement_name": config.engagement_name,
        "test_title": test_title,
        "auto_create_context": "true",
        "close_old_findings": "true",
        "do_not_reactivate": "false",
    }

    boundary, payload = build_multipart_payload(fields, entry.report_path)
    request = urllib.request.Request(endpoint, method="POST", data=payload)
    request.add_header("Authorization", f"Token {config.api_token}")
    request.add_header("Accept", "application/json")
    request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

    ssl_context = None
    if not config.verify_ssl:
        ssl_context = ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(request, context=ssl_context, timeout=120) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            return response.getcode(), response_body
    except urllib.error.HTTPError as error:
        response_body = error.read().decode("utf-8", errors="replace")
        return error.code, response_body


def process_uploads(
    entries: Iterable[UploadEntry],
    config: UploadConfig,
    uploader: Uploader = reimport_scan,
) -> UploadSummary:
    summary = UploadSummary()

    for entry in entries:
        if not entry.report_path.is_file():
            print(f"SKIP: report file does not exist: {entry.report_path}")
            summary.skipped += 1
            continue

        if entry.report_path.stat().st_size == 0:
            print(f"FAIL: report file is empty: {entry.report_path}")
            summary.failed += 1
            continue

        if not is_allowed_repo(entry.product_name):
            print(f"SKIP: repository is not in allowlist: {entry.product_name}")
            summary.skipped += 1
            continue

        if config.dry_run:
            print(
                "DRY-RUN: would upload "
                f"{entry.report_path} as product='{entry.product_name}' "
                f"engagement='{config.engagement_name}'"
            )
            summary.uploaded += 1
            continue

        status_code, response_body = uploader(config, entry)
        if 200 <= status_code < 300:
            print(f"OK: {entry.report_path.name} -> HTTP {status_code}")
            summary.uploaded += 1
            continue

        print(
            f"FAIL: {entry.report_path.name} -> HTTP {status_code} | "
            f"{response_body[:300].replace(chr(10), ' ')}"
        )
        summary.failed += 1

    return summary


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def normalize_base_url(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        return normalized

    has_scheme = "://" in normalized
    if not has_scheme:
        normalized = f"https://{normalized.lstrip('/')}"

    parsed = urllib.parse.urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(
            "DD_BASE_URL must be a valid URL (for example: https://defectdojo.example.com)"
        )

    if parsed.query or parsed.fragment:
        raise ValueError("DD_BASE_URL must not include query string or fragment")

    base_path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{base_path}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload Grype JSON reports to DefectDojo via reimport-scan."
    )
    parser.add_argument("--reports-dir", default="grype_scans", help="Directory with Grype JSON reports")
    parser.add_argument(
        "--manifest",
        default=None,
        help="Optional TSV manifest (defaults to <reports-dir>/manifest.tsv when present)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print actions without uploading")
    parser.add_argument(
        "--verify-ssl",
        choices=["true", "false"],
        default=None,
        help="Override DD_VERIFY_SSL (true/false)",
    )
    parser.add_argument(
        "--product-type-name",
        default=os.getenv("DD_PRODUCT_TYPE_NAME", "Container Images"),
        help="DefectDojo product type name",
    )
    parser.add_argument(
        "--engagement-name",
        default=os.getenv(
            "DD_ENGAGEMENT_NAME", "Continuous Container Vulnerability Scanning"
        ),
        help="DefectDojo engagement name",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv_file(Path(".env"))
    args = parse_args()

    reports_dir = Path(args.reports_dir)
    if not reports_dir.exists():
        print(f"Reports directory does not exist: {reports_dir}", file=sys.stderr)
        return 2

    verify_ssl_env = os.getenv("DD_VERIFY_SSL", "true")
    verify_ssl_raw = args.verify_ssl if args.verify_ssl is not None else verify_ssl_env
    try:
        verify_ssl = parse_bool(verify_ssl_raw)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    base_url_raw = os.getenv("DD_BASE_URL", "").strip()
    api_token = os.getenv("DD_API_TOKEN", "").strip()

    try:
        base_url = normalize_base_url(base_url_raw)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    if base_url_raw and "://" not in base_url_raw:
        print("Warning: DD_BASE_URL has no scheme; assuming https://", file=sys.stderr)

    if not args.dry_run and (not base_url or not api_token):
        print("DD_BASE_URL and DD_API_TOKEN are required unless --dry-run is used.", file=sys.stderr)
        return 2

    if args.dry_run and (not base_url or not api_token):
        print("Warning: DD_BASE_URL/DD_API_TOKEN missing; continuing because --dry-run is enabled.")

    manifest_path: Optional[Path]
    if args.manifest:
        manifest_path = Path(args.manifest)
    else:
        default_manifest = reports_dir / "manifest.tsv"
        manifest_path = default_manifest if default_manifest.exists() else None

    entries = discover_report_entries(reports_dir, manifest_path)
    if not entries:
        print("No eligible Grype reports found for upload.")
        return 0

    config = UploadConfig(
        base_url=base_url,
        api_token=api_token,
        product_type_name=args.product_type_name,
        engagement_name=args.engagement_name,
        verify_ssl=verify_ssl,
        dry_run=args.dry_run,
    )

    summary = process_uploads(entries, config)
    print(
        "Upload summary: "
        f"uploaded={summary.uploaded}, failed={summary.failed}, skipped={summary.skipped}"
    )

    return 1 if summary.failed > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())

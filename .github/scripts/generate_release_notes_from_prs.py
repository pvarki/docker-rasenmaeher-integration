#!/usr/bin/env python3
"""
Generate release notes from merged PRs between two tags.

- Uses commits between previous tag and current tag in the integration repo
  to discover PRs.
- For each PR:
  - Reads the PR body, expecting:
      ## User-facing summary (used in release notes)
      ## Why It's Good for the Product (Release Goal)
  - Collects ALL lines under those headings (not just first line).
  - Collects all commits for that PR.

- Additionally:
  - Reads .gitmodules to discover ALL submodules (no hardcoding).
  - For each submodule, finds old/new SHAs at prev_tag/current_tag.
  - If SHAs differ, calls GitHub compare API for that submodule repo
    to get the commits between those SHAs.

- In the release notes:
  - TL;DR = all user-facing summary lines from all included PRs
            (plus one bullet about breaking changes or lack thereof).
  - "Release Goals" = all "Why it's good" lines from all PRs.
  - "New features" / "Improvements & fixes" / "Breaking changes" / "Security"
    = categorized commit messages from:
      - integration repo commits (via PRs)
      - submodule repo commits (via compare)
    Each bullet for integration commits links to the PR.
    Each bullet for submodule commits links to the commit in that repo,
    prefixed with [submodule-name].

Outputs: docs/releases/<tag>.md (e.g., docs/releases/1.15.0.md)

Requires env:
- GITHUB_TOKEN       (PAT or Actions token)
- GITHUB_REPOSITORY  (e.g. "pvarki/docker-rasenmaeher-integration")
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


def sh(cmd: str) -> str:
    """Run a shell command and return stdout (stripped)."""
    return subprocess.check_output(cmd, shell=True, text=True).strip()


@dataclass
class PRInfo:
    """Pull request metadata used for release notes."""

    number: int
    title: str
    body: str
    author: str
    merged_at: str


@dataclass
class PRCommit:
    """Commit data (subject + body) belonging to a PR."""

    sha: str
    subject: str
    body: str


@dataclass
class ReleaseEntry:
    """Parsed release-relevant data for a single PR."""

    pr: PRInfo
    summary_lines: List[str]
    goal_lines: List[str]
    commits: List[PRCommit]


@dataclass
class SubmoduleCommit:
    """Commit in a submodule that is part of this integration release."""

    repo_slug: str  # e.g. "pvarki/docker-rasenmaeher-rmapi"
    label: str  # e.g. "rmapi"
    commit: PRCommit


def github_client() -> Dict[str, str]:
    """Build basic GitHub API client configuration from env."""
    token = os.environ["GITHUB_TOKEN"]
    repo = os.environ["GITHUB_REPOSITORY"]
    base_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    return {
        "token": token,
        "repo": repo,
        "base_url": base_url.rstrip("/"),
    }


def gh_get_json(path: str, params: Optional[Dict[str, str]] = None) -> Any:
    """
    Simple GitHub API GET helper for the *integration repo* using stdlib only.

    path: "/repos/{repo}/commits/sha/pulls"
    params: {"per_page": "100"} etc.
    """
    client = github_client()
    base_url = client["base_url"]
    token = client["token"]
    repo = client["repo"]

    if path.startswith("/"):
        url = f"{base_url}{path}"
    else:
        url = f"{base_url}/{path}"

    url = url.replace("{repo}", repo)

    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{query}"

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "release-notes-script",
        },
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"GitHub API error {exc.code} for {url}: " f"{exc.read().decode('utf-8', errors='ignore')}"
        ) from exc


def gh_get_json_for_repo(repo_slug: str, path: str, params: Optional[Dict[str, str]] = None) -> Any:
    """
    Simple GitHub API GET helper for an arbitrary repo given by slug "owner/repo".

    path: "/compare/old...new", etc.
    """
    client = github_client()
    base_url = client["base_url"]
    token = client["token"]

    if path.startswith("/"):
        url = f"{base_url}/repos/{repo_slug}{path}"
    else:
        url = f"{base_url}/repos/{repo_slug}/{path}"

    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{query}"

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "release-notes-script",
        },
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"GitHub API error {exc.code} for {url}: " f"{exc.read().decode('utf-8', errors='ignore')}"
        ) from exc


def get_previous_tag(current_tag: str) -> str:
    """
    Get the previous tag before the current one.

    Assumes tags are plain semver-like (no enforced 'v' prefix).
    """
    return sh(f"git describe --tags --abbrev=0 {current_tag}^")


def get_commits_between(prev_tag: str, current_tag: str) -> List[str]:
    """Return list of commit SHAs between prev_tag and current_tag."""
    out = sh(f"git rev-list {prev_tag}..{current_tag}")
    return [line for line in out.splitlines() if line.strip()]


def get_prs_for_commits(commits: Sequence[str]) -> List[PRInfo]:
    """
    For a list of commit SHAs, ask GitHub which PRs they belong to.

    Uses /repos/{repo}/commits/{sha}/pulls.
    """
    prs: Dict[int, PRInfo] = {}

    for sha in commits:
        data = gh_get_json(f"/repos/{{repo}}/commits/{sha}/pulls")
        if not isinstance(data, list):
            continue
        for pr in data:
            number = pr["number"]
            if number in prs:
                continue
            prs[number] = PRInfo(
                number=number,
                title=pr["title"],
                body=pr.get("body") or "",
                author=pr["user"]["login"],
                merged_at=pr.get("merged_at") or "",
            )

    return sorted(prs.values(), key=lambda p: p.merged_at or "")


def get_commits_for_pr(pr_number: int) -> List[PRCommit]:
    """Fetch commits for a PR from GitHub and parse subjects/bodies."""
    data = gh_get_json(
        f"/repos/{{repo}}/pulls/{pr_number}/commits",
        params={"per_page": "100"},
    )
    if not isinstance(data, list):
        return []

    commits: List[PRCommit] = []
    for item in data:
        commit_data = item["commit"]
        message: str = commit_data["message"]
        subject, _, body = message.partition("\n")
        commits.append(PRCommit(sha=item["sha"], subject=subject, body=body))
    return commits


def extract_block(body: str, heading: str) -> str:
    """
    Extract markdown text between '## heading' and the next '## '.

    Comparison is case-insensitive.
    """
    lines = body.splitlines()
    collected: List[str] = []
    in_block = False
    target = heading.strip().lower()

    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("## "):
            section_title = stripped[3:].strip().lower()
            if in_block:
                break
            if section_title == target:
                in_block = True
                continue
        elif in_block:
            collected.append(line)

    return "\n".join(collected).strip()


def parse_lines(block: str) -> List[str]:
    """
    Return ALL non-empty, non-comment lines from a markdown block,
    with leading 'Summary:' / '-' stripped away.
    """
    result: List[str] = []
    if not block:
        return result

    for raw in block.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("<!--") and line.endswith("-->"):
            continue
        line = re.sub(r"^Summary:\s*-?\s*", "", line, flags=re.IGNORECASE)
        line = line.lstrip("- ").strip()
        if line:
            result.append(line)
    return result


# Conventional Commit regex:
#   feat(scope)!: description
#   fix: description
_CONVENTIONAL_RE = re.compile(
    r"^(?P<type>\w+)"  # feat, fix, chore, etc.
    r"(?:\([^)]*\))?"  # optional scope
    r"(?P<breaking>!)?"  # optional !
    r":\s*(?P<desc>.+)$"
)


def classify_commit(c: PRCommit) -> Tuple[str, str]:
    """
    Classify a single commit and return (logical_type, full_subject).

    Keeps the full original subject including:
    feat:, fix:, chore:, scope, etc.
    """
    full_subject = c.subject.strip()
    logical_type = "internal"

    m = _CONVENTIONAL_RE.match(c.subject)
    breaking_flag = False
    ctype: Optional[str] = None

    if m:
        ctype = m.group("type").lower()
        breaking_flag = bool(m.group("breaking"))
    if "BREAKING CHANGE" in c.body:
        breaking_flag = True

    if breaking_flag:
        logical_type = "breaking"
    elif ctype == "feat":
        logical_type = "feature"
    elif ctype in {"fix", "perf", "refactor", "chore"}:
        logical_type = "fix"
    elif ctype in {"sec", "security"}:
        logical_type = "security"

    return logical_type, full_subject


def generate_entries(prs: Sequence[PRInfo]) -> List[ReleaseEntry]:
    """For each PR, parse ALL summary + goal lines + collect commits."""
    entries: List[ReleaseEntry] = []

    for pr in prs:
        summary_block = extract_block(pr.body, "User-facing summary (used in release notes)")
        summary_lines = parse_lines(summary_block)
        if not summary_lines:
            summary_lines = ["No user-facing summary provided."]

        goal_block = extract_block(pr.body, "Why It's Good for the Product (Release Goal)")
        goal_lines = parse_lines(goal_block)

        pr_commits = get_commits_for_pr(pr.number)

        entries.append(
            ReleaseEntry(
                pr=pr,
                summary_lines=summary_lines,
                goal_lines=goal_lines,
                commits=pr_commits,
            )
        )

    return entries


def github_repo_slug_from_url(url: str) -> Optional[str]:
    """
    Derive "owner/repo" from typical GitHub submodule URLs:

    - git@github.com:owner/repo.git
    - https://github.com/owner/repo.git
    - https://github.com/owner/repo
    """
    if "github.com" not in url:
        return None

    # Strip protocol
    url = url.strip()
    url = url.replace("git@", "").replace("ssh://", "")
    # Normalize ssh-style
    if url.startswith("github.com:"):
        url = "github.com/" + url.split("github.com:", 1)[1]
    # Remove scheme if present
    url = re.sub(r"^https?://", "", url)

    # Now expect github.com/owner/repo(.git)
    m = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+)", url)
    if not m:
        return None
    owner = m.group("owner")
    repo = m.group("repo")
    if repo.endswith(".git"):
        repo = repo[:-4]
    return f"{owner}/{repo}"


def get_submodules() -> Dict[str, str]:
    """
    Parse .gitmodules to discover submodules.

    Returns mapping: path -> repo_slug ("owner/repo").
    """
    gitmodules = Path(".gitmodules")
    if not gitmodules.exists():
        return {}

    # name -> path
    name_to_path: Dict[str, str] = {}
    # name -> url
    name_to_url: Dict[str, str] = {}

    try:
        out_paths = sh("git config --file .gitmodules --get-regexp 'submodule\\..*\\.path'")
    except subprocess.CalledProcessError:
        out_paths = ""

    for line in out_paths.splitlines():
        key, path = line.split(" ", 1)
        # key like "submodule.subname.path"
        parts = key.split(".")
        if len(parts) < 3:
            continue
        name = parts[1]
        name_to_path[name] = path.strip()

    try:
        out_urls = sh("git config --file .gitmodules --get-regexp 'submodule\\..*\\.url'")
    except subprocess.CalledProcessError:
        out_urls = ""

    for line in out_urls.splitlines():
        key, url = line.split(" ", 1)  # <-- '=' instead of 'in'
        parts = key.split(".")
        if len(parts) < 3:
            continue
        name = parts[1]
        name_to_url[name] = url.strip()

    result: Dict[str, str] = {}
    for name, path in name_to_path.items():
        url_value = name_to_url.get(name)
        if not url_value:
            continue
        slug = github_repo_slug_from_url(url_value)
        if not slug:
            continue
        result[path] = slug

    return result


def get_submodule_sha_at_ref(ref: str, path: str) -> Optional[str]:
    """
    Get the submodule SHA at a given ref for a given submodule path.

    Uses `git ls-tree <ref> <path>` which outputs lines like:
      160000 commit <sha>\t<path>
    """
    try:
        out = sh(f"git ls-tree {ref} {path}")
    except subprocess.CalledProcessError:
        return None
    if not out:
        return None
    parts = out.split()
    if len(parts) < 3:
        return None
    return parts[2]


def get_submodule_commits_between(
    repo_slug: str,
    old_sha: str,
    new_sha: str,
    label: str,
) -> List[SubmoduleCommit]:
    """
    Use GitHub compare API to get commits between old_sha..new_sha for a submodule repo.
    """
    # Compare endpoint: /repos/{owner}/{repo}/compare/{base}...{head}
    data = gh_get_json_for_repo(
        repo_slug,
        f"/compare/{old_sha}...{new_sha}",
        params={"per_page": "250"},
    )

    if not isinstance(data, dict):
        return []

    commits_data = data.get("commits") or []
    if not isinstance(commits_data, list):
        return []

    commits: List[SubmoduleCommit] = []

    for item in commits_data:
        sha = item["sha"]
        commit_data = item["commit"]
        message: str = commit_data["message"]
        subject, _, body = message.partition("\n")
        commits.append(
            SubmoduleCommit(
                repo_slug=repo_slug,
                label=label,
                commit=PRCommit(sha=sha, subject=subject, body=body),
            )
        )

    return commits


def generate_markdown(
    product_name: str,
    version: str,
    entries: Sequence[ReleaseEntry],
    submodule_commits: Sequence[SubmoduleCommit],
) -> str:
    """
    Render the final release notes markdown from PR entries and submodule commits.
    """
    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    today = date.today().isoformat()
    main_repo_slug = github_client()["repo"]

    # ---- Release Goals (all goal lines)
    goals = [line for e in entries for line in e.goal_lines]
    goal_block = "\n".join(f"- {g}" for g in goals) if goals else "- (none)"

    # ---- TL;DR (all user-facing summary lines)
    all_summary_lines = [
        line for e in entries for line in e.summary_lines if line != "No user-facing summary provided."
    ]

    if all_summary_lines:
        tldr_items = list(all_summary_lines)
    else:
        tldr_items = [
            "Main highlight of this release.",
            "Second important change.",
        ]

    # ---- Commit-based sections
    feature_lines: List[str] = []
    fix_lines: List[str] = []
    breaking_lines: List[str] = []
    security_lines: List[str] = []

    breaking_desc_for_tldr: Optional[str] = None

    # Integration repo commits (with PR links)
    for e in entries:
        pr_number = e.pr.number
        for c in e.commits:
            logical_type, desc = classify_commit(c)
            if logical_type == "feature":
                feature_lines.append(f"- {desc} ([#{pr_number}](https://github.com/{main_repo_slug}/pull/{pr_number}))")
            elif logical_type == "fix":
                fix_lines.append(f"- {desc} ([#{pr_number}](https://github.com/{main_repo_slug}/pull/{pr_number}))")
            elif logical_type == "breaking":
                breaking_lines.append(
                    f"- {desc} ([#{pr_number}](https://github.com/{main_repo_slug}/pull/{pr_number}))"
                )
                if breaking_desc_for_tldr is None:
                    breaking_desc_for_tldr = desc
            elif logical_type == "security":
                security_lines.append(
                    f"- {desc} ([#{pr_number}](https://github.com/{main_repo_slug}/pull/{pr_number}))"
                )

    # Submodule commits (with commit links, prefixed by [label])
    for sc in submodule_commits:
        logical_type, desc = classify_commit(sc.commit)
        prefix = f"[{sc.label}] "
        commit_url = f"https://github.com/{sc.repo_slug}/commit/{sc.commit.sha}"
        line = f"- {prefix}{desc} ([commit]({commit_url}))"
        if logical_type == "feature":
            feature_lines.append(line)
        elif logical_type == "fix":
            fix_lines.append(line)
        elif logical_type == "breaking":
            breaking_lines.append(line)
            if breaking_desc_for_tldr is None:
                breaking_desc_for_tldr = f"{prefix}{desc}"
        elif logical_type == "security":
            security_lines.append(line)
        # internal ignored

    # Add one bullet about breaking changes to TL;DR
    if breaking_desc_for_tldr is not None:
        tldr_items.append(f"Breaking change: {breaking_desc_for_tldr}")
    else:
        tldr_items.append("No breaking changes.")

    def block(lines: List[str]) -> str:
        return "\n".join(lines) if lines else "- (none)"

    features_block = block(feature_lines)
    fixes_block = block(fix_lines)
    breaking_block = block(breaking_lines)
    security_block = block(security_lines)

    contributors: Set[str] = {e.pr.author for e in entries}
    contributors_block = "\n".join(f"- @{c}" for c in sorted(contributors)) if contributors else "- (none)"

    return f"""# {product_name} {version}

**Release date:** {today}

## TL;DR

{chr(10).join(f"- {x}" for x in tldr_items)}

---

## Release Goals

{goal_block}

---

## New features

{features_block}

---

## Improvements & fixes

{fixes_block}

---

## Breaking changes

{breaking_block}

---

## Security

{security_block}

---

## Contributors

{contributors_block}
"""


def main() -> None:
    """
    Entry point: compute previous tag, gather PRs and submodule commits,
    and write docs/releases/<tag>.md.
    """
    # pylint: disable=too-many-locals
    if len(sys.argv) < 3:
        print(
            "Usage: generate_release_notes_from_prs.py <tag> <product_name>",
            file=sys.stderr,
        )
        sys.exit(1)

    tag = sys.argv[1]  # e.g. "1.15.0"
    product = sys.argv[2]  # e.g. "docker-rasenmaeher-integration"

    try:
        prev_tag = get_previous_tag(tag)
    except subprocess.CalledProcessError as exc:
        print(f"Failed to determine previous tag before {tag}: {exc}", file=sys.stderr)
        sys.exit(1)

    commits = get_commits_between(prev_tag, tag)
    if not commits:
        print(f"No commits between {prev_tag} and {tag}, nothing to do.")
        sys.exit(0)

    prs = get_prs_for_commits(commits)
    if not prs:
        print("No PRs associated with the commits for this tag range, nothing to do.")
        sys.exit(0)

    entries = generate_entries(prs)

    # --- Submodule commits
    submodules = get_submodules()
    submodule_commit_list: List[SubmoduleCommit] = []

    for path, repo_slug in submodules.items():
        old_sha = get_submodule_sha_at_ref(prev_tag, path)
        new_sha = get_submodule_sha_at_ref(tag, path)
        if not old_sha or not new_sha or old_sha == new_sha:
            continue
        # label: last path segment (e.g. "rmapi" from "submodules/rmapi")
        label = Path(path).name
        submodule_commit_list.extend(get_submodule_commits_between(repo_slug, old_sha, new_sha, label))

    md = generate_markdown(product, tag, entries, submodule_commit_list)

    out_dir = Path("docs") / "releases"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{tag}.md"
    out_file.write_text(md, encoding="utf-8")
    print(f"Wrote {out_file}")


if __name__ == "__main__":
    main()

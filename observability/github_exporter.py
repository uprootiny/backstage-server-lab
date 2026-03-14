#!/usr/bin/env python3
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from prometheus_client import Gauge, start_http_server


GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "uprootiny/backstage-server-lab").strip()
POLL_SECONDS = int(os.getenv("GITHUB_EXPORTER_POLL_SECONDS", "90"))
PORT = int(os.getenv("GITHUB_EXPORTER_PORT", "9171"))
TIMEOUT = int(os.getenv("GITHUB_API_TIMEOUT_SECONDS", "20"))

if "/" not in GITHUB_REPOSITORY:
    raise SystemExit("GITHUB_REPOSITORY must look like owner/repo")

OWNER, REPO = GITHUB_REPOSITORY.split("/", 1)
BASE = "https://api.github.com"

HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "backstage-server-lab-github-exporter",
}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

M_REPO_UP = Gauge("github_repo_up", "1 if last scrape succeeded", ["repo"])
M_RATE_LIMIT_REMAINING = Gauge("github_api_rate_limit_remaining", "GitHub API remaining calls")
M_RATE_LIMIT_RESET = Gauge("github_api_rate_limit_reset_epoch", "GitHub API reset epoch")

M_STARS = Gauge("github_repo_stars", "Repository stars", ["repo"])
M_FORKS = Gauge("github_repo_forks", "Repository forks", ["repo"])
M_SUBSCRIBERS = Gauge("github_repo_subscribers", "Repository watchers/subscribers", ["repo"])
M_OPEN_ISSUES = Gauge("github_repo_open_issues", "Open issues (excluding PRs)", ["repo"])
M_OPEN_PRS = Gauge("github_repo_open_prs", "Open pull requests", ["repo"])
M_CONTRIBUTORS = Gauge("github_repo_contributors", "Contributors count", ["repo"])
M_RELEASES = Gauge("github_repo_releases", "Releases count", ["repo"])
M_COMMITS_24H = Gauge("github_repo_commits_24h", "Commits in last 24h", ["repo"])
M_WORKFLOWS = Gauge("github_actions_workflows", "Workflow count", ["repo"])
M_WORKFLOW_RUNS_TOTAL = Gauge("github_actions_workflow_runs_total", "Workflow runs total", ["repo"])
M_WORKFLOW_RUNS_7D = Gauge("github_actions_workflow_runs_7d", "Workflow runs in last 7 days", ["repo"])
M_WORKFLOW_FAIL_7D = Gauge("github_actions_workflow_failures_7d", "Workflow failures in last 7 days", ["repo"])


def _get(url: str, params: dict[str, Any] | None = None) -> requests.Response:
    r = requests.get(url, headers=HEADERS, params=params or {}, timeout=TIMEOUT)
    rem = r.headers.get("X-RateLimit-Remaining")
    rst = r.headers.get("X-RateLimit-Reset")
    if rem is not None:
        try:
            M_RATE_LIMIT_REMAINING.set(float(rem))
        except Exception:
            pass
    if rst is not None:
        try:
            M_RATE_LIMIT_RESET.set(float(rst))
        except Exception:
            pass
    r.raise_for_status()
    return r


def _count_search_issues(query: str) -> int:
    r = _get(f"{BASE}/search/issues", params={"q": query, "per_page": 1})
    return int(r.json().get("total_count", 0))


def _scrape_once() -> None:
    repo_label = GITHUB_REPOSITORY

    repo = _get(f"{BASE}/repos/{OWNER}/{REPO}").json()
    M_STARS.labels(repo=repo_label).set(float(repo.get("stargazers_count", 0)))
    M_FORKS.labels(repo=repo_label).set(float(repo.get("forks_count", 0)))
    M_SUBSCRIBERS.labels(repo=repo_label).set(float(repo.get("subscribers_count", 0)))

    open_prs = _count_search_issues(f"repo:{OWNER}/{REPO} type:pr state:open")
    open_issues_all = int(repo.get("open_issues_count", 0))
    open_issues = max(0, open_issues_all - open_prs)
    M_OPEN_PRS.labels(repo=repo_label).set(float(open_prs))
    M_OPEN_ISSUES.labels(repo=repo_label).set(float(open_issues))

    contrib = _get(f"{BASE}/repos/{OWNER}/{REPO}/contributors", params={"per_page": 100, "anon": "true"}).json()
    M_CONTRIBUTORS.labels(repo=repo_label).set(float(len(contrib) if isinstance(contrib, list) else 0))

    rel = _get(f"{BASE}/repos/{OWNER}/{REPO}/releases", params={"per_page": 100}).json()
    M_RELEASES.labels(repo=repo_label).set(float(len(rel) if isinstance(rel, list) else 0))

    since_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    commits = _get(f"{BASE}/repos/{OWNER}/{REPO}/commits", params={"since": since_24h, "per_page": 100}).json()
    M_COMMITS_24H.labels(repo=repo_label).set(float(len(commits) if isinstance(commits, list) else 0))

    wf = _get(f"{BASE}/repos/{OWNER}/{REPO}/actions/workflows", params={"per_page": 100}).json()
    M_WORKFLOWS.labels(repo=repo_label).set(float(len(wf.get("workflows", []))))

    runs_all = _get(f"{BASE}/repos/{OWNER}/{REPO}/actions/runs", params={"per_page": 1}).json()
    M_WORKFLOW_RUNS_TOTAL.labels(repo=repo_label).set(float(runs_all.get("total_count", 0)))

    since_7d = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    runs_7d = _get(f"{BASE}/repos/{OWNER}/{REPO}/actions/runs", params={"per_page": 100, "created": f">={since_7d}"}).json()
    items = runs_7d.get("workflow_runs", []) if isinstance(runs_7d, dict) else []
    fail = sum(1 for it in items if str(it.get("conclusion", "")).lower() == "failure")
    M_WORKFLOW_RUNS_7D.labels(repo=repo_label).set(float(len(items)))
    M_WORKFLOW_FAIL_7D.labels(repo=repo_label).set(float(fail))

    M_REPO_UP.labels(repo=repo_label).set(1.0)

def _loop() -> None:
    while True:
        try:
            _scrape_once()
        except Exception:
            M_REPO_UP.labels(repo=GITHUB_REPOSITORY).set(0.0)
        time.sleep(max(15, POLL_SECONDS))


def main() -> None:
    start_http_server(PORT)
    _loop()


if __name__ == "__main__":
    main()

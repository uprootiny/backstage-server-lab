#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


WATCH = [
    ("GITHUB_TOKEN", "github_api"),
    ("VAST_API_KEY", "vast_api"),
    ("VAST_HOST", "vast_ssh"),
    ("VAST_USER", "vast_ssh"),
    ("VAST_SSH_PORT", "vast_ssh"),
    ("VAST_SSH_KEY", "vast_ssh"),
    ("KAGGLE_USERNAME", "kaggle_api"),
    ("KAGGLE_KEY", "kaggle_api"),
    ("OPENAI_API_KEY", "model_api"),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_payload() -> dict:
    rows = []
    by_group: dict[str, dict[str, int]] = {}
    for key, group in WATCH:
        present = bool(os.getenv(key, "").strip())
        rows.append(
            {
                "key": key,
                "group": group,
                "present": present,
                "value_preview": "***set***" if present else "",
            }
        )
        g = by_group.setdefault(group, {"total": 0, "present": 0})
        g["total"] += 1
        g["present"] += 1 if present else 0

    return {
        "generated_at": _now(),
        "kind": "ci_secrets_instrumentation",
        "keys": rows,
        "groups": {
            k: {
                "present": v["present"],
                "total": v["total"],
                "ready": v["present"] == v["total"],
            }
            for k, v in sorted(by_group.items())
        },
    }


def write_reports(out_json: Path, out_md: Path) -> None:
    payload = build_payload()
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# CI Secrets Instrumentation",
        "",
        f"- generated_at: {payload['generated_at']}",
        "",
        "## Groups",
        "",
        "| Group | Present | Total | Ready |",
        "|---|---:|---:|---|",
    ]
    for group, row in payload["groups"].items():
        lines.append(f"| `{group}` | {row['present']} | {row['total']} | {'yes' if row['ready'] else 'no'} |")

    lines += [
        "",
        "## Keys (presence only)",
        "",
        "| Key | Group | Present |",
        "|---|---|---|",
    ]
    for row in payload["keys"]:
        lines.append(f"| `{row['key']}` | `{row['group']}` | {'yes' if row['present'] else 'no'} |")

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"secrets_json={out_json}")
    print(f"secrets_md={out_md}")


def main() -> None:
    out_json = Path(os.getenv("CI_SECRETS_JSON", "reports/ci/secrets_status.json"))
    out_md = Path(os.getenv("CI_SECRETS_MD", "reports/ci/secrets_status.md"))
    write_reports(out_json, out_md)


if __name__ == "__main__":
    main()

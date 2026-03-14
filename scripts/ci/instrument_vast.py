#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run(cmd: list[str]) -> tuple[int, str, str]:
    p = subprocess.run(cmd, text=True, capture_output=True)
    return p.returncode, p.stdout, p.stderr


def collect() -> dict:
    payload: dict = {
        "generated_at": _now(),
        "kind": "vast_cli_instrumentation",
        "vastai_in_path": shutil.which("vastai") is not None,
        "vast_api_key_present": bool(os.getenv("VAST_API_KEY", "").strip()),
        "instances": [],
        "instance_count": 0,
        "status": "unavailable",
        "error": "",
    }
    if not payload["vastai_in_path"]:
        payload["error"] = "vastai not installed"
        return payload

    code, out, err = _run(["vastai", "show", "instances", "--raw"])
    if code != 0:
        payload["status"] = "auth_or_cli_error"
        payload["error"] = (err or out).strip()[:400]
        return payload

    rows = json.loads(out or "[]")
    if isinstance(rows, dict):
        rows = [rows]
    slim = []
    for r in rows:
        slim.append(
            {
                "id": r.get("id"),
                "actual_status": r.get("actual_status"),
                "gpu_name": r.get("gpu_name"),
                "gpu_ram": r.get("gpu_ram"),
                "gpu_util": r.get("gpu_util"),
                "ssh_host": r.get("ssh_host"),
                "ssh_port": r.get("ssh_port"),
                "direct_port_start": r.get("direct_port_start"),
                "direct_port_end": r.get("direct_port_end"),
            }
        )
    payload["instances"] = slim
    payload["instance_count"] = len(slim)
    payload["status"] = "ok"
    return payload


def write_reports(out_json: Path, out_md: Path) -> None:
    p = collect()
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(p, indent=2), encoding="utf-8")

    lines = [
        "# Vast CLI Instrumentation",
        "",
        f"- generated_at: {p['generated_at']}",
        f"- status: {p['status']}",
        f"- vastai_in_path: {'yes' if p['vastai_in_path'] else 'no'}",
        f"- vast_api_key_present: {'yes' if p['vast_api_key_present'] else 'no'}",
        f"- instance_count: {p['instance_count']}",
    ]
    if p.get("error"):
        lines += ["", "## Error", "", "```", str(p["error"]), "```"]

    lines += [
        "",
        "## Instances",
        "",
        "| ID | Status | GPU | VRAM | GPU util | SSH | Ports |",
        "|---:|---|---|---:|---:|---|---|",
    ]
    for r in p.get("instances", []):
        lines.append(
            "| {id} | {actual_status} | {gpu_name} | {gpu_ram} | {gpu_util} | {ssh_host}:{ssh_port} | {direct_port_start}-{direct_port_end} |".format(
                **{k: ("" if v is None else v) for k, v in r.items()}
            )
        )

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"vast_json={out_json}")
    print(f"vast_md={out_md}")


def main() -> None:
    out_json = Path(os.getenv("CI_VAST_JSON", "reports/ci/vast_status.json"))
    out_md = Path(os.getenv("CI_VAST_MD", "reports/ci/vast_status.md"))
    write_reports(out_json, out_md)


if __name__ == "__main__":
    main()

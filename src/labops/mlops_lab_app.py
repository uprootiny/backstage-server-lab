"""
MLOps Lab — Dev Journal, Logs, Timeline, GPU Status, Service Health, Docs Browser.

Run:
    streamlit run src/labops/mlops_lab_app.py --server.port 8523 --server.address 0.0.0.0
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs"
ARTIFACTS = ROOT / "artifacts"
EVENTS_PATH = ARTIFACTS / "operator_events.jsonl"
PARALLEL_LEDGER = ARTIFACTS / "kaggle_parallel" / "ledger.jsonl"
SCORING_LEDGER = ARTIFACTS / "kaggle_scoring_ledger.jsonl"
LOGS_DIR = Path("/workspace/logs")
REPO_LOGS = ROOT / "logs"

st.set_page_config(
    page_title="MLOps Lab",
    page_icon="⚙",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── dark phosphor CSS ────────────────────────────────────────────────────────
st.markdown("""
<style>
    [data-testid="stSidebar"] { background: #0a0f14; }
    .timeline-event { border-left: 3px solid #00ff88; padding: 4px 12px; margin: 4px 0; font-family: monospace; font-size: 0.82em; }
    .timeline-event.warning { border-left-color: #ffaa00; }
    .timeline-event.error { border-left-color: #ff4444; }
    .log-line { font-family: 'Fira Code', 'Cascadia Code', monospace; font-size: 0.78em; line-height: 1.3; }
    .metric-card { background: #111820; border: 1px solid #1a2a3a; border-radius: 8px; padding: 16px; margin: 4px; }
    .gpu-ok { color: #00ff88; } .gpu-warn { color: #ffaa00; } .gpu-err { color: #ff4444; }
</style>
""", unsafe_allow_html=True)

# ── sidebar nav ──────────────────────────────────────────────────────────────
pages = [
    "📓 Dev Journal",
    "⏱ Event Timeline",
    "📋 Log Browser",
    "🖥 GPU Status",
    "🩺 Service Health",
    "📚 Docs Browser",
    "🔁 Reboot Runbook",
]
page = st.sidebar.radio("Navigate", pages)
st.sidebar.markdown("---")
st.sidebar.caption(f"MLOps Lab · {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC")


# ── helpers ──────────────────────────────────────────────────────────────────
def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    events = []
    for line in path.read_text().strip().splitlines():
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events


def run_cmd(cmd: str, timeout: int = 10) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout + r.stderr
    except Exception as e:
        return f"ERROR: {e}"


def tail_file(path: Path, n: int = 100) -> str:
    if not path.exists():
        return f"(file not found: {path})"
    lines = path.read_text(errors="replace").splitlines()
    return "\n".join(lines[-n:])


def parse_journal_sections(text: str) -> list[dict]:
    """Split DEV_JOURNAL.md into sections by ## headers."""
    sections = []
    current: dict | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            if current:
                sections.append(current)
            current = {"title": line.lstrip("# ").strip(), "body": ""}
        elif current is not None:
            current["body"] += line + "\n"
    if current:
        sections.append(current)
    return sections


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE: Dev Journal
# ═══════════════════════════════════════════════════════════════════════════════
if page == "📓 Dev Journal":
    st.title("📓 Dev Journal")

    journal_path = DOCS_DIR / "DEV_JOURNAL.md"
    if not journal_path.exists():
        st.error("DEV_JOURNAL.md not found")
    else:
        text = journal_path.read_text()
        sections = parse_journal_sections(text)

        if not sections:
            st.markdown(text)
        else:
            # search/filter
            query = st.text_input("🔍 Search journal", placeholder="gpu, reboot, EGNN...")
            for sec in reversed(sections):  # most recent first
                if query and query.lower() not in (sec["title"] + sec["body"]).lower():
                    continue
                with st.expander(sec["title"], expanded=not query):
                    st.markdown(sec["body"])

    # git log timeline
    st.markdown("---")
    st.subheader("Git Commit History")
    git_log = run_cmd(f"git -C {ROOT} log --oneline --date=short --format='%h %ad %s' -30")
    if git_log.strip():
        for line in git_log.strip().splitlines():
            parts = line.split(" ", 2)
            if len(parts) == 3:
                sha, date, msg = parts
                st.markdown(f"`{sha}` **{date}** {msg}")
            else:
                st.text(line)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE: Event Timeline
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "⏱ Event Timeline":
    st.title("⏱ Event Timeline")

    # merge all event sources
    events = []
    for ev in load_jsonl(EVENTS_PATH):
        ev["_source"] = "operator"
        events.append(ev)
    for ev in load_jsonl(PARALLEL_LEDGER):
        ev["_source"] = "parallel"
        events.append(ev)
    for ev in load_jsonl(SCORING_LEDGER):
        ev["_source"] = "scoring"
        events.append(ev)

    if not events:
        st.info("No events found.")
    else:
        # filters
        col1, col2, col3 = st.columns(3)
        sources = sorted({e.get("_source", "?") for e in events})
        kinds = sorted({e.get("kind", e.get("event", "?")) for e in events})
        severities = sorted({e.get("severity", "info") for e in events})

        with col1:
            sel_sources = st.multiselect("Source", sources, default=sources)
        with col2:
            sel_kinds = st.multiselect("Kind", kinds, default=kinds)
        with col3:
            sel_sev = st.multiselect("Severity", severities, default=severities)

        filtered = [
            e for e in events
            if e.get("_source", "?") in sel_sources
            and e.get("kind", e.get("event", "?")) in sel_kinds
            and e.get("severity", "info") in sel_sev
        ]

        # sort by timestamp
        def get_ts(e):
            t = e.get("ts", e.get("timestamp", ""))
            return t if t else "0"

        filtered.sort(key=get_ts, reverse=True)

        st.caption(f"{len(filtered)} events")
        for ev in filtered[:200]:
            ts = ev.get("ts", ev.get("timestamp", "?"))
            kind = ev.get("kind", ev.get("event", "?"))
            sev = ev.get("severity", "info")
            msg = ev.get("message", ev.get("msg", json.dumps(ev, default=str)))
            source = ev.get("source", ev.get("_source", ""))

            css_class = "warning" if sev == "warning" else ("error" if sev == "error" else "")
            st.markdown(
                f'<div class="timeline-event {css_class}">'
                f'<b>{ts}</b> [{kind}] <i>{source}</i><br/>{msg}</div>',
                unsafe_allow_html=True,
            )


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE: Log Browser
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "📋 Log Browser":
    st.title("📋 Log Browser")

    # collect log files
    log_files: list[Path] = []
    if LOGS_DIR.exists():
        log_files.extend(sorted(LOGS_DIR.glob("*.log")))
    if REPO_LOGS.exists():
        log_files.extend(sorted(REPO_LOGS.glob("*.log")))

    if not log_files:
        st.warning("No log files found.")
    else:
        col1, col2 = st.columns([1, 3])
        with col1:
            names = [f.name for f in log_files]
            selected = st.radio("Log file", names)
            tail_n = st.slider("Lines", 50, 500, 100, 50)
            auto_refresh = st.checkbox("Auto-refresh (5s)")

        with col2:
            sel_path = next(f for f in log_files if f.name == selected)
            st.caption(f"{sel_path} · {sel_path.stat().st_size / 1024:.1f} KB")

            grep_q = st.text_input("Filter lines", placeholder="error, WARNING, gpu...")
            content = tail_file(sel_path, tail_n)

            if grep_q:
                content = "\n".join(
                    l for l in content.splitlines()
                    if grep_q.lower() in l.lower()
                )

            st.code(content, language="log")

            if auto_refresh:
                import time
                time.sleep(5)
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE: GPU Status
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "🖥 GPU Status":
    st.title("🖥 GPU Status")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("nvidia-smi")
        smi = run_cmd("nvidia-smi")
        if "ERR" in smi or "failed" in smi.lower():
            st.error("GPU is in error state!")
        st.code(smi, language="text")

    with col2:
        st.subheader("CUDA Check")
        cuda_check = run_cmd(
            'python3 -c "import torch; print(f\'available: {torch.cuda.is_available()}\'); '
            'print(f\'device: {torch.cuda.get_device_name(0)}\' if torch.cuda.is_available() else \'no cuda\'); '
            'print(f\'vram_alloc: {torch.cuda.memory_allocated(0)/1e9:.2f} GB\' if torch.cuda.is_available() else \'\'); '
            'print(f\'vram_reserved: {torch.cuda.memory_reserved(0)/1e9:.2f} GB\' if torch.cuda.is_available() else \'\')"'
        )
        st.code(cuda_check, language="text")

    st.markdown("---")
    st.subheader("GPU Processes")
    procs = run_cmd("nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv,noheader 2>/dev/null || echo 'no processes'")
    st.code(procs, language="text")

    st.subheader("dmesg Xid Errors")
    xid = run_cmd("dmesg 2>/dev/null | grep -i xid | tail -20 || echo 'no xid errors (or no access)'")
    st.code(xid, language="text")

    st.subheader("VRAM Headroom Policy")
    vram_info = run_cmd("nvidia-smi --query-gpu=memory.free,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null")
    if vram_info.strip() and "failed" not in vram_info.lower():
        try:
            parts = [int(x.strip()) for x in vram_info.strip().split(",")]
            free_mb, used_mb, total_mb = parts[0], parts[1], parts[2]
            pct = used_mb / total_mb * 100 if total_mb else 0
            st.progress(pct / 100, text=f"VRAM: {used_mb} MB used / {total_mb} MB total ({free_mb} MB free)")
            if free_mb < 2048:
                st.warning(f"⚠ Low VRAM headroom: {free_mb} MB free (policy: keep >2048 MB)")
            else:
                st.success(f"✓ VRAM headroom OK: {free_mb} MB free")
        except (ValueError, IndexError):
            st.text(vram_info)

    if st.button("🔄 Refresh"):
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE: Service Health
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "🩺 Service Health":
    st.title("🩺 Service Health")

    services = [
        ("Streamlit Mashup", 1111, "/"),
        ("TensorBoard", 6006, "/"),
        ("Portal", 8520, "/"),
        ("Notebook Lab", 8521, "/"),
        ("Validation", 8522, "/"),
        ("Grafana", 3000, "/api/health"),
        ("Prometheus", 9090, "/-/healthy"),
        ("Node Exporter", 9100, "/metrics"),
        ("MLOps Lab", 8523, "/"),
    ]

    cols = st.columns(3)
    for i, (name, port, path) in enumerate(services):
        with cols[i % 3]:
            code = run_cmd(f"curl -sf -o /dev/null -w '%{{http_code}}' --max-time 2 http://localhost:{port}{path} 2>/dev/null || echo '---'").strip()
            if code.startswith("2") or code.startswith("3"):
                st.success(f"**{name}** :{port} → {code}")
            elif code == "---":
                st.error(f"**{name}** :{port} → DOWN")
            else:
                st.warning(f"**{name}** :{port} → {code}")

    st.markdown("---")
    st.subheader("Port Mapping (Vast.ai)")
    port_map = {
        1111: 19121, 6006: 19448, 8080: 19808,
        8384: 19753, 19842: 19842, 22: 19636,
    }
    for local, ext in port_map.items():
        st.text(f"  :{local} → external :{ext}")
    st.caption("Ports not listed above are NOT externally accessible without a tunnel.")

    st.markdown("---")
    st.subheader("Supervisor Log (last 30 lines)")
    sup_log = Path("/workspace/logs/supervisor.log")
    st.code(tail_file(sup_log, 30), language="log")

    if st.button("🔄 Refresh"):
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE: Docs Browser
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "📚 Docs Browser":
    st.title("📚 Docs Browser")

    if not DOCS_DIR.exists():
        st.error("docs/ directory not found")
    else:
        docs = sorted(DOCS_DIR.glob("*.md"))
        if not docs:
            st.info("No markdown docs found.")
        else:
            query = st.text_input("🔍 Search docs", placeholder="gpu, pipeline, kaggle...")

            # group by prefix
            grouped: dict[str, list[Path]] = {}
            for d in docs:
                prefix = d.stem.split("_")[0] if "_" in d.stem else "general"
                grouped.setdefault(prefix, []).append(d)

            col1, col2 = st.columns([1, 3])
            with col1:
                names = [d.stem for d in docs]
                selected_doc = st.radio("Document", names)

            with col2:
                sel_doc_path = DOCS_DIR / f"{selected_doc}.md"
                content = sel_doc_path.read_text(errors="replace")

                if query:
                    # highlight search hits
                    lines = content.splitlines()
                    matching = [l for l in lines if query.lower() in l.lower()]
                    if matching:
                        st.caption(f"{len(matching)} matching lines")
                        st.markdown("\n".join(matching))
                    else:
                        st.info(f"No matches for '{query}' in {selected_doc}")
                else:
                    st.markdown(content)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE: Reboot Runbook
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "🔁 Reboot Runbook":
    st.title("🔁 GPU Reboot Runbook")

    st.markdown("""
### Quick Reference: Instance Recovery

**When GPU enters ERR state:**

```bash
# 1. From external machine (Contabo / Mac / anywhere with vastai CLI):
vastai stop instance 32817406
sleep 60
vastai start instance 32817406

# 2. Wait for SSH to come back, then:
ssh -p 19636 root@175.155.64.231
cd /workspace/backstage-server-lab
bash scripts/boot_all.sh

# 3. Verify:
nvidia-smi
python3 -c "import torch; print(torch.cuda.is_available())"
```

### What Does NOT Work
| Attempt | Result |
|---------|--------|
| `nvidia-smi -r` | "GPU reset not supported" |
| Kill CUDA processes | GPU stays in ERR |
| `rmmod nvidia` | Permission denied (container) |
| Wait it out | Xid faults don't self-heal |

### Prevention Checklist
- [ ] GPU watchdog cron running (check `nvidia-smi` every 2 min)
- [ ] VRAM headroom >2 GB before new jobs
- [ ] `dmesg | grep xid` clean
- [ ] Restart script pre-staged on Contabo
- [ ] Checkpoints saved every 10 epochs
- [ ] Don't run >2 training jobs concurrently

### Pre-Stage Restart on Contabo
```bash
# On Contabo (173.212.203.211), create ~/restart-vast-gpu.sh:
#!/bin/bash
vastai stop instance 32817406 && sleep 60 && vastai start instance 32817406
```

Then from the GPU instance (while alive):
```bash
ssh contabo 'bash ~/restart-vast-gpu.sh'
```
""")

    # live GPU check
    st.markdown("---")
    st.subheader("Current GPU State")
    smi = run_cmd("nvidia-smi --query-gpu=name,temperature.gpu,memory.used,memory.total,gpu_bus_id --format=csv,noheader 2>/dev/null || echo 'nvidia-smi failed'")
    if "failed" in smi.lower() or "ERR" in smi:
        st.error(f"🔴 GPU FAULT — reboot required\n```\n{smi}\n```")
    else:
        st.success(f"🟢 GPU healthy\n```\n{smi.strip()}\n```")

#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks/starters/04_interactive_pipeline_orchestrator.ipynb"

nb = {
    "cells": [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Interactive Notebook Orchestrator\\n",
                "Control source pulls, plan generation, and dispatch from one notebook."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "import json, subprocess, pathlib\\n",
                "import ipywidgets as widgets\\n",
                "from IPython.display import display, Markdown\\n",
                "ROOT = pathlib.Path('/workspace/backstage-server-lab') if pathlib.Path('/workspace/backstage-server-lab').exists() else pathlib.Path('.').resolve()\\n",
                "print('root=', ROOT)"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "workers = widgets.Dropdown(options=[3,10,12], value=3, description='workers')\\n",
                "profile = widgets.Dropdown(options=['three','ten','dozen'], value='three', description='profile')\\n",
                "pull_btn = widgets.Button(description='Pull Repos + Build Plan', button_style='primary')\\n",
                "dispatch_btn = widgets.Button(description='Dispatch Plan', button_style='success')\\n",
                "status_out = widgets.Output(layout={'border':'1px solid #333','height':'260px'})\\n",
                "display(widgets.HBox([workers, profile, pull_btn, dispatch_btn]), status_out)"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "def run_cmd(cmd):\\n",
                "    p = subprocess.run(cmd, cwd=ROOT, shell=True, text=True, capture_output=True)\\n",
                "    return p.returncode, p.stdout + p.stderr\\n",
                "\\n",
                "def on_pull(_):\\n",
                "    with status_out:\\n",
                "        status_out.clear_output()\\n",
                "        print('>>> pulling notebook sources and building plan')\\n",
                "        rc, out = run_cmd('python scripts/pull_notebook_sources.py')\\n",
                "        print(out)\\n",
                "        if rc == 0:\\n",
                "            plan = ROOT / 'artifacts/kaggle_parallel/plan.json'\\n",
                "            if plan.exists():\\n",
                "                j = json.loads(plan.read_text())\\n",
                "                print('jobs:', len(j.get('jobs', [])))\\n",
                "\\n",
                "def on_dispatch(_):\\n",
                "    with status_out:\\n",
                "        print(f'>>> dispatch profile={profile.value} workers={workers.value}')\\n",
                "        cmd = f\"PYTHONPATH=src /venv/main/bin/python -m labops.cli kaggle-parallel-dispatch --plan artifacts/kaggle_parallel/plan.json --workers {workers.value} --ledger artifacts/kaggle_parallel/ledger.jsonl\"\\n",
                "        rc, out = run_cmd(cmd)\\n",
                "        print(out)\\n",
                "\\n",
                "pull_btn.on_click(on_pull)\\n",
                "dispatch_btn.on_click(on_dispatch)\\n",
                "display(Markdown('Use **Pull Repos + Build Plan** then **Dispatch Plan**.'))"
            ]
        }
    ],
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.10"}
    },
    "nbformat": 4,
    "nbformat_minor": 5
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(nb, indent=2), encoding="utf-8")
print(f"wrote {OUT}")

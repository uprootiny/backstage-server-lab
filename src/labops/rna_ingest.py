from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


NT_MAP = {"A": "A", "U": "U", "G": "G", "C": "C", "T": "U"}
RES3 = {"A": "ADE", "U": "URA", "G": "GUA", "C": "CYT"}


def _nt3(nt: str) -> str:
    n = NT_MAP.get(nt.upper(), "A")
    return RES3[n]


def _pdb_line(serial: int, atom: str, resn: str, resi: int, x: float, y: float, z: float, b: float) -> str:
    return f"ATOM  {serial:5d} {atom:<4}{resn:>3} A{resi:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00{b:6.2f}           {atom[0]:>2}"


def _rows_to_pdb(rows: list[dict[str, Any]], out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    serial = 1
    for r in rows:
        atom = str(r.get("atom", "P"))
        resi = int(r.get("resi", serial))
        resn = str(r.get("resn", "A"))
        x = float(r.get("x", 0.0))
        y = float(r.get("y", 0.0))
        z = float(r.get("z", 0.0))
        b = float(r.get("b", 50.0))
        lines.append(_pdb_line(serial, atom, resn, resi, x, y, z, b))
        serial += 1
    lines.append("END")
    out.write_text("\n".join(lines) + "\n")
    return out


def _from_dataframe(df: pd.DataFrame, out: Path, default_seq: str = "") -> Path:
    required = {"x", "y", "z"}
    if not required.issubset(set(df.columns)):
        raise ValueError(f"expected columns including {required}; got {set(df.columns)}")
    rows: list[dict[str, Any]] = []
    for i, row in df.reset_index(drop=True).iterrows():
        resi = int(row["resi"]) if "resi" in df.columns else i + 1
        nt = str(row["resn"]) if "resn" in df.columns else (default_seq[resi - 1] if default_seq and resi - 1 < len(default_seq) else "A")
        atom = str(row["atom"]) if "atom" in df.columns else "C1'"
        b = float(row["b"]) if "b" in df.columns else 50.0
        rows.append(
            {
                "resi": resi,
                "resn": _nt3(nt) if len(nt) == 1 else nt,
                "atom": atom,
                "x": float(row["x"]),
                "y": float(row["y"]),
                "z": float(row["z"]),
                "b": b,
            }
        )
    return _rows_to_pdb(rows, out)


def ingest_result(input_path: Path, out_pdb: Path, default_seq: str = "") -> Path:
    ext = input_path.suffix.lower()
    if ext == ".pdb":
        out_pdb.parent.mkdir(parents=True, exist_ok=True)
        out_pdb.write_text(input_path.read_text())
        return out_pdb
    if ext == ".csv":
        return _from_dataframe(pd.read_csv(input_path), out_pdb, default_seq=default_seq)
    if ext in {".json", ".jsonl"}:
        payload = json.loads(input_path.read_text())
        if isinstance(payload, dict) and "atoms" in payload and isinstance(payload["atoms"], list):
            return _rows_to_pdb(payload["atoms"], out_pdb)
        if isinstance(payload, dict) and "coords" in payload:
            coords = np.array(payload["coords"], dtype=float)
            seq = str(payload.get("sequence", default_seq))
            rows = []
            for i, xyz in enumerate(coords):
                nt = seq[i] if i < len(seq) else "A"
                rows.append({"resi": i + 1, "resn": _nt3(nt), "atom": "C1'", "x": xyz[0], "y": xyz[1], "z": xyz[2], "b": 50.0})
            return _rows_to_pdb(rows, out_pdb)
        raise ValueError("unsupported json shape; expected {atoms:[...]} or {coords:[[x,y,z],...],sequence:'...'}")
    if ext in {".npy", ".npz"}:
        arr = np.load(input_path)
        if isinstance(arr, np.lib.npyio.NpzFile):
            if "coords" not in arr:
                raise ValueError("npz missing 'coords' array")
            coords = arr["coords"]
            seq = str(arr["sequence"][0]) if "sequence" in arr else default_seq
        else:
            coords = arr
            seq = default_seq
        if coords.ndim != 2 or coords.shape[1] != 3:
            raise ValueError(f"expected coords shape (N,3), got {coords.shape}")
        rows = []
        for i, xyz in enumerate(coords):
            nt = seq[i] if i < len(seq) else "A"
            rows.append({"resi": i + 1, "resn": _nt3(nt), "atom": "C1'", "x": float(xyz[0]), "y": float(xyz[1]), "z": float(xyz[2]), "b": 50.0})
        return _rows_to_pdb(rows, out_pdb)
    raise ValueError(f"unsupported input extension: {ext}")

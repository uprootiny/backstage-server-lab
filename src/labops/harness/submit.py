from __future__ import annotations

from pathlib import Path
import pandas as pd


def validate_submission_csv(path: Path) -> dict[str, int | bool]:
    df = pd.read_csv(path)
    cols = {str(c).lower() for c in df.columns}
    has_coords = {"x", "y", "z"}.issubset(cols) or (
        any(c.startswith("x_") for c in cols)
        and any(c.startswith("y_") for c in cols)
        and any(c.startswith("z_") for c in cols)
    )
    return {"rows": int(len(df)), "columns": int(len(df.columns)), "has_coordinates": bool(has_coords)}

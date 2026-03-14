from __future__ import annotations

from typing import Any


def validate_results(results: list[dict[str, Any]], min_score: float = 0.70) -> dict[str, Any]:
    if not results:
        return {"passed": False, "reason": "no_results", "passing": 0, "total": 0}
    passing = [r for r in results if float(r.get("score", 0.0)) >= min_score]
    return {
        "passed": len(passing) > 0,
        "reason": "ok" if passing else "no_variant_met_threshold",
        "passing": len(passing),
        "total": len(results),
    }

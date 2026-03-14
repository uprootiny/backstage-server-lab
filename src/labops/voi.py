from __future__ import annotations


def value_of_information(uncertainty: float, expected_improvement: float, importance: float) -> float:
    u = max(0.0, min(1.0, uncertainty))
    e = max(0.0, expected_improvement)
    i = max(0.0, importance)
    return u * e * i

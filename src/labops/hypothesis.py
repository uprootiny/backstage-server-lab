from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Hypothesis:
    statement: str
    question: str
    status: str = "untested"
    evidence: list[str] = field(default_factory=list)

    def add_evidence(self, item: str) -> None:
        self.evidence.append(item)
        if self.status == "untested":
            self.status = "in_review"

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class GradingScheme:
    min_total_per_subject: int = 40
    min_external_per_subject: int = 35


# Example subject credits mapping; replace with real data as needed
DEFAULT_SUBJECT_CREDITS: Dict[str, int] = {
    # "21MAT11": 3,
    # "21PHY12": 3,
}




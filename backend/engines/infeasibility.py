"""Pre-generation infeasibility report models.

Exposes a deterministic schema that the smart-scheduling engine populates
before running ``generate_timetable``. Each report contains zero or more
``InfeasibilityIssue`` records. Issues with severity ``"blocker"`` cause
``blocks_generation=True`` and the generation endpoints abort with HTTP
422 (``GENERATION_BLOCKED``). Issues with severity ``"advisory"`` are
informational only and never block generation.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field


class InfeasibilityIssue(BaseModel):
    code: str  # "INF-01" .. "INF-05" or "ADV-XX"
    severity: Literal["blocker", "advisory"]
    message_en: str
    message_ar: str
    refs: Dict[str, Any] = Field(default_factory=dict)


class InfeasibilityReport(BaseModel):
    blocks_generation: bool
    issues: List[InfeasibilityIssue] = Field(default_factory=list)
    computed_at: datetime

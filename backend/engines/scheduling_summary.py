"""Build the generation_summary object for a Hakeem timetable run.

Schema is defined in docs/superpowers/specs/2026-05-03-hakeem-engine-audit-design.md §6.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RejectionCounters:
    teacher_busy: int = 0
    class_busy: int = 0
    teacher_unavailable: int = 0
    max_consecutive_exceeded: int = 0
    max_per_day_exceeded: int = 0
    weekly_quota_exceeded: int = 0
    constraint_registry_rejected: int = 0
    no_eligible_teacher: int = 0

    def as_dict(self) -> Dict[str, int]:
        return {
            "teacher_busy": self.teacher_busy,
            "class_busy": self.class_busy,
            "teacher_unavailable": self.teacher_unavailable,
            "max_consecutive_exceeded": self.max_consecutive_exceeded,
            "max_per_day_exceeded": self.max_per_day_exceeded,
            "weekly_quota_exceeded": self.weekly_quota_exceeded,
            "constraint_registry_rejected": self.constraint_registry_rejected,
            "no_eligible_teacher": self.no_eligible_teacher,
        }


@dataclass
class TeacherPlacementRecord:
    teacher_id: str
    name: str
    by_day: Dict[str, int] = field(default_factory=dict)
    max_consecutive: int = 0
    gaps: int = 0

    def total_periods(self) -> int:
        return sum(self.by_day.values())

    def as_dict(self) -> Dict[str, Any]:
        return {
            "teacher_id": self.teacher_id,
            "name": self.name,
            "total_periods": self.total_periods(),
            "by_day": dict(self.by_day),
            "max_consecutive": self.max_consecutive,
            "gaps": self.gaps,
        }


def build_generation_summary(
    *,
    required: int,
    placed: int,
    elapsed_ms: int,
    fairness_score: int,
    constraints_evaluated: List[str],
    rejection_counters: RejectionCounters,
    teacher_records: List[TeacherPlacementRecord],
    unplaced_demands: List[Dict[str, Any]],
) -> Dict[str, Any]:
    failed = max(required - placed, 0)
    placement_rate: Optional[float]
    if required == 0:
        placement_rate = None
    else:
        placement_rate = round(placed / required, 3)

    return {
        "schema_version": 1,
        "totals": {
            "required": required,
            "placed": placed,
            "failed": failed,
            "placement_rate": placement_rate,
        },
        "elapsed_ms": elapsed_ms,
        "fairness": {
            "overall_score": fairness_score,
            "per_teacher": [r.as_dict() for r in teacher_records],
        },
        "rejections_by_reason": rejection_counters.as_dict(),
        "constraints_evaluated": list(constraints_evaluated),
        "unplaced_demands": list(unplaced_demands),
    }

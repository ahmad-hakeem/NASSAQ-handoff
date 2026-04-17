"""Types for the hard-constraint registry."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional, Set

from engines.smart_scheduling_engine import ConflictSeverity


@dataclass
class ConstraintContext:
    school_id: str
    sessions: List[Dict[str, Any]] = field(default_factory=list)
    demands: List[Dict[str, Any]] = field(default_factory=list)
    resources: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    time_slots: List[Dict[str, Any]] = field(default_factory=list)
    settings: Dict[str, Any] = field(default_factory=dict)
    active_validation_keys: Set[str] = field(default_factory=set)


@dataclass(frozen=True)
class ConstraintViolation:
    code: str
    validation_key: str
    severity: ConflictSeverity
    message_en: str
    message_ar: str
    refs: Dict[str, Any] = field(default_factory=dict)
    tier: Literal["placement", "full"] = "full"


@dataclass(frozen=True)
class ValidatorMeta:
    code: str
    validation_key: str
    severity: ConflictSeverity
    tier: Literal["placement", "full"]
    fn: Callable[..., List[ConstraintViolation]]

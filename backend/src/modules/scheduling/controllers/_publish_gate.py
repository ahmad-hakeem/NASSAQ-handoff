"""Shared publish-gate helper.

`assert_publishable` is the single point that every publish endpoint MUST
call before flipping a timetable to ``status="published"``. It delegates
the decision to ``engine.validate_before_publish``, which dispatches the
HardConstraintRegistry and partitions HIGH/CRITICAL violations as
blocking.
"""

from fastapi import HTTPException


async def assert_publishable(engine, *, school_id: str, timetable_id: str) -> None:
    result = await engine.validate_before_publish(
        school_id=school_id, timetable_id=timetable_id
    )
    if result.get("is_publishable", True):
        return
    raise HTTPException(
        status_code=409,
        detail={
            "code": "PUBLISH_BLOCKED",
            "message_en": "Timetable cannot be published due to active hard-constraint violations.",
            "message_ar": "لا يمكن نشر الجدول بسبب وجود انتهاكات نشطة لقيود ثابتة.",
            "violations": result.get("violations", []),
            "warnings": result.get("warnings", []),
        },
    )

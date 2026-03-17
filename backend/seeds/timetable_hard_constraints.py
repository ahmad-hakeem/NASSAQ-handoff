"""
القيود الإلزامية لإنشاء الجدول الدراسي
Hard Constraints — School Timetable

هذه القيود هي قواعد نظام ثابتة لا يمكن تجاوزها عند إنشاء أو نشر الجدول الدراسي.
These are system-level rules that MUST be enforced during timetable generation and publishing.
"""

from datetime import datetime, timezone

TIMETABLE_HARD_CONSTRAINTS = [
    {
        "code": "HC-01",
        "name_ar": "تعارض المعلمين",
        "name_en": "Teacher Conflict",
        "description_ar": "لا يمكن إسناد أكثر من حصة لنفس المعلم في نفس الوقت، لأن المعلم يجب أن يكون في مكان واحد فقط خلال كل فترة زمنية. إذا كان المعلم مرتبطًا بحصة في نفس اليوم ونفس رقم الحصة، يُمنع إسناده إلى أي حصة أخرى في نفس الوقت سواء كانت لفصل آخر أو مادة أخرى أو قاعة أخرى.",
        "description_en": "A teacher cannot be assigned to more than one session in the same time slot because a teacher must be in only one place during each period. If a teacher is linked to a session on the same day and same period number, they are blocked from any other assignment at that time regardless of class, subject, or room.",
        "category": "resource_conflict",
        "applies_to": ["teacher"],
        "severity": "critical",
        "is_system": True,
        "is_active": True,
        "can_disable": False,
        "validation_key": "teacher_overlap",
        "order": 1
    },
    {
        "code": "HC-02",
        "name_ar": "تعارض الفصول",
        "name_en": "Class Conflict",
        "description_ar": "لا يمكن تعيين فصل واحد لأكثر من حصة في نفس الفترة الزمنية. الفصل يجب أن يكون مرتبطًا بحصة واحدة فقط في كل فترة زمنية.",
        "description_en": "A class cannot be assigned to more than one session in the same time slot. A class must have exactly one session per time slot.",
        "category": "resource_conflict",
        "applies_to": ["class"],
        "severity": "critical",
        "is_system": True,
        "is_active": True,
        "can_disable": False,
        "validation_key": "class_overlap",
        "order": 2
    },
    {
        "code": "HC-03",
        "name_ar": "تعارض القاعات",
        "name_en": "Room Conflict",
        "description_ar": "لا يمكن استخدام نفس القاعة الدراسية لأكثر من حصة في نفس الوقت.",
        "description_en": "The same room cannot be used for more than one session at the same time.",
        "category": "resource_conflict",
        "applies_to": ["room"],
        "severity": "critical",
        "is_system": True,
        "is_active": True,
        "can_disable": False,
        "validation_key": "room_overlap",
        "order": 3
    },
    {
        "code": "HC-04",
        "name_ar": "الالتزام بأوقات اليوم الدراسي",
        "name_en": "School Day Boundaries",
        "description_ar": "لا يمكن وضع أي حصة قبل بداية اليوم الدراسي أو بعد نهاية اليوم الدراسي. جميع الحصص يجب أن تقع داخل الفترات الزمنية المحددة في إعدادات المدرسة.",
        "description_en": "No session can be placed before the start or after the end of the school day. All sessions must fall within the time slots defined in school settings.",
        "category": "time_boundary",
        "applies_to": ["session"],
        "severity": "critical",
        "is_system": True,
        "is_active": True,
        "can_disable": False,
        "validation_key": "school_day_boundary",
        "order": 4
    },
    {
        "code": "HC-05",
        "name_ar": "منع الحصص أثناء الفترات غير الدراسية",
        "name_en": "No Sessions During Non-Teaching Periods",
        "description_ar": "لا يمكن وضع أي حصة داخل وقت الاستراحة أو وقت الصلاة أو أي فترة غير مخصصة للتدريس. هذه الفترات تعتبر مغلقة للتدريس داخل النظام.",
        "description_en": "No session can be placed during break time, prayer time, or any non-teaching period. These periods are closed for teaching within the system.",
        "category": "time_boundary",
        "applies_to": ["session"],
        "severity": "critical",
        "is_system": True,
        "is_active": True,
        "can_disable": False,
        "validation_key": "non_teaching_period",
        "order": 5
    },
    {
        "code": "HC-06",
        "name_ar": "احترام عدد الحصص اليومية",
        "name_en": "Daily Period Limit",
        "description_ar": "عدد الحصص في اليوم يجب أن يطابق القيمة المحددة في إعدادات الجدول. مثال: إذا كان اليوم الدراسي يحتوي على 7 حصص، فلا يمكن إضافة حصة ثامنة.",
        "description_en": "The number of periods per day must match the value set in timetable settings. E.g., if the school day has 7 periods, no 8th period can be added.",
        "category": "capacity",
        "applies_to": ["class"],
        "severity": "critical",
        "is_system": True,
        "is_active": True,
        "can_disable": False,
        "validation_key": "daily_period_limit",
        "order": 6
    },
    {
        "code": "HC-07",
        "name_ar": "احترام أيام العمل الرسمية",
        "name_en": "Working Days Compliance",
        "description_ar": "لا يمكن وضع حصص دراسية في أيام العطلة الأسبوعية أو أيام الإجازات الرسمية أو أي يوم غير محدد كيوم دراسي في إعدادات المدرسة.",
        "description_en": "No sessions can be placed on weekly holidays, official holidays, or any day not designated as a working day in school settings.",
        "category": "time_boundary",
        "applies_to": ["session"],
        "severity": "critical",
        "is_system": True,
        "is_active": True,
        "can_disable": False,
        "validation_key": "working_days",
        "order": 7
    },
    {
        "code": "HC-08",
        "name_ar": "عدم تجاوز النصاب الأسبوعي للمعلم",
        "name_en": "Teacher Weekly Load Limit",
        "description_ar": "لا يمكن أن يتجاوز المعلم عدد الحصص الأسبوعية المسموح بها. إذا كان النصاب المحدد للمعلم 20 حصة أسبوعيًا، فلا يمكن إسناد أكثر من ذلك.",
        "description_en": "A teacher cannot exceed their allowed weekly session count. If the teacher's quota is 20 sessions/week, no more than 20 can be assigned.",
        "category": "workload",
        "applies_to": ["teacher"],
        "severity": "critical",
        "is_system": True,
        "is_active": True,
        "can_disable": False,
        "validation_key": "teacher_weekly_load",
        "order": 8
    },
    {
        "code": "HC-09",
        "name_ar": "احترام عدد الحصص الأسبوعية لكل مادة",
        "name_en": "Subject Weekly Period Compliance",
        "description_ar": "كل مادة دراسية يجب أن تظهر في الجدول بعدد الحصص المحدد لها في المنهج الرسمي. مثال: الرياضيات = 5 حصص أسبوعيًا، اللغة العربية = 6 حصص أسبوعيًا. لا يمكن أن يكون العدد أقل أو أكثر.",
        "description_en": "Each subject must appear in the timetable with the exact number of periods defined in the official curriculum. E.g., Math = 5/week, Arabic = 6/week. Cannot be less or more.",
        "category": "curriculum",
        "applies_to": ["subject", "class"],
        "severity": "critical",
        "is_system": True,
        "is_active": True,
        "can_disable": False,
        "validation_key": "subject_weekly_periods",
        "order": 9
    },
    {
        "code": "HC-10",
        "name_ar": "منع تكرار المادة في حصتين متتاليتين",
        "name_en": "No Consecutive Same Subject",
        "description_ar": "لا يمكن إعطاء نفس المادة لفصل واحد في حصتين متتاليتين. مثال غير مسموح: الحصة الثانية → رياضيات، الحصة الثالثة → رياضيات. إلا إذا كان النظام يسمح بذلك صراحة في إعدادات خاصة.",
        "description_en": "The same subject cannot be assigned to a class in two consecutive periods. E.g., Period 2 → Math, Period 3 → Math is not allowed, unless explicitly permitted in special settings.",
        "category": "distribution",
        "applies_to": ["subject", "class"],
        "severity": "critical",
        "is_system": True,
        "is_active": True,
        "can_disable": True,
        "override_setting": "allow_consecutive_same_subject",
        "validation_key": "no_consecutive_subject",
        "order": 10
    },
    {
        "code": "HC-11",
        "name_ar": "احترام تخصص المعلم",
        "name_en": "Teacher Subject Qualification",
        "description_ar": "لا يمكن إسناد مادة إلى معلم غير مسند له تدريسها. يجب أن يكون المعلم مرتبطًا بالمادة في نظام Teacher Subject Assignment.",
        "description_en": "A subject cannot be assigned to a teacher who is not qualified to teach it. The teacher must be linked to the subject in the Teacher Subject Assignment system.",
        "category": "assignment",
        "applies_to": ["teacher", "subject"],
        "severity": "critical",
        "is_system": True,
        "is_active": True,
        "can_disable": False,
        "validation_key": "teacher_subject_match",
        "order": 11
    },
    {
        "code": "HC-12",
        "name_ar": "احترام إسناد المعلم للفصل",
        "name_en": "Teacher Class Assignment",
        "description_ar": "لا يمكن إسناد حصة لفصل إذا لم يكن المعلم مربوطًا بهذا الفصل أو المادة لهذا الفصل داخل النظام.",
        "description_en": "A session cannot be assigned to a class if the teacher is not linked to that class or the subject for that class in the system.",
        "category": "assignment",
        "applies_to": ["teacher", "class"],
        "severity": "critical",
        "is_system": True,
        "is_active": True,
        "can_disable": False,
        "validation_key": "teacher_class_assignment",
        "order": 12
    },
    {
        "code": "HC-13",
        "name_ar": "عدم وجود فترات مزدوجة لنفس المورد",
        "name_en": "No Double-Booking Any Resource",
        "description_ar": "أي مورد داخل الجدول (معلم – فصل – قاعة) يجب أن يكون مرتبطًا بحصة واحدة فقط في كل فترة زمنية.",
        "description_en": "Any resource in the timetable (teacher, class, room) must be linked to exactly one session per time slot.",
        "category": "resource_conflict",
        "applies_to": ["teacher", "class", "room"],
        "severity": "critical",
        "is_system": True,
        "is_active": True,
        "can_disable": False,
        "validation_key": "resource_single_booking",
        "order": 13
    },
    {
        "code": "HC-14",
        "name_ar": "اكتمال جميع الحصص المطلوبة",
        "name_en": "Complete Schedule Requirement",
        "description_ar": "لا يمكن نشر جدول ناقص. كل فصل يجب أن يحصل على جميع الحصص الأسبوعية المطلوبة وجميع المواد المحددة في المنهج.",
        "description_en": "An incomplete timetable cannot be published. Every class must receive all required weekly sessions and all subjects defined in the curriculum.",
        "category": "completeness",
        "applies_to": ["timetable"],
        "severity": "critical",
        "is_system": True,
        "is_active": True,
        "can_disable": False,
        "validation_key": "schedule_completeness",
        "order": 14
    },
    {
        "code": "HC-15",
        "name_ar": "عدم وجود حصص خارج الهيكل الأكاديمي",
        "name_en": "Academic Structure Compliance",
        "description_ar": "لا يمكن إضافة مادة غير موجودة في الهيكل الأكاديمي أو المنهج الرسمي إلى جدول أي فصل.",
        "description_en": "No subject outside the academic structure or official curriculum can be added to any class timetable.",
        "category": "curriculum",
        "applies_to": ["subject"],
        "severity": "critical",
        "is_system": True,
        "is_active": True,
        "can_disable": False,
        "validation_key": "academic_structure_match",
        "order": 15
    },
    {
        "code": "HC-16",
        "name_ar": "صحة العلاقات بين الكيانات",
        "name_en": "Entity Relationship Integrity",
        "description_ar": "أي حصة في الجدول يجب أن تحتوي على فصل صحيح ومادة صحيحة ومعلم صحيح وفترة زمنية صحيحة. لا يمكن إنشاء حصة تحتوي على بيانات ناقصة.",
        "description_en": "Every session in the timetable must have a valid class, subject, teacher, and time slot. No session can be created with incomplete data.",
        "category": "data_integrity",
        "applies_to": ["session"],
        "severity": "critical",
        "is_system": True,
        "is_active": True,
        "can_disable": False,
        "validation_key": "entity_integrity",
        "order": 16
    },
    {
        "code": "HC-17",
        "name_ar": "منع نشر الجدول عند وجود تعارض",
        "name_en": "Block Publishing With Conflicts",
        "description_ar": "إذا اكتشف النظام أي خرق لأي من القيود السابقة، يجب أن يمنع نشر الجدول ويعرض رسالة واضحة توضح نوع المشكلة ويحدد مكان التعارض داخل الجدول.",
        "description_en": "If the system detects any violation of the above constraints, it must block timetable publishing, display a clear message explaining the issue, and identify the conflict location within the timetable.",
        "category": "publishing",
        "applies_to": ["timetable"],
        "severity": "critical",
        "is_system": True,
        "is_active": True,
        "can_disable": False,
        "validation_key": "block_publish_on_conflict",
        "order": 17
    }
]


async def seed_hard_constraints(db):
    """
    تثبيت القيود الإلزامية في قاعدة البيانات
    Seed hard constraints into the database.
    Only inserts if not already present (idempotent).
    """
    collection = db.timetable_hard_constraints
    now = datetime.now(timezone.utc).isoformat()

    inserted = 0
    updated = 0
    for constraint in TIMETABLE_HARD_CONSTRAINTS:
        existing = await collection.find_one({"code": constraint["code"]})
        if existing:
            await collection.update_one(
                {"code": constraint["code"]},
                {"$set": {
                    **constraint,
                    "updated_at": now
                }}
            )
            updated += 1
        else:
            await collection.insert_one({
                **constraint,
                "created_at": now,
                "updated_at": now
            })
            inserted += 1

    await collection.create_index("code", unique=True)
    await collection.create_index("validation_key")
    await collection.create_index("category")
    await collection.create_index("is_active")

    if inserted == 0 and updated == len(TIMETABLE_HARD_CONSTRAINTS):
        return {"status": "already_seeded", "count": updated}
    return {"status": "seeded", "inserted": inserted, "updated": updated, "total": len(TIMETABLE_HARD_CONSTRAINTS)}

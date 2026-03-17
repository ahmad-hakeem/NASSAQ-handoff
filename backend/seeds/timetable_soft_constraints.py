"""
القيود التفضيلية لإنشاء الجدول الدراسي
Soft Constraints — School Timetable

هذه القيود تفضيلية يسعى النظام لتحقيقها قدر الإمكان لتحسين جودة الجدول.
These are preference-level rules the system tries to satisfy to improve timetable quality.
"""

from datetime import datetime, timezone

TIMETABLE_SOFT_CONSTRAINTS = [
    {
        "code": "SC-01",
        "name_ar": "عدم تكرار المادة في حصتين متتاليتين",
        "name_en": "No Consecutive Same Subject",
        "description_ar": "تجنب جدولة نفس المادة في حصتين متتاليتين لنفس الفصل في نفس اليوم، لتنويع تجربة التعلم.",
        "description_en": "Avoid scheduling the same subject in two consecutive periods for the same class on the same day.",
        "category": "distribution",
        "applies_to": ["class", "subject"],
        "weight": 8,
        "is_active": True,
        "can_disable": True,
        "scoring_key": "no_consecutive_same_subject",
        "order": 1
    },
    {
        "code": "SC-02",
        "name_ar": "توزيع متوازن للمواد خلال الأسبوع",
        "name_en": "Balanced Weekly Subject Distribution",
        "description_ar": "توزيع حصص كل مادة بشكل متوازن عبر أيام الأسبوع بدلاً من تكديسها في يوم واحد.",
        "description_en": "Distribute each subject's sessions evenly across the week rather than clustering them.",
        "category": "distribution",
        "applies_to": ["class", "subject"],
        "weight": 9,
        "is_active": True,
        "can_disable": True,
        "scoring_key": "balanced_weekly_distribution",
        "order": 2
    },
    {
        "code": "SC-03",
        "name_ar": "تقليل فراغات المعلمين",
        "name_en": "Minimize Teacher Gaps",
        "description_ar": "تقليل الفترات الفارغة بين حصص المعلم في نفس اليوم لتجنب أوقات الانتظار الطويلة.",
        "description_en": "Minimize idle gaps between a teacher's sessions on the same day to avoid long waiting times.",
        "category": "teacher_comfort",
        "applies_to": ["teacher"],
        "weight": 7,
        "is_active": True,
        "can_disable": True,
        "scoring_key": "minimize_teacher_gaps",
        "order": 3
    },
    {
        "code": "SC-04",
        "name_ar": "تقليل فراغات الفصول",
        "name_en": "Minimize Class Gaps",
        "description_ar": "تقليل الفترات الفارغة في جدول الفصل بحيث تكون الحصص متتالية قدر الإمكان.",
        "description_en": "Minimize empty periods in a class schedule so sessions are as contiguous as possible.",
        "category": "distribution",
        "applies_to": ["class"],
        "weight": 6,
        "is_active": True,
        "can_disable": True,
        "scoring_key": "minimize_class_gaps",
        "order": 4
    },
    {
        "code": "SC-05",
        "name_ar": "المواد الصعبة في الحصص المبكرة",
        "name_en": "Hard Subjects in Early Periods",
        "description_ar": "جدولة المواد الأساسية والصعبة (رياضيات، علوم، لغة عربية) في الحصص الأولى من اليوم عندما يكون تركيز الطلاب أعلى.",
        "description_en": "Schedule core/difficult subjects in early periods when student concentration is highest.",
        "category": "pedagogy",
        "applies_to": ["class", "subject"],
        "weight": 5,
        "is_active": True,
        "can_disable": True,
        "scoring_key": "hard_subjects_early",
        "order": 5
    },
    {
        "code": "SC-06",
        "name_ar": "تقليل الحصص المتتالية للمعلم",
        "name_en": "Limit Consecutive Teacher Sessions",
        "description_ar": "تجنب تحميل المعلم بأكثر من 3 حصص متتالية بدون استراحة لضمان جودة التدريس.",
        "description_en": "Avoid giving a teacher more than 3 consecutive sessions without a break.",
        "category": "teacher_comfort",
        "applies_to": ["teacher"],
        "weight": 7,
        "is_active": True,
        "can_disable": True,
        "scoring_key": "limit_consecutive_teacher",
        "order": 6
    },
    {
        "code": "SC-07",
        "name_ar": "توزيع عادل لحصص الصباح الباكر",
        "name_en": "Fair First Period Distribution",
        "description_ar": "توزيع الحصة الأولى بين المعلمين بشكل عادل بدلاً من تحميل معلم واحد بحصص الصباح كل يوم.",
        "description_en": "Distribute first-period sessions fairly among teachers instead of burdening one teacher every morning.",
        "category": "fairness",
        "applies_to": ["teacher"],
        "weight": 4,
        "is_active": True,
        "can_disable": True,
        "scoring_key": "fair_first_period",
        "order": 7
    },
    {
        "code": "SC-08",
        "name_ar": "توزيع عادل لحصص نهاية اليوم",
        "name_en": "Fair Last Period Distribution",
        "description_ar": "توزيع الحصة الأخيرة بين المعلمين بشكل عادل.",
        "description_en": "Distribute last-period sessions fairly among teachers.",
        "category": "fairness",
        "applies_to": ["teacher"],
        "weight": 4,
        "is_active": True,
        "can_disable": True,
        "scoring_key": "fair_last_period",
        "order": 8
    },
    {
        "code": "SC-09",
        "name_ar": "تنويع المواد بعد الاستراحة",
        "name_en": "Diverse Subjects After Break",
        "description_ar": "تفضيل جدولة مادة مختلفة بعد فترة الاستراحة لتجديد نشاط الطلاب.",
        "description_en": "Prefer scheduling a different subject after break time to refresh student engagement.",
        "category": "pedagogy",
        "applies_to": ["class"],
        "weight": 3,
        "is_active": True,
        "can_disable": True,
        "scoring_key": "diverse_after_break",
        "order": 9
    },
    {
        "code": "SC-10",
        "name_ar": "توازن الحمل اليومي للمعلم",
        "name_en": "Balanced Daily Teacher Load",
        "description_ar": "توزيع حصص المعلم بشكل متوازن عبر أيام الأسبوع بدلاً من تكديسها في أيام معينة.",
        "description_en": "Distribute a teacher's sessions evenly across working days rather than clustering them.",
        "category": "teacher_comfort",
        "applies_to": ["teacher"],
        "weight": 8,
        "is_active": True,
        "can_disable": True,
        "scoring_key": "balanced_daily_teacher_load",
        "order": 10
    },
    {
        "code": "SC-11",
        "name_ar": "حصص التربية البدنية في أوقات مناسبة",
        "name_en": "PE in Appropriate Times",
        "description_ar": "تفضيل جدولة حصص التربية البدنية في الحصص الأخيرة أو بعد الاستراحة.",
        "description_en": "Prefer scheduling PE sessions in later periods or after breaks.",
        "category": "pedagogy",
        "applies_to": ["subject"],
        "weight": 3,
        "is_active": True,
        "can_disable": True,
        "scoring_key": "pe_appropriate_times",
        "order": 11
    },
    {
        "code": "SC-12",
        "name_ar": "تقليل انتقال المعلم بين الفصول المتباعدة",
        "name_en": "Minimize Teacher Travel",
        "description_ar": "في حال وجود مباني أو طوابق متعددة، تقليل انتقال المعلم بين فصول متباعدة في حصص متتالية.",
        "description_en": "When multiple buildings/floors exist, minimize teacher movement between distant classes in consecutive periods.",
        "category": "teacher_comfort",
        "applies_to": ["teacher"],
        "weight": 2,
        "is_active": True,
        "can_disable": True,
        "scoring_key": "minimize_teacher_travel",
        "order": 12
    },
]


async def seed_soft_constraints(database):
    collection = database.timetable_soft_constraints
    now = datetime.now(timezone.utc).isoformat()

    existing_count = await collection.count_documents({})
    if existing_count >= len(TIMETABLE_SOFT_CONSTRAINTS):
        return {"status": "already_seeded", "count": existing_count}

    inserted = 0
    updated = 0
    for constraint in TIMETABLE_SOFT_CONSTRAINTS:
        existing = await collection.find_one({"code": constraint["code"]})
        if existing:
            await collection.update_one(
                {"code": constraint["code"]},
                {"$set": {**constraint, "updated_at": now}}
            )
            updated += 1
        else:
            await collection.insert_one({**constraint, "created_at": now, "updated_at": now})
            inserted += 1

    await collection.create_index("code", unique=True)
    await collection.create_index("scoring_key")
    await collection.create_index("category")
    await collection.create_index("is_active")

    return {"status": "seeded", "inserted": inserted, "updated": updated, "total": len(TIMETABLE_SOFT_CONSTRAINTS)}

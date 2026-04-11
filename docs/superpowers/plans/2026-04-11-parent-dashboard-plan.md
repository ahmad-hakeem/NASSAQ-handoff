# Parent Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the parent portal with real-time student tracking, weekly analytics, communication center, student profile management, cumulative analytics, and AI chatbot.

**Architecture:** Extend the existing FastAPI backend with new parent-portal endpoints using `gd_*` data access helpers. Rebuild the React frontend parent dashboard using extracted components in `components/parent/`, a custom `useParentDashboard` hook for state management, and Recharts for visualizations. All UI follows Arabic-first RTL design with the existing shadcn/ui + Tailwind system.

**Tech Stack:** React, Tailwind CSS, shadcn/ui, Recharts, lucide-react, FastAPI, SQLAlchemy (async), OpenAI

---

### Task 1: Backend — Today Live Endpoint

**Files:**
- Modify: `backend/routes/parent_portal_routes.py`

- [ ] **Step 1: Add the `today-live` endpoint**

Add a new endpoint after the existing schedule endpoint (~line 414). This endpoint returns current class info, upcoming classes, school day progress, and performance indicator data for a specific child.

```python
@router.get("/child/{child_id}/today-live")
async def get_child_today_live(
    child_id: str,
    current_user: dict = Depends(require_roles([UserRole.PARENT]))
):
    """بيانات اليوم المباشرة للطالب"""
    parent_id = current_user.get("id")
    parent_phone = current_user.get("phone")
    school_id = current_user.get("tenant_id")

    child = await _verify_parent_access(parent_id, parent_phone, child_id, school_id)
    if not child:
        raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

    now = datetime.now(timezone(timedelta(hours=3)))  # Saudi Arabia timezone (AST)
    current_time = now.strftime("%H:%M")
    day_map = {6: "sunday", 0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday"}
    today_en = day_map.get(now.weekday(), "")

    # Get timetable sessions for today
    today_sessions = []
    if child.get("class_id") and today_en:
        timetable = await gd_find_one(db.session, "timetables", {
            "school_id": child.get("school_id", school_id),
            "status": "published"
        }) or await gd_find_one(db.session, "timetables", {
            "school_id": child.get("school_id", school_id)
        }, sort=[("created_at", -1)])

        if timetable:
            sessions = await gd_find(db.session, "timetable_sessions", {
                "timetable_id": timetable.get("id"),
                "class_id": child.get("class_id"),
                "day_of_week": today_en
            }, limit=20)

            sub_ids = list(set(s.get("subject_id") for s in sessions if s.get("subject_id")))
            tch_ids = list(set(s.get("teacher_id") for s in sessions if s.get("teacher_id")))
            subs = await gd_find(db.session, "subjects", {"id": {"$in": sub_ids}}, limit=50) if sub_ids else []
            tchs = await gd_find(db.session, "teachers", {"id": {"$in": tch_ids}}, limit=50) if tch_ids else []
            sub_map = {s["id"]: s.get("name_ar", s.get("name", "")) for s in subs}
            tch_map = {t["id"]: t.get("full_name", "") for t in tchs}

            for s in sorted(sessions, key=lambda x: x.get("period_number", 0)):
                today_sessions.append({
                    "period": s.get("period_number"),
                    "subject": sub_map.get(s.get("subject_id"), "غير محدد"),
                    "subject_id": s.get("subject_id"),
                    "teacher": tch_map.get(s.get("teacher_id"), "غير محدد"),
                    "teacher_id": s.get("teacher_id"),
                    "start_time": s.get("start_time"),
                    "end_time": s.get("end_time"),
                })

    # Determine current and upcoming classes
    current_class = None
    upcoming_classes = []
    completed_count = 0
    for session in today_sessions:
        start = session.get("start_time", "")
        end = session.get("end_time", "")
        if start and end:
            if current_time >= end:
                completed_count += 1
            elif start <= current_time < end:
                current_class = {**session, "is_current": True}
            else:
                upcoming_classes.append(session)

    # Performance indicator
    from datetime import date as date_type
    today_date = now.date()
    week_start = today_date - timedelta(days=today_date.weekday() + 1 if today_date.weekday() != 6 else 0)
    last_week_start = week_start - timedelta(days=7)
    last_week_end = week_start - timedelta(days=1)

    this_week_grades = await gd_find(db.session, "grades", {
        "student_id": child_id,
        "date": {"$gte": week_start.isoformat(), "$lte": today_date.isoformat()}
    }, limit=200)
    last_week_grades = await gd_find(db.session, "grades", {
        "student_id": child_id,
        "date": {"$gte": last_week_start.isoformat(), "$lte": last_week_end.isoformat()}
    }, limit=200)

    all_grades = await gd_find(db.session, "grades", {"student_id": child_id}, limit=500)
    overall_avg = round(sum(g.get("percentage", 0) for g in all_grades) / len(all_grades), 1) if all_grades else 0

    this_avg = round(sum(g.get("percentage", 0) for g in this_week_grades) / len(this_week_grades), 1) if this_week_grades else overall_avg
    last_avg = round(sum(g.get("percentage", 0) for g in last_week_grades) / len(last_week_grades), 1) if last_week_grades else this_avg

    trend = round(this_avg - last_avg, 1)

    if overall_avg >= 90:
        level = "ممتاز"
    elif overall_avg >= 80:
        level = "جيد جداً"
    elif overall_avg >= 70:
        level = "جيد ومستقر"
    elif overall_avg >= 60:
        level = "مقبول"
    else:
        level = "يحتاج تحسين"

    motivational_phrases = {
        "up": "استمروا على هذا التقدم الرائع! 🌟",
        "stable": "أداء مستقر، واصلوا الدعم 💪",
        "down": "لا تقلقوا، بالمتابعة سيتحسن الأداء 🌱"
    }
    if trend > 2:
        phrase = motivational_phrases["up"]
    elif trend < -2:
        phrase = motivational_phrases["down"]
    else:
        phrase = motivational_phrases["stable"]

    return {
        "student": {
            "name": child.get("full_name"),
            "school_name": child.get("school_name", ""),
            "grade_level": child.get("grade_level", child.get("grade", "")),
            "class_name": child.get("class_name", ""),
        },
        "school_day": {
            "today": today_en,
            "total_periods": len(today_sessions),
            "completed_periods": completed_count,
            "remaining_periods": len(upcoming_classes) + (1 if current_class else 0),
            "all_sessions": today_sessions,
            "is_school_day": today_en in day_map.values(),
            "server_time": current_time,
        },
        "current_class": current_class,
        "upcoming_classes": upcoming_classes,
        "performance": {
            "level": level,
            "overall_average": overall_avg,
            "trend": trend,
            "trend_direction": "up" if trend > 2 else ("down" if trend < -2 else "stable"),
            "phrase": phrase,
        }
    }
```

- [ ] **Step 2: Verify the endpoint works**

Run: `curl -s http://localhost:8000/parent-portal/child/TEST_ID/today-live -H "Authorization: Bearer TOKEN" | python -m json.tool`
Expected: JSON response with student, school_day, current_class, upcoming_classes, and performance objects.

---

### Task 2: Backend — Weekly Story Endpoint

**Files:**
- Modify: `backend/routes/parent_portal_routes.py`

- [ ] **Step 1: Add the `weekly-story` endpoint**

```python
@router.get("/child/{child_id}/weekly-story")
async def get_child_weekly_story(
    child_id: str,
    current_user: dict = Depends(require_roles([UserRole.PARENT]))
):
    """قصة الأسبوع للطالب"""
    parent_id = current_user.get("id")
    parent_phone = current_user.get("phone")
    school_id = current_user.get("tenant_id")

    child = await _verify_parent_access(parent_id, parent_phone, child_id, school_id)
    if not child:
        raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

    now = datetime.now(timezone(timedelta(hours=3)))
    today = now.date()
    # Week runs Saturday-Thursday (Saudi school week)
    days_since_saturday = (today.weekday() + 2) % 7
    week_start = today - timedelta(days=days_since_saturday)
    week_end = week_start + timedelta(days=4)  # Thursday

    # Participation
    participation = await gd_find(db.session, "participation_records", {
        "student_id": child_id,
        "created_at": {"$gte": week_start.isoformat(), "$lte": (week_end + timedelta(days=1)).isoformat()}
    }, limit=200)
    participation_count = len(participation)

    # Positive behaviors
    positive_behaviors = await gd_count(db.session, "behaviour_records", {
        "student_id": child_id,
        "type": "positive",
        "created_at": {"$gte": week_start.isoformat(), "$lte": (week_end + timedelta(days=1)).isoformat()}
    })

    # Skills from session interactions
    skills = await gd_find(db.session, "session_interactions", {
        "student_id": child_id,
        "created_at": {"$gte": week_start.isoformat(), "$lte": (week_end + timedelta(days=1)).isoformat()}
    }, limit=200)
    acquired_skills = list(set(
        s.get("skill_tag") for s in skills if s.get("skill_tag")
    ))

    # Grades this week by subject
    week_grades = await gd_find(db.session, "grades", {
        "student_id": child_id,
        "date": {"$gte": week_start.isoformat(), "$lte": week_end.isoformat()}
    }, limit=200)
    subject_scores = {}
    for g in week_grades:
        subj = g.get("subject_name") or g.get("subject_id", "عام")
        if subj not in subject_scores:
            subject_scores[subj] = []
        subject_scores[subj].append(g.get("percentage", 0))

    strong_subjects = []
    weak_subjects = []
    for subj, scores in subject_scores.items():
        avg = sum(scores) / len(scores) if scores else 0
        if avg >= 80:
            strong_subjects.append({"subject": subj, "average": round(avg, 1)})
        elif avg < 60:
            weak_subjects.append({"subject": subj, "average": round(avg, 1)})

    # Remedial plans
    remedial_plans = await gd_find(db.session, "student_plans", {
        "student_id": child_id,
        "plan_type": "remedial",
        "created_at": {"$gte": week_start.isoformat(), "$lte": (week_end + timedelta(days=1)).isoformat()}
    }, limit=20)

    # Daily breakdown for bar chart
    daily_data = []
    day_names_ar = ["السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس"]
    for i in range(6):
        day_date = week_start + timedelta(days=i)
        day_str = day_date.isoformat()
        day_participation = sum(1 for p in participation if p.get("created_at", "").startswith(day_str))
        day_behavior = await gd_count(db.session, "behaviour_records", {
            "student_id": child_id,
            "type": "positive",
            "created_at": {"$gte": day_str, "$lt": (day_date + timedelta(days=1)).isoformat()}
        })
        daily_data.append({
            "day": day_names_ar[i],
            "date": day_str,
            "participation": day_participation,
            "positive_behavior": day_behavior,
        })

    # Weekly tip
    tips = [
        "شجعوا أبناءكم على القراءة اليومية لمدة 15 دقيقة على الأقل",
        "احرصوا على مراجعة الواجبات مع أبنائكم يومياً",
        "النوم الكافي يعزز التركيز والتحصيل الدراسي",
        "شاركوا أبناءكم في حل المسائل الرياضية بطريقة ممتعة",
        "كلمة تشجيع واحدة تصنع فرقاً كبيراً في أداء الطالب",
    ]
    import hashlib
    tip_index = int(hashlib.md5(f"{child_id}-{week_start}".encode()).hexdigest(), 16) % len(tips)

    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "participation_count": participation_count,
        "positive_behaviors": positive_behaviors,
        "acquired_skills": acquired_skills,
        "strong_subjects": strong_subjects,
        "weak_subjects": weak_subjects,
        "remedial_plans": [
            {
                "id": p.get("id"),
                "title": p.get("title", "خطة علاجية"),
                "description": p.get("description", ""),
                "subject": p.get("subject", ""),
                "teacher_name": p.get("teacher_name", ""),
                "created_at": p.get("created_at"),
            }
            for p in remedial_plans
        ],
        "daily_chart_data": daily_data,
        "weekly_tip": tips[tip_index],
    }
```

- [ ] **Step 2: Verify the endpoint**

Test the endpoint returns valid weekly data structure.

---

### Task 3: Backend — Student Profile & Achievements Endpoints

**Files:**
- Modify: `backend/routes/parent_portal_routes.py`

- [ ] **Step 1: Add profile GET/PUT endpoints**

```python
@router.get("/child/{child_id}/profile")
async def get_child_profile(
    child_id: str,
    current_user: dict = Depends(require_roles([UserRole.PARENT]))
):
    """ملف الطالب الشخصي"""
    parent_id = current_user.get("id")
    parent_phone = current_user.get("phone")
    child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"))
    if not child:
        raise HTTPException(status_code=403, detail="غير مصرح")

    school_name = child.get("school_name", "")
    if not school_name:
        sid = child.get("school_id") or current_user.get("tenant_id")
        if sid:
            s_doc = await gd_find_one(db.session, "schools", {"id": sid})
            school_name = s_doc.get("name") if s_doc else ""

    return {
        "id": child.get("id"),
        "name": child.get("full_name"),
        "grade_level": child.get("grade_level", child.get("grade", "")),
        "class_name": child.get("class_name", ""),
        "school_name": school_name,
        "emoji": child.get("emoji", "👦"),
        "profile_picture": child.get("profile_picture", ""),
        "gender": child.get("gender", ""),
        "health_conditions": child.get("health_conditions", []),
        "behavioral_aspects": child.get("behavioral_aspects", []),
        "family_situation": child.get("family_situation", ""),
    }

@router.put("/child/{child_id}/profile")
async def update_child_profile(
    child_id: str,
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.PARENT]))
):
    """تعديل ملف الطالب"""
    parent_id = current_user.get("id")
    parent_phone = current_user.get("phone")
    child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"))
    if not child:
        raise HTTPException(status_code=403, detail="غير مصرح")

    allowed_fields = {"emoji", "health_conditions", "behavioral_aspects", "family_situation"}
    update_data = {k: v for k, v in data.items() if k in allowed_fields}

    if not update_data:
        raise HTTPException(status_code=400, detail="لا توجد بيانات صالحة للتحديث")

    await gd_update_one(db.session, "students", {"id": child_id}, {"$set": update_data})
    return {"success": True, "message": "تم تحديث الملف بنجاح"}
```

- [ ] **Step 2: Add achievements CRUD endpoints**

```python
@router.get("/child/{child_id}/achievements")
async def get_child_achievements(
    child_id: str,
    current_user: dict = Depends(require_roles([UserRole.PARENT]))
):
    """إنجازات الطالب"""
    parent_id = current_user.get("id")
    parent_phone = current_user.get("phone")
    child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"))
    if not child:
        raise HTTPException(status_code=403, detail="غير مصرح")

    achievements = await gd_find(
        db.session, "student_achievements",
        {"student_id": child_id},
        order_by="created_at", desc_order=True, limit=100
    )
    return {"achievements": achievements, "total": len(achievements)}

@router.post("/child/{child_id}/achievements")
async def add_child_achievement(
    child_id: str,
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.PARENT]))
):
    """إضافة إنجاز جديد"""
    parent_id = current_user.get("id")
    parent_phone = current_user.get("phone")
    school_id = current_user.get("tenant_id")
    child = await _verify_parent_access(parent_id, parent_phone, child_id, school_id)
    if not child:
        raise HTTPException(status_code=403, detail="غير مصرح")

    achievement = {
        "id": str(uuid.uuid4()),
        "student_id": child_id,
        "school_id": child.get("school_id", school_id),
        "name": data.get("name", ""),
        "type": data.get("type", "other"),
        "source": "parent",
        "source_user_id": parent_id,
        "file_url": data.get("file_url", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await gd_insert(db.session, "student_achievements", achievement)
    return {"success": True, "achievement": achievement}
```

---

### Task 4: Backend — Analytics & Communication Endpoints

**Files:**
- Modify: `backend/routes/parent_portal_routes.py`

- [ ] **Step 1: Add cumulative analytics endpoint**

```python
@router.get("/child/{child_id}/analytics")
async def get_child_analytics(
    child_id: str,
    current_user: dict = Depends(require_roles([UserRole.PARENT]))
):
    """تحليل أداء الطالب التراكمي"""
    parent_id = current_user.get("id")
    parent_phone = current_user.get("phone")
    school_id = current_user.get("tenant_id")
    child = await _verify_parent_access(parent_id, parent_phone, child_id, school_id)
    if not child:
        raise HTTPException(status_code=403, detail="غير مصرح")

    # All grades
    all_grades = await gd_find(db.session, "grades", {"student_id": child_id}, limit=1000)
    overall_avg = round(sum(g.get("percentage", 0) for g in all_grades) / len(all_grades), 1) if all_grades else 0

    # Subject breakdown for radar chart
    target_subjects = {"رياضيات": 0, "علوم": 0, "عربي": 0, "إنجليزي": 0, "مهارات رقمية": 0}
    subject_counts = {k: 0 for k in target_subjects}
    subject_all = {}
    for g in all_grades:
        subj = g.get("subject_name") or g.get("subject_id", "عام")
        if subj not in subject_all:
            subject_all[subj] = []
        subject_all[subj].append(g.get("percentage", 0))
        for key in target_subjects:
            if key in subj:
                target_subjects[key] += g.get("percentage", 0)
                subject_counts[key] += 1
                break

    radar_data = []
    for subj, total in target_subjects.items():
        count = subject_counts[subj]
        radar_data.append({"subject": subj, "score": round(total / count, 1) if count > 0 else 0})

    # Performance trend (line chart) — monthly averages
    monthly_data = {}
    for g in all_grades:
        date_str = g.get("date", "")
        if date_str:
            month_key = date_str[:7]  # YYYY-MM
            if month_key not in monthly_data:
                monthly_data[month_key] = []
            monthly_data[month_key].append(g.get("percentage", 0))

    line_chart_data = sorted([
        {"month": k, "average": round(sum(v) / len(v), 1)}
        for k, v in monthly_data.items()
    ], key=lambda x: x["month"])

    # Class comparison
    class_id = child.get("class_id")
    class_avg = 0
    if class_id:
        classmates = await gd_find(db.session, "students", {"class_id": class_id}, limit=100)
        classmate_ids = [c.get("id") for c in classmates if c.get("id") != child_id]
        if classmate_ids:
            class_grades = await gd_find(db.session, "grades", {
                "student_id": {"$in": classmate_ids}
            }, limit=5000)
            class_avg = round(sum(g.get("percentage", 0) for g in class_grades) / len(class_grades), 1) if class_grades else 0

    # Strengths and weaknesses
    strengths = []
    weaknesses = []
    for subj, scores in subject_all.items():
        avg = round(sum(scores) / len(scores), 1) if scores else 0
        if avg >= 80:
            strengths.append({"area": subj, "detail": f"متوسط {avg}%"})
        elif avg < 60:
            weaknesses.append({"area": subj, "detail": f"متوسط {avg}%"})

    # Participation strength
    total_participation = await gd_count(db.session, "participation_records", {"student_id": child_id})
    if total_participation > 20:
        strengths.append({"area": "مشاركة صفية", "detail": f"{total_participation} مشاركة مسجلة"})

    # Attendance
    total_att = await gd_count(db.session, "attendance", {"student_id": child_id})
    present_att = await gd_count(db.session, "attendance", {"student_id": child_id, "status": "present"})
    att_rate = round((present_att / total_att * 100), 1) if total_att > 0 else 100

    # Homework completion
    assignments = await gd_find(db.session, "student_assignments", {
        "$or": [{"class_id": class_id}, {"grade_id": child.get("grade_id")}]
    }, limit=200) if class_id else []
    submissions = await gd_find(db.session, "assignment_submissions", {
        "student_id": child_id
    }, limit=200)
    homework_rate = round(len(submissions) / max(1, len(assignments)) * 100, 1)

    if homework_rate < 60:
        weaknesses.append({"area": "واجبات غير مكتملة", "detail": f"نسبة إنجاز {homework_rate}%"})

    # Home follow-up indicator
    follow_up_score = (att_rate * 0.3) + (homework_rate * 0.3) + (min(total_participation, 50) / 50 * 100 * 0.2) + (overall_avg * 0.2)
    if follow_up_score >= 75:
        follow_up_status = "مستقر"
    elif follow_up_score >= 50:
        follow_up_status = "يحتاج متابعة"
    else:
        follow_up_status = "بحاجة دعم"

    # Performance level for gauge
    if overall_avg >= 90:
        level = "ممتاز"
    elif overall_avg >= 80:
        level = "جيد جداً"
    elif overall_avg >= 70:
        level = "جيد"
    elif overall_avg >= 60:
        level = "مقبول"
    else:
        level = "ضعيف"

    return {
        "student_name": child.get("full_name"),
        "summary": {
            "overall_average": overall_avg,
            "level": level,
            "class_average": class_avg,
            "total_assessments": len(all_grades),
        },
        "gauge_data": {"value": overall_avg, "level": level},
        "line_chart_data": line_chart_data,
        "radar_data": radar_data,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "follow_up": {
            "score": round(follow_up_score, 1),
            "status": follow_up_status,
            "breakdown": {
                "attendance_rate": att_rate,
                "homework_rate": homework_rate,
                "participation_score": min(total_participation, 50) / 50 * 100,
                "academic_average": overall_avg,
            }
        }
    }
```

- [ ] **Step 2: Add open-requests-count endpoint for communication center**

```python
@router.get("/open-requests-count")
async def get_open_requests_count(
    current_user: dict = Depends(require_roles([UserRole.PARENT]))
):
    """عدد الطلبات المفتوحة"""
    parent_id = current_user.get("id")
    open_messages = await gd_count(db.session, "messages", {
        "sender_id": parent_id,
        "status": {"$in": ["open", "pending", "sent"]}
    })
    open_excuses = await gd_count(db.session, "absence_excuses", {
        "parent_id": parent_id,
        "status": {"$in": ["pending", "submitted"]}
    })
    open_meetings = await gd_count(db.session, "meeting_requests", {
        "parent_id": parent_id,
        "status": {"$in": ["pending", "submitted"]}
    })
    total_open = open_messages + open_excuses + open_meetings
    return {
        "total_open": total_open,
        "limit": 3,
        "can_submit": total_open < 3,
        "breakdown": {
            "messages": open_messages,
            "excuses": open_excuses,
            "meetings": open_meetings,
        }
    }
```

---

### Task 5: Backend — Hakim Parent Chat Endpoint

**Files:**
- Modify: `backend/routes/ai_routes_mod.py`

- [ ] **Step 1: Add parent-chat endpoint**

Add a new endpoint that accepts parent context and sends it to the Hakim engine with a parent-specific system prompt. The endpoint should:
- Accept `child_id`, `message`, and `conversation_history`
- Verify parent access to the child
- Fetch child's academic data (grades, attendance, behavior, weaknesses)
- Build a parent-specific system prompt with the child's context
- Call the existing OpenAI chat completion
- Return the response

- [ ] **Step 2: Test the endpoint**

Verify Hakim responds with personalized advice when asked about a specific child.

---

### Task 6: Frontend — Custom Hook & Student Switcher

**Files:**
- Create: `frontend/src/hooks/useParentDashboard.js`
- Create: `frontend/src/components/parent/StudentSwitcher.jsx`

- [ ] **Step 1: Create the useParentDashboard hook**

Custom hook that manages all dashboard state:
- Selected child index and child list
- Today live data (fetched per child)
- Weekly story data (fetched per child)
- Loading states
- Auto-refresh interval for countdown timer
- Methods: `selectChild(index)`, `refreshLiveData()`, `refreshWeeklyStory()`

- [ ] **Step 2: Create StudentSwitcher component**

Horizontal scrollable list of child pills/chips. Each shows emoji + name. Active child has indigo highlight. Calls `selectChild()` on tap.

---

### Task 7: Frontend — Dashboard Main Page (Header, Progress, Current Class)

**Files:**
- Modify: `frontend/src/pages/ParentPortal/ParentPortalDashboard.jsx`
- Create: `frontend/src/components/parent/SchoolDayProgress.jsx`
- Create: `frontend/src/components/parent/CurrentClassCard.jsx`
- Create: `frontend/src/components/parent/UpcomingClasses.jsx`
- Create: `frontend/src/components/parent/PerformanceIndicator.jsx`

- [ ] **Step 1: Build SchoolDayProgress component**

Animated horizontal bar with period segments. Uses today's sessions data. Current time marker auto-advances via `setInterval(30s)`. Completed periods filled, current highlighted, remaining empty. Shows "X حصص متبقية" text.

- [ ] **Step 2: Build CurrentClassCard component**

Card showing current subject, teacher, time range. Live countdown timer (mm:ss) using `setInterval(1s)`. Shows "انتهى اليوم الدراسي" or "لم يبدأ بعد" when outside school hours.

- [ ] **Step 3: Build UpcomingClasses component**

Simple list of remaining periods. Each row: subject icon + name, start—end time. Sorted by period number.

- [ ] **Step 4: Build PerformanceIndicator component**

Card with performance level badge, trend arrow with percentage, and motivational phrase. Green for up, amber for stable, red for down.

- [ ] **Step 5: Rewrite ParentPortalDashboard.jsx**

Compose all components using the `useParentDashboard` hook:
1. StudentSwitcher (top)
2. Student header (name, school, grade)
3. Top icons (calendar → schedule page, bell → notifications sheet)
4. PerformanceIndicator
5. CurrentClassCard
6. UpcomingClasses
7. WeeklyStory

---

### Task 8: Frontend — Weekly Story Section

**Files:**
- Create: `frontend/src/components/parent/WeeklyStory.jsx`

- [ ] **Step 1: Build WeeklyStory component**

Full weekly analytics section with:
- Stat badges: participation count, positive behaviors count
- Skill tags (chips)
- Strong subjects (green badges) and weak subjects (amber badges)
- Remedial plans list (expandable cards)
- Recharts BarChart showing daily participation + behavior
- Weekly tip card with decorative styling

---

### Task 9: Frontend — Communication Center Page

**Files:**
- Create: `frontend/src/pages/ParentPortal/ParentCommunicationCenter.jsx`
- Modify: `frontend/src/pages/ParentPortal/index.js`
- Modify: `frontend/src/routes/appRoutes.js`

- [ ] **Step 1: Build ParentCommunicationCenter page**

Three-tab page:
1. **Send Message tab**: Form with type dropdown (ملاحظة/اقتراح/استفسار), recipient picker, text area. On success: "تم استلام رسالتكم، رضاكم محل اهتمامنا"
2. **Medical Excuse tab**: Form with description, file upload. Sends to admin.
3. **Inbox tab**: Message thread list with status badges.

Request limit enforcement: fetch `/parent-portal/open-requests-count` on mount. If `can_submit` is false, disable forms with message.

- [ ] **Step 2: Add route and navigation**

Add `/parent/communication` route to appRoutes.js. Add navigation link in PortalLayout or dashboard.

---

### Task 10: Frontend — Student Profile & Achievements

**Files:**
- Create: `frontend/src/pages/ParentPortal/StudentProfilePage.jsx`
- Create: `frontend/src/components/parent/ProfileEditor.jsx`
- Create: `frontend/src/components/parent/AchievementsArchive.jsx`
- Modify: `frontend/src/pages/ParentPortal/index.js`
- Modify: `frontend/src/routes/appRoutes.js`

- [ ] **Step 1: Build ProfileEditor component**

Inline edit form with:
- Emoji picker grid (common emoji options)
- Health condition icons: multi-select with icons (🫁 Asthma, 👓 Weak Vision, 🤧 Allergy, etc.)
- Behavioral aspects icons: multi-select with label "سلوك يحتاج تحسين" (🙈 Shyness, ⚡ Hyperactivity, 🎯 Concentration)
- Family situation dropdown (مع الوالدين / مع الأب فقط / مع الأم فقط / طرف آخر)
- Save/Cancel buttons

- [ ] **Step 2: Build AchievementsArchive component**

Achievement grid/list with source badges. Upload dialog with name, type selector, file upload field.

- [ ] **Step 3: Build StudentProfilePage**

Page composing: Profile Card (view mode) with edit icon toggle → ProfileEditor. "إنجازاتي" button → AchievementsArchive.

- [ ] **Step 4: Add route**

Add `/parent/child/:childId/profile` route.

---

### Task 11: Frontend — Student Analytics Page

**Files:**
- Create: `frontend/src/pages/ParentPortal/StudentAnalyticsPage.jsx`
- Create: `frontend/src/components/parent/AnalyticsCharts.jsx`
- Modify: `frontend/src/pages/ParentPortal/index.js`
- Modify: `frontend/src/routes/appRoutes.js`

- [ ] **Step 1: Build AnalyticsCharts component**

Three chart components using Recharts:
1. **GaugeChart**: Custom PieChart with half-circle showing performance level
2. **PerformanceLine**: LineChart showing monthly averages over time
3. **SubjectRadar**: RadarChart with 5 subjects

- [ ] **Step 2: Build StudentAnalyticsPage**

Page sections:
1. Performance summary (overall avg, class avg, level badge)
2. Gauge + Line chart side by side
3. Radar chart (full width)
4. Strength cards (green) and weakness cards (amber)
5. Home follow-up indicator with status badge and breakdown bars

- [ ] **Step 3: Add route**

Add `/parent/child/:childId/analytics` route.

---

### Task 12: Frontend — Hakim AI Chatbot Widget

**Files:**
- Create: `frontend/src/components/parent/HakimChatWidget.jsx`
- Modify: `frontend/src/pages/ParentPortal/ParentPortalDashboard.jsx`

- [ ] **Step 1: Build HakimChatWidget component**

Floating button (bottom-left for RTL) with حكيم label. Opens Sheet/Drawer with:
- Chat message bubbles (user right-aligned, Hakim left-aligned)
- Text input + send button
- Loading indicator while waiting for response
- Session-based conversation history (React state)
- Sends selected child ID with each message

- [ ] **Step 2: Integrate into dashboard**

Add HakimChatWidget to the ParentPortalDashboard, passing the selected child ID.

---

### Task 13: Translation Keys & Route Registration

**Files:**
- Modify: `frontend/src/locales/ar.json`
- Modify: `frontend/src/locales/en.json`
- Modify: `frontend/src/routes/appRoutes.js`
- Modify: `frontend/src/pages/ParentPortal/index.js`

- [ ] **Step 1: Add translation keys**

Add all new UI text keys to both locale files:
- Dashboard sections (where is student, upcoming classes, weekly story, etc.)
- Communication center labels
- Profile editor labels
- Analytics labels
- Chatbot labels

- [ ] **Step 2: Register all new routes**

Ensure all new pages are properly imported and routed in appRoutes.js with parent role guard.

- [ ] **Step 3: Update ParentPortal index exports**

Export all new page components from index.js.

---

### Task 14: Final Integration & Testing

- [ ] **Step 1: Verify all endpoints respond correctly**
- [ ] **Step 2: Verify all frontend pages render without errors**
- [ ] **Step 3: Test student switching updates all sections**
- [ ] **Step 4: Test countdown timer accuracy**
- [ ] **Step 5: Test communication center 3-request limit**
- [ ] **Step 6: Test profile save/load cycle**
- [ ] **Step 7: Test analytics charts render with data**
- [ ] **Step 8: Test Hakim chat responds contextually**
- [ ] **Step 9: Verify RTL layout consistency across all new pages**
- [ ] **Step 10: Check all translation keys resolve in both AR and EN**

# خطة تنفيذ إصلاح تذكرة KAN-59: معالجة النصاب الأقصى للمعلم في جدول حصص الانتظار (Standby Max Quota Bug)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** تضمين حقل `max_quota` مع `weekly_quota` في حمولة الـ API لجدول حصص الانتظار مع اعتماد نصاب الرتبة والنظام عند غياب النصاب المباشر، وإصلاح النصوص المشوهة (مثل `"-/8"`) في واجهات الفرونت إند ("حسب اليوم" ومصفوفة المعلمين) مع توفير تراجع آمن (Safe Fallback).

**Architecture:** 
1. **الباك إند (Backend):** بناء دالة موحدة `resolve_teacher_weekly_quota` لمعالجة نصاب المعلم وفق هرمية واضحة (`weekly_periods` صريح -> رتبة المعلم `rank` -> القيمة الافتراضية المعتمدة لوزارة التعليم 24). حقن `max_quota` و `weekly_quota` في مخرجات مسار `/standby/roster` وخدمات `standby_roster_service` و `substitution_service`.
2. **الفرونت إند (Frontend):** تصحيح صياغة النصوص في مكونات `StandbyRosterPage.jsx` (شاشة اختيار المعلم في العرض اليومي والمصفوفة) مع عزل اتجاه الأرقام باستخدام `<span dir="ltr">` لمنع انقلاب الشرطة المائلة في سياق RTL، وتطبيق التراجع الآمن (عرض عدد الحصص فقط مثل `8 حصص` دون شرطات في حال عدم تعيين النصاب).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Pytest, React (Vite/CRA), Tailwind CSS.

---

## تفاصيل المشكلة وجذورها (Root Cause Analysis)

### 1. في الباك إند:
* مسار `GET /standby/roster` في `backend/src/modules/scheduling/controllers/standby_routes.py` يعتمد فقط على `t.get("weekly_periods") or 0`.
* المعلمون المستوردون من نظام "نور" أو الذين لم يُسجل لهم نصاب يدوي لا يملكون حقل `weekly_periods` في قاعدة البيانات، مما يجعل القيمة `0`.
* الحقل المطلوب صراحة في تذكرة Jira هو `max_quota` ولم يكن متوفراً في الـ JSON Payload.
* في خوارزمية التوزيع الآلي `backend/services/standby_roster_service.py`، كان المعلم الذي يملك نصاباً `0` يُستبعد كلياً من جدول الانتظار.

### 2. في الفرونت إند:
* في نافذة اختيار المعلم (Modal Picker) السطر 536:
  `{t.assigned_periods}/{t.weekly_quota || '—'} حصص`
* في مصفوفة المعلمين (Teacher Matrix) السطر 640-643:
  `{teacher.assigned_periods} / {teacher.weekly_quota || '—'}`
* عند غياب النصاب (`0` أو `null`)، يتم استبداله بـ `'—'`.
* في بيئة اللغة العربية ذات الاتجاه من اليمين لليسار (`dir="rtl"`):
  تقوم خوارزمية BiDi بقلب النص المكتوب بصيغة `8/—` ليظهر للمستخدم كـ `-/8`، وعند دمجه مع النقاط والكلمات ينتج: `"رياضيات . -/8 - حصص"` أو `"-/6 -"`.

---

## خطة المهام المقسمة (Actionable Tasks)

### Task 1: بناء وحدة استنتاج النصاب وإثراء مسارات الباك إند

**الملفات المستهدفة:**
* تعديل: `backend/services/standby_roster_service.py`
* تعديل: `backend/src/modules/scheduling/controllers/standby_routes.py`
* تعديل: `backend/services/substitution_service.py`
* إنشاء: `backend/tests/test_standby_roster_quota.py`

- [ ] **الخطوة 1: كتابة اختبار الوحدات الآلي الفاشل (Failing Test)**
إنشاء ملف الاختبار `backend/tests/test_standby_roster_quota.py` للتحقق من:
1. دالة `resolve_teacher_weekly_quota` تعيد النصاب المباشر إذا وُجد، أو نصاب الرتبة (24 لخبير، 22 لمتقدم، 20 لممارس، 18 لمساعد)، أو 24 كافتراضي عام.
2. التحقق من أن بيانات المعلم في `GET /standby/roster` تحوي حقلي `max_quota` و `weekly_quota` بقيم رقمية صحيحة موجبة وليست صفراً عند غياب `weekly_periods`.

- [ ] **الخطوة 2: تشغيل الاختبار للتحقق من الفشل**
أمر التشغيل:
```bash
/opt/anaconda3/envs/nassaq/bin/pytest tests/test_standby_roster_quota.py -v
```

- [ ] **الخطوة 3: تطبيق التعديل في `standby_roster_service.py`**
إضافة خريطة الرتب ودالة `resolve_teacher_weekly_quota`، وتحديث دالة `compute_standby_roster` لحساب سعة المعلم بناءً على النصاب المستنتج بدلاً من استبعاد المعلم.

- [ ] **الخطوة 4: تطبيق التعديل في `standby_routes.py` و `substitution_service.py`**
تحديث حمولة المعلمين لتتضمن:
```python
"weekly_quota": quota,
"max_quota": quota,
```

- [ ] **الخطوة 5: إعادة تشغيل الاختبارات للتأكد من نجاحها**
```bash
/opt/anaconda3/envs/nassaq/bin/pytest tests/test_standby_roster_quota.py tests/test_standby_roster_distribution.py -v
```

---

### Task 2: إصلاح صياغة النص والتراجع الآمن في الفرونت إند (Frontend Views)

**الملفات المستهدفة:**
* تعديل: `frontend/src/features/schedule/pages/StandbyRosterPage.jsx`
* تعديل: `frontend/src/features/schedule/pages/SchedulePageNew.jsx`
* تعديل: `frontend/src/features/schedule/components/schedule/CandidatesSidePanel.jsx`

- [ ] **الخطوة 1: إنشاء دالة مساعدة لصياغة النصاب والعبء التدريسي في الفرونت إند**
دعم قراءة `max_quota` مع `weekly_quota`، وضمان التنسيق الصحيح:
```jsx
// إذا توفر النصاب: "8 / 20 حصص" مع عزل LTR لمنع قلب الشرطة في العربية
// إذا لم يتوفر النصاب: "8 حصص" كتراجع آمن بدون شرطات مائلة أو مجهولة
```

- [ ] **الخطوة 2: تطبيق التنسيق في نافذة الإسناد باليوم ("By Day" Modal Picker)**
تعديل السطر 536 في `StandbyRosterPage.jsx` لاستخدام التنسيق المحمي والمطابق لـ Jira:
`[التخصص] • [الحصص المسندة] / [النصاب الأقصى] حصص`
(مثال: `رياضيات • 8 / 20 حصص`).

- [ ] **الخطوة 3: تطبيق التنسيق في مصفوفة المعلمين ("Teacher Matrix" View)**
تعديل الأسطر 636-644 في `StandbyRosterPage.jsx` لعرض النسبة بعزل LTR وتفادي تشوه النص مثل `"-/6 -"`.

- [ ] **الخطوة 4: مراجعة المكونات المرتبطة في `SchedulePageNew.jsx` و `CandidatesSidePanel.jsx`**
تطبيق عزل الاتجاه نفسه على الأرقام لمنع أي تشوه مماثل في شاشات الجدولة والبدلاء.

---

### Task 3: التحقق والتأكد من مطابقة شروط قبول Jira (Verification & Acceptance)

- [ ] **الخطوة 1: اختبار واجهات الـ API عبر مسارات الفحص**
التحقق من أن استدعاء `/standby/roster?school_id=...&shape=day_centric` يعيد المعلمين بحقل `max_quota` مع أرقام حقيقية.

- [ ] **الخطوة 2: اختبار الواجهة بصرياً عبر المتصفح (Browser Verification)**
فتح صفحة "جدول حصص الانتظار" بحساب مدير المدرسة (`mudeer@example.com`):
1. فحص مصفوفة المعلمين والتأكد من ظهور النص الصحيح تحت اسم المعلم (مثل `8 / 20 حصص`).
2. الانتقال إلى عرض "حسب اليوم"، والضغط على خانة فارغة لفتح نافذة "إضافة معلم لخانة الانتظار"، والتحقق من ظهور: `رياضيات • 8 / 20 حصص`.
3. التأكد من اختفاء النصوص المشوهة مثل `"-/8 - حصص"` أو `"-/6 -"`.

- [ ] **الخطوة 3: تحديث تذكرة Jira KAN-59**
توثيق حل العيب البرمجي وإرفاق الملاحظات الفنية على التذكرة.

---

## خطة التحقق والاختبار (Verification Plan)

### Automated Tests
1. تشغيل اختبارات الباك إند:
   ```bash
   /opt/anaconda3/envs/nassaq/bin/pytest tests/test_standby_roster_quota.py tests/test_standby_roster_distribution.py -v
   ```
2. فحص سلامة بناء الفرونت إند ومطابقة الأنواع:
   ```bash
   npm run build --prefix frontend -- --dry-run
   ```

### Manual Verification
1. تسجيل الدخول بحساب مدير المدرسة التجريبي `mudeer@example.com`.
2. الدخول إلى: الجدول المدرسي -> جدول حصص الانتظار.
3. التأكد من شاشة مصفوفة المعلمين: عمود المعلمين يعرض حصص المعلم ونصابه بشكل سليم.
4. التأكد من شاشة العرض باليوم: فتح نافذة إضافة المعلم والتأكد من ظهور `التخصص • الحصص / النصاب حصص` بشكل متناسق وسليم لغوياً وبرمجياً.

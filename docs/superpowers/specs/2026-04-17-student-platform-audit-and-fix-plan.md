# خطة مراجعة وإصلاح منصة الطالب — NASSAQ
**التاريخ:** 17 أبريل 2026
**النطاق:** كل ما يخص الطالب — البوابة (StudentPortal) + صفحات الإدارة + الـ APIs الخلفية
**المنهجية:** عصف ذهني + فحص متوازي للكود + تصنيف بالخطورة + إصلاح متدرّج آمن

---

## 1) ملخص تنفيذي

تم فحص شامل لـ 8 ملفات backend (≈ 3,300 سطر) و 11 ملف frontend خاصة بالطالب. النتائج:

| الخطورة | عدد المشاكل |
|---------|-------------|
| **Critical** (ثغرات أمنية / تسريب بيانات بين المدارس) | 4 |
| **High** (وظائف مكسورة / تعطّل صفحات / N+1) | 9 |
| **Medium** (تعارض schema / ترجمات ناقصة / تجربة سيئة) | 13 |
| **Low** (كود ميت / تنظيف / accessibility) | 11 |
| **المجموع** | **37** |

---

## 2) تصنيف المشاكل حسب الفئة

### 🔴 الفئة A — أمنية (Critical)
ثغرات تسمح بالوصول لبيانات طلاب من مدرسة أخرى أو رؤية واجبات/رسائل لا تخص الطالب.

| # | الملف:السطر | المشكلة | الإصلاح |
|---|-------------|----------|---------|
| A1 | `backend/routes/student_portal_routes.py:1232-1253` | **IDOR** في `get_assignment_details`: أي طالب يمرر `assignment_id` يحصل على أي واجب حتى لو لم يكن من فصله/مدرسته | تحقق أن الواجب ينتمي إلى `class_id`/`grade_id`/`school_id` للطالب قبل الإرجاع |
| A2 | `backend/routes/student_portal_routes.py:143, 207, 326` | **غياب tenant_id** في استعلامات `/grades`, `/attendance`, `/messages` — احتمال تسرّب بين المدارس | إضافة `school_id = current_user["tenant_id"]` لكل الاستعلامات |
| A3 | `backend/routes/student_management_routes.py:271, 296, 314, 343, 359, 375` | غياب `require_roles` على routes إدارة الطلاب — أي مستخدم مصادق (طالب/ولي أمر) يقدر يستدعيها | تطبيق `require_roles([SCHOOL_ADMIN, SCHOOL_SUB_ADMIN, PLATFORM_ADMIN])` |
| A4 | `backend/routes/student_portal_routes.py:318-349` | عدم تطابق اسم الحقل: route يستعلم `receiver_id` بينما الـ model يستخدم `recipient_id` | توحيد الاسم على `recipient_id` في الاستعلام والـ schema |

### 🟠 الفئة B — وظائف مكسورة (High)
صفحات أو نداءات API ترجع 404 أو بيانات خاطئة.

| # | الملف:السطر | المشكلة | الإصلاح |
|---|-------------|----------|---------|
| B1 | `frontend/src/pages/StudentDashboard.jsx:44` | يستدعي `/student/dashboard/{id}` غير الموجود (الصحيح `/student-portal/dashboard`) | تصحيح المسار |
| B2 | `frontend/src/pages/StudentPortal/StudentPortalDashboard.jsx:38-39` | يستدعي `/student-portal/points` و `/student-portal/activities` غير المُنفّذتين في backend | إما إنشاء الـ endpoints أو الاكتفاء ببيانات `/dashboard` |
| B3 | `frontend/src/pages/StudentPortal/StudentHomeworkPage.jsx:84-102` | فحص الحالات يبحث عن `completed`/`overdue` بينما backend يرجع `graded`/`submitted`/`late`/`pending` — كل الحالات تظهر خاطئة | توحيد قائمة الحالات بين الطرفين |
| B4 | `backend/routes/student_portal_routes.py:1149-1155` | **N+1 queries** داخل حلقة الواجبات (subjects + teachers لكل واجب) | جمع IDs ثم استعلام `$in` واحد لكل نوع |
| B5 | `backend/routes/student_portal_routes.py:1276` | عدم تطابق: الكود يقرأ `subject_name` بينما جدول grades قد يخزن `subject` فقط | توحيد الحقل والتأكد من تعبئته عند الإدخال |
| B6 | `backend/routes/student_portal_routes.py:1104-1105` | استعلام assignments يستخدم `class_ids` و `class_id` معاً — أحدهما لن يعمل | اختيار حقل واحد قياسي |
| B7 | `backend/routes/student_portal_routes.py:1134` | عند فشل parse للـ `due_date` يستخدم `now+7d` بصمت — يخفي فساد البيانات ويضلل الطالب | تسجيل خطأ وإرجاع null أو علامة "غير محدد" |
| B8 | `frontend/src/pages/StudentPortal/StudentSchedulePage.jsx:37-48` | استخدام أسماء أيام عربية كمفاتيح بينما backend يستخدم `sunday`...`saturday` | استخدام keys إنجليزية في المنطق وترجمة العرض فقط |
| B9 | `backend/engines/student_management_engine.py:137` | توليد `student_number` بـ `count+1` يسبب تعارض عند الإنشاء المتزامن | استخدام sequence من DB أو قفل صفّي |

### 🟡 الفئة C — Schema / تحقق / تجربة (Medium)

| # | الملف:السطر | المشكلة | الإصلاح |
|---|-------------|----------|---------|
| C1 | `backend/routes/student_portal_routes.py:92, 102, 187, 470, 473, 1270, 1314` | **القسمة على صفر** في حساب `attendance_rate`/`avg_score`/`overall_avg` | حماية: `x/n if n else 0` في كل النقاط |
| C2 | `backend/routes/student_portal_routes.py:351-357` | `send_student_message` بدون Pydantic validation — يقبل محتوى فارغ أو ضخم | إنشاء `MessageRequest(BaseModel)` مع `min_length`/`max_length` |
| C3 | `backend/routes/student_portal_routes.py:48, 279, 415` | ربط بحالة `"published"` فقط للجداول — مدرسة بحالة "active" لن ترى شيئاً | استخدام Enum أو قبول قائمة حالات حية |
| C4 | `backend/routes/student_portal_routes.py:87-90` | 4 استعلامات count منفصلة لإحصائيات الحضور | استعلام واحد + تجميع في Python |
| C5 | `backend/shared_models.py:398` vs `pg_models.py:173` | `StudentResponse` يحوي `parent_name/phone/email` غير الموجودة في ORM | تحقيق التطابق أو ضمان التعبئة عبر join |
| C6 | `backend/routes/student_management_routes.py:32` (10) vs `student_creation_routes.py:44` (Optional) | عدم اتساق التحقق من `national_id` | type/validator مشترك في `shared_models.py` |
| C7 | `backend/routes/student_creation_routes.py:298, 326, 329` | إدراجات متعددة بدون transaction — احتمال يوزر بدون student | لفّ الإنشاء في `begin()` transaction |
| C8 | `frontend/src/pages/StudentsPage.jsx:143` | يرسل `full_name` بينما `student_management_routes` يطلب `full_name_ar` | توحيد الاسم عبر كل endpoints |
| C9 | `frontend/src/pages/StudentPortal/StudentProgressPage.jsx:44`, `StudentAchievementsPage.jsx:83` | catch يطبع console.log فقط — المستخدم لا يرى خطأ | `setError` + استخدام `nassaqError` |
| C10 | `frontend/src/pages/StudentPortal/StudentPortalDashboard.jsx:114, 230, 364, 377` + `StudentHomeworkPage.jsx:98-99` + `StudentSchedulePage.jsx:90,124,126,161` + `StudentProgressPage.jsx:95-127` | نصوص مُجَمَّدة (isRTL ? 'عربي' : 'EN') خارج نظام i18n | تحويل لـ `t('key')` وإضافة المفاتيح في `ar.json/en.json` |
| C11 | `frontend/src/pages/student/StudentAssignments.jsx:277-278, 463` + `student/StudentDashboard.jsx:127` | نصوص عربية حرفية | تحويل للترجمات |
| C12 | `frontend/src/pages/StudentsPage.jsx:300` | Modal بطول 60vh يصعب التنقل فيه على الجوال | استخدام wizard متعدد الخطوات (موجود `AddStudentWizard.jsx`) |
| C13 | `backend/routes/academics_student_routes.py:401` | `transfer_class` يأخذ JSON بدون Pydantic | إضافة `ClassTransferRequest` model |

### 🔵 الفئة D — كود ميت / تنظيف (Low)

| # | الملف:السطر | المشكلة | الإصلاح |
|---|-------------|----------|---------|
| D1 | `frontend/src/pages/StudentDashboard.jsx`, `student/StudentDashboard.jsx`, `StudentPortal/StudentPortalDashboard.jsx` | **3 لوحات تحكم طالب مكررة** — كابوس صيانة | الإبقاء على `StudentPortalDashboard.jsx` فقط وحذف الباقي + تحديث `appRoutes.js` |
| D2 | `frontend/src/pages/student/StudentGrades.jsx` vs `StudentPortal/StudentGradesPage.jsx` | تكرار صفحة الدرجات | حذف القديمة |
| D3 | `frontend/src/pages/StudentDashboard.jsx:13-14` | imports غير مستعملة (Home/Settings/Chevrons) | حذف |
| D4 | `frontend/src/pages/student/StudentAssignments.jsx:45` | `nassaqError, nassaqWarning` غير مستعملين | حذف |
| D5 | `backend/routes/student_portal_routes.py:33-35, 263-265, 408-410, 464-466, 1092-1094` | تكرار pattern البحث عن student بـ id ثم user_id | helper مشترك أو FastAPI dependency |
| D6 | `backend/routes/student_portal_routes.py:917-1071` | كود إنشاء حسابات اختبار داخل ملف routes | نقل لـ `seeds/test_utils` |
| D7 | `backend/routes/student_portal_routes.py:117, 304` | الترتيب في Python بعد الجلب | استخدام `order_by` في الاستعلام |
| D8 | `backend/routes/student_portal_routes.py:375` | hardcoded `"student"` | استخدام `UserRole.STUDENT.value` |
| D9 | `frontend/src/pages/StudentProfilePage.jsx:49` | `BackArrow = isRTL ? ChevronRight : ChevronRight` (نفس الأيقونة) | `isRTL ? ChevronRight : ChevronLeft` |
| D10 | `frontend/src/pages/StudentDashboard.jsx:328-349` | bottom nav بدون `aria-label` ولا active state | استبدال بـ `NavLink` + aria |
| D11 | `frontend/src/pages/StudentProfilePage.jsx:180` | "معلق"/"Suspended" مُجَمَّدة | `t('suspended')` |

---

## 3) خطة الإصلاح المرحلية (5 مراحل آمنة)

كل مرحلة:
- تنفيذ → اختبار → restart workflow → تأكيد قبل الانتقال للتالية
- لا تكسر سلوك موجود (Stability Rules من `replit.md`)

### المرحلة 1 — أمن البيانات (يوم 1) 🔴
**الهدف:** إغلاق كل ثغرات تسرّب البيانات قبل أي شيء آخر.
- A1: حماية `get_assignment_details` بفحص class/school
- A2: إضافة `school_id` لكل استعلامات `/grades`, `/attendance`, `/messages`
- A3: تطبيق `require_roles` على 6 routes إدارية
- A4: توحيد `recipient_id`
- C7: لفّ إنشاء الطالب في transaction

**التحقق:** اختبار تجريبي يدوي بحساب طالب من مدرسة A يحاول قراءة بيانات مدرسة B → يجب 403/404.

### المرحلة 2 — وظائف مكسورة (يوم 1-2) 🟠
- B1: تصحيح `/student/dashboard/{id}` → `/student-portal/dashboard`
- B2: قرار: حذف نداءات `/points` و `/activities` من frontend (لأن البيانات موجودة في `/dashboard`) — أبسط من إنشاء endpoints جديدة
- B3: توحيد قائمة حالات الواجب بين frontend و backend
- B5, B6: توحيد أسماء حقول `subject_name` و `class_id`
- B7: استبدال السقوط الصامت بإرجاع null + log
- B8: استخدام keys إنجليزية للأيام
- B9: فحص ووضع UNIQUE قوي على `(school_id, student_number)` + retry-on-conflict

**التحقق:** فتح كل صفحة في البوابة والتأكد من عدم ظهور 404 وبيانات صحيحة.

### المرحلة 3 — Schema & Validation (يوم 2-3) 🟡
- C1: حماية القسمة على صفر (7 مواقع)
- C2, C13: Pydantic models لـ message و class transfer
- C3: قبول قائمة حالات للجدول الحي
- C4: تجميع استعلامات الحضور
- C5: محاذاة `StudentResponse` مع DB
- C6: validator مشترك لـ `national_id`
- C8: توحيد `full_name` ضد `full_name_ar`

### المرحلة 4 — تجربة المستخدم & i18n (يوم 3-4) 🟡
- C9: error states في ProgressPage و AchievementsPage
- C10, C11: تحويل ~20 نص مُجَمَّد لـ `t()` + إضافة المفاتيح في ar/en JSON
- C12: استبدال modal الطويل بـ wizard
- D9, D10, D11: إصلاحات RTL و a11y الصغيرة

### المرحلة 5 — تنظيف & تحسينات (يوم 4-5) 🔵
- D1, D2: **حذف 3 لوحات تحكم وصفحة درجات مكررة** (مع توحيد routing)
- D3, D4: حذف imports غير مستعملة
- D5: helper `get_student_by_user(user)` مشترك
- D6: نقل كود seed لـ `seeds/`
- D7: `order_by` في الاستعلامات
- D8: استخدام `UserRole.STUDENT.value`
- B4: إصلاح N+1 في الواجبات

---

## 4) معايير القبول (Acceptance Criteria)

### بعد كل مرحلة:
- ✅ Backend logs خالية من tracebacks جديدة
- ✅ Frontend يبني بدون errors (warnings مقبولة فقط للبنود غير المتعلقة)
- ✅ كل صفحة طالب تفتح وتعرض بيانات
- ✅ لا regression في صفحات معلم/إدارة/ولي أمر

### في النهاية:
- ✅ صفر مشكلة Critical
- ✅ صفر صفحة طالب تعرض 404 من API
- ✅ صفر نص حرفي عربي/إنجليزي خارج نظام i18n في صفحات الطالب
- ✅ صفحة طالب واحدة فقط في `/student/dashboard` (مش 3)
- ✅ كل routes الإدارية تتطلب الدور الصحيح

---

## 5) قواعد الإصلاح (مأخوذة من replit.md)

- ✅ التحقق من أسماء الأدوار من DB (لا افتراضات): `school_admin, school_sub_admin, teacher, student, parent, platform_admin, platform_operations_manager`
- ✅ مطابقة Schema بين backend ↔ frontend ↔ DB قبل أي تعديل
- ✅ كل تعديل: `Restart Workflow` + اختبار يدوي + regression check للوظائف المرتبطة
- ✅ استخدام `nassaqError/Warning/Confirm` بدل `alert()` و `toast.error()`
- ✅ كل النصوص عبر `t('key')` من `ar.json/en.json` — لا `isRTL ? 'عربي' : 'EN'` جديد
- ✅ التواريخ الهجرية عبر `frontend/src/utils/hijriDate.js` و backend `hijri_converter`

---

## 6) خريطة الملفات المتأثرة

**Backend (5 ملفات):**
- `backend/routes/student_portal_routes.py` (الأكبر — 14 إصلاح)
- `backend/routes/student_management_routes.py` (5 إصلاحات)
- `backend/routes/student_creation_routes.py` (2 إصلاحات)
- `backend/routes/academics_student_routes.py` (2 إصلاحات)
- `backend/engines/student_management_engine.py` (1 إصلاح)
- `backend/shared_models.py` (1 إصلاح)

**Frontend (11 ملف):**
- `frontend/src/pages/StudentPortal/*` (7 ملفات — معظم إصلاحات i18n)
- `frontend/src/pages/StudentDashboard.jsx` (للحذف)
- `frontend/src/pages/student/*` (للحذف بعد توحيد)
- `frontend/src/pages/StudentsPage.jsx`, `StudentProfilePage.jsx` (إصلاحات صغيرة)
- `frontend/src/locales/ar.json`, `en.json` (إضافة ≈ 25 مفتاح)
- `frontend/src/appRoutes.js` (تحديث routes بعد حذف المكررات)

---

## 7) ما لن يُعمل في هذه الخطة (YAGNI)

- ❌ إعادة كتابة منصة الطالب من الصفر
- ❌ إضافة features جديدة (تركيز كامل على الإصلاح)
- ❌ تعديل صفحات معلم/ولي أمر/إدارة (إلا عند ضرورة لتجنب regression)
- ❌ تغيير DB schema بشكل مدمّر — كل التغييرات backwards-compatible
- ❌ تغيير نظام المصادقة أو WebSocket

---

## 8) الخطوة التالية المقترحة

1. **مراجعتك للخطة** — هل النطاق والأولويات والمراحل مناسبة؟
2. عند الموافقة: أبدأ بالمرحلة 1 (الأمن) فوراً — هذه أعلى أولوية
3. بعد كل مرحلة: تقرير مختصر + اختبار + موافقتك للمرحلة التالية

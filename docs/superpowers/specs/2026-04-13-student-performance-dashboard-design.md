# لوحة رؤى تحليل أداء الطلاب — وثيقة التصميم الكاملة
# Student Performance Analytics Dashboard — Full Design Spec

**التاريخ:** 2026-04-13
**الحالة:** معتمدة — في انتظار التنفيذ
**المرجع:** PRD الإدارة + جلسة التصميم التفاعلية

---

## 1. نظرة عامة

### الهدف
إضافة تبويب جديد "تحليل أداء الطلاب" داخل صفحة رؤى الذكاء الاصطناعي (`AIInsightsPage`) لعرض حالة الطلاب اللحظية وتقديم رؤى تحليلية للإدارة، مع الكشف المبكر عن الطلاب المتعثرين وتقديم الدعم الاستباقي.

### القرارات المعتمدة

| القرار | الاختيار |
|--------|---------|
| الموقع | تبويب جديد داخل `AIInsightsPage` (ليست صفحة مستقلة) |
| الأدوار المستهدفة | `school_admin` + `school_sub_admin` فقط |
| تنظيم الأقسام | عرض تسلسلي (Scrollable) — كل الأقسام مرئية بالتمرير |
| أزرار الإجراءات | عاملة فعلياً — ترسل رسائل حقيقية وتنشئ خطط فعلية |
| تحديث البيانات | عند فتح الصفحة + زر تحديث يدوي |
| مصدر التوصيات | ذكاء اصطناعي عبر حكيم (OpenAI) باللغة العربية |
| التصميم | يتبع ألوان وهوية نسق بالكامل |

---

## 2. هوية التصميم (Brand Compliance)

### الألوان الأساسية
| الاسم | الكود | الاستخدام |
|-------|-------|----------|
| Brand Navy | `#1C3D74` | العناوين، الأزرار الأساسية، النصوص المهمة |
| Brand Turquoise | `#46C1BE` | هوية حكيم AI، أزرار CTA، الخطوط التفاعلية |
| Brand Purple | `#615090` | اللون الثالثي، حالة "متفوق" |
| Brand Black | `#312E2F` | نصوص الجسم |
| Brand Gray | `#EAECED` | الفواصل، الحدود الخفيفة |

### ألوان الحالات
| الحالة | اللون | الكود |
|--------|-------|-------|
| مستقر | أخضر | `#22c55e` |
| يحتاج متابعة | أصفر | `#eab308` |
| خطر تعليمي | أحمر | `#ef4444` |
| متفوق | بنفسجي (Brand Purple) | `#615090` |

### الخطوط
- **العناوين**: Cairo (font-cairo)
- **النصوص**: Tajawal (font-tajawal)
- **الأرقام/الأكواد**: IBM Plex Mono (font-mono)

### عناصر التصميم
- **Border Radius**: `12px` (var(--radius) = 0.75rem)
- **Box Shadow**: `0 4px 20px -4px rgba(15, 44, 89, 0.1)` (shadow-card)
- **الاتجاه**: RTL بالكامل
- **خلفية الصفحة**: `from-slate-50 via-white to-blue-50/20`

---

## 3. هيكل الواجهة — الأقسام الخمسة

### التخطيط العام
```
┌─────────────────────────────────────────────────────┐
│  [الرؤى الذكية]  [تحليل أداء الطلاب] ← تبويب نشط  │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────┐ ┌──────────┐ ┌──────────┐ ┌──────┐       │
│  │مستقر │ │يحتاج     │ │خطر       │ │متفوق │       │
│  │ 62%  │ │متابعة 23%│ │تعليمي 10%│ │ 5%   │       │
│  └──────┘ └──────────┘ └──────────┘ └──────┘       │
│                                                     │
│  ┌────────────────────┐ ┌──────────────────┐        │
│  │  خريطة المخاطر     │ │ طلاب يحتاجون    │        │
│  │  (Scatter Plot)     │ │ تدخلاً          │        │
│  │                     │ │ [إجراء] [إجراء]  │        │
│  └────────────────────┘ └──────────────────┘        │
│                                                     │
│  ┌────────────────┐ ┌──────────────────────┐        │
│  │ أسباب التعثر   │ │ اقتراحات نسق         │        │
│  │ (Pie Chart)    │ │ (توصيات حكيم AI)     │        │
│  └────────────────┘ └──────────────────────┘        │
└─────────────────────────────────────────────────────┘
```

---

### 3.1 الملخص التنفيذي (Executive Summary)

**الوصف**: صف من 4 بطاقات KPI في أعلى الصفحة

**محتوى كل بطاقة:**
- النسبة المئوية (خط كبير بلون الحالة)
- عدد الطلاب
- أيقونة تعبيرية (✓، !، ↓، ★)
- لون خط جانبي أيمن (border-right) يمثل الحالة

**التصنيفات:**

| التصنيف | المنطق (من Hakim Risk Score) | اللون |
|---------|------------------------------|-------|
| مستقر | Risk Score 75-100 (Low Risk) | أخضر `#22c55e` |
| يحتاج متابعة | Risk Score 50-75 (Medium Risk) | أصفر `#eab308` |
| خطر تعليمي | Risk Score 0-50 (High + Critical) | أحمر `#ef4444` |
| متفوق | Risk Score 90+ مع أعلى درجات أكاديمية | بنفسجي `#615090` |

**مصدر البيانات:**
- يستدعي endpoint جديد يجمع Risk Scores لكل الطلاب في المدرسة (tenant)
- يصنفهم حسب الفئات الأربع
- يحسب النسب والأعداد

---

### 3.2 خريطة المخاطر (Student Risk Map)

**الوصف**: تمثيل بصري تفاعلي — كل نقطة تمثل طالباً

**نوع الرسم**: Scatter Plot باستخدام Recharts `<ScatterChart>`

**المحاور:**
- المحور X: مؤشر الأداء الأكاديمي (0-100)
- المحور Y: مؤشر الحضور والمشاركة (0-100)

**الترميز اللوني:**
- 🟢 أخضر: مستقر (score >= 75)
- 🟡 أصفر: يحتاج متابعة (score 50-75)
- 🔴 أحمر: خطر (score < 50)
- 🟣 بنفسجي: متفوق (score >= 90 + top academic)

**التفاعل عند النقر على نقطة:**
- Tooltip يظهر: اسم الطالب، الفصل، مؤشر الأداء الكلي
- أسباب التصنيف (مثل: "غياب متكرر"، "تراجع درجات")
- اقتراحات تدخل سريعة
- رابط لملف الطالب التفصيلي

**مصدر البيانات:**
- نفس endpoint الملخص التنفيذي (يُرجع مصفوفة الطلاب مع إحداثياتهم)

---

### 3.3 قائمة التدخل (Intervention List)

**الوصف**: قائمة إجرائية للطلاب الأكثر عرضة للتعثر (فئة خطر + متابعة)

**البيانات المعروضة لكل طالب:**
- اسم الطالب
- الفصل
- نوع المشكلة (غياب متكرر، تراجع اختبارات، ضعف مشاركة، واجبات)
- شارة الحالة (خطر / متابعة) بلونها المميز

**زر "اتخاذ إجراء":**
عند الضغط يفتح قائمة منسدلة (Dropdown) تحتوي على 3 خيارات:

#### 3.3.1 إرسال رسالة لولي الأمر
- **الربط**: نظام الإشعارات الحالي (`NotificationEngine`)
- **التنفيذ**: يستخدم `trigger_attendance_alert` أو `create_notification` مع:
  - `recipient_id` = `parent_id` من جدول الطالب
  - `category` = نوع المشكلة المحددة
  - `priority` = "high" للخطر، "medium" للمتابعة
- **الواجهة**: Modal بسيط لتأكيد الإرسال مع إمكانية تعديل نص الرسالة
- **القالب الافتراضي**: "ولي أمر {student_name} الكريم، نود إبلاغكم بأن ابنكم/ابنتكم بحاجة لمتابعة بخصوص {issue_type}. نرجو التواصل مع المدرسة."

#### 3.3.2 إعداد خطة علاجية
- **الربط**: نظام السلوك الحالي (`BehaviourRecord`) + سجل جديد
- **التنفيذ**: إنشاء سجل في collection جديد `remedial_plans` يحتوي على:
  - `student_id`, `created_by`, `issue_type`, `plan_description`
  - `start_date`, `target_date`, `status` (active/completed/cancelled)
  - `milestones[]` — خطوات المتابعة
- **الواجهة**: Modal يحتوي نموذج:
  - نوع المشكلة (محدد مسبقاً)
  - وصف الخطة (textarea)
  - تاريخ البداية والهدف
  - خطوات المتابعة (قابلة للإضافة)

#### 3.3.3 جدولة متابعة للأسبوع القادم
- **الربط**: نظام المتابعات الحالي (`requires_follow_up` + `follow_up_date`)
- **التنفيذ**: إنشاء/تحديث سجل متابعة في `behaviour_records` أو `remedial_plans` مع:
  - `follow_up_date` = التاريخ المحدد (افتراضي: بعد أسبوع)
  - `follow_up_notes` = ملاحظات المتابعة
- **الواجهة**: Modal مختصر بتقويم لاختيار التاريخ + حقل ملاحظات

**الترتيب**: الطلاب الأكثر خطورة أولاً (مرتبة تنازلياً حسب Risk Score)

---

### 3.4 تحليل أسباب التعثر (Root Cause Analysis)

**الوصف**: مخطط دائري (Pie Chart) يعرض توزيع أسباب التعثر

**نوع المخطط**: Recharts `<PieChart>` مع labels

**الأسباب والحساب:**

| السبب | منطق التصنيف | اللون |
|-------|-------------|-------|
| الواجبات | طلاب تراجعت درجات واجباتهم أو لم يسلموها | أزرق `#3b82f6` |
| الغياب | طلاب نسبة حضورهم < 80% | أصفر `#eab308` |
| المشاركة | طلاب مصنفين "silent" في تحليل المشاركة | أخضر `#22c55e` |
| الاختبارات | طلاب تراجعت نتائج اختباراتهم | بنفسجي `#615090` |

**مصدر البيانات:**
- تحليل عوامل التعثر من Hakim AI Engine (الأوزان الأربعة)
- للطلاب المتعثرين فقط (risk score < 75): يُحسب العامل الأضعف لكل طالب
- النسب = عدد الطلاب المتعثرين بسبب كل عامل ÷ إجمالي المتعثرين

---

### 3.5 اقتراحات نسق — توصيات حكيم (AI Recommendations)

**الوصف**: قسم ذكي يقدم نصائح مبنية على البيانات عبر OpenAI

**أنواع التوصيات:**

| النوع | الأيقونة | لون الحد الأيمن | مثال |
|-------|---------|----------------|------|
| توصية كمية | 📊 | تركوازي `#46C1BE` | "5 طلاب يحتاجون متابعة مستمرة للواجبات" |
| توصية أكاديمية | 🎯 | تركوازي `#46C1BE` | "نقترح نشاطاً تفاعلياً جماعياً لفصل 5B" |
| تنبيه إحصائي | ⚠️ | أحمر `#ef4444` | "ارتفاع نسبة الغياب 12% عن الأسبوع الماضي" |
| نتيجة إيجابية | ✅ | أخضر `#22c55e` | "تحسن ملحوظ لـ 3 طلاب بعد التدخل المبكر" |
| توجيه إداري | 📋 | بنفسجي `#615090` | "ضرورة التواصل مع أولياء أمور فئة الخطر العالي" |

**آلية التوليد:**
1. Backend يجمع البيانات الإحصائية (عدد المتعثرين بالفئة، نسب التغيير الأسبوعية، نتائج التدخلات السابقة)
2. يُرسل البيانات المجمعة إلى OpenAI عبر Hakim AI Engine مع prompt باللغة العربية
3. OpenAI يُرجع توصيات مهيكلة (JSON) بالأنواع المحددة أعلاه
4. Frontend يعرضها كبطاقات ملونة

**Prompt Template:**
```
أنت مستشار تعليمي ذكي. بناءً على البيانات التالية لمدرسة:
- عدد الطلاب المتعثرين: {count}
- أسباب التعثر: {causes}
- نسبة التغيير عن الأسبوع الماضي: {weekly_change}
- عدد التدخلات الناجحة: {successful_interventions}
- فصول تحتاج اهتمام: {classes_needing_attention}

قدم 4-6 توصيات مهيكلة بصيغة JSON:
[{"type": "quantitative|academic|statistical_alert|positive|administrative", 
  "text": "نص التوصية باللغة العربية"}]
```

---

## 4. الهيكل التقني

### 4.1 Backend — Endpoints جديدة

#### `GET /ai/student-performance/dashboard`
**الوصف**: Endpoint رئيسي يُرجع كل بيانات اللوحة دفعة واحدة

**Request:**
```
GET /ai/student-performance/dashboard
Headers: Authorization: Bearer {token}
```

**Response:**
```json
{
  "summary": {
    "total_students": 200,
    "stable": {"count": 124, "percentage": 62},
    "needs_followup": {"count": 46, "percentage": 23},
    "at_risk": {"count": 20, "percentage": 10},
    "excelling": {"count": 10, "percentage": 5}
  },
  "risk_map": [
    {
      "student_id": "uuid",
      "name": "سارة الأحمدي",
      "class_name": "5A",
      "academic_score": 35,
      "engagement_score": 40,
      "risk_score": 38,
      "category": "at_risk",
      "factors": ["غياب متكرر", "تراجع واجبات"]
    }
  ],
  "intervention_list": [
    {
      "student_id": "uuid",
      "name": "سارة الأحمدي",
      "class_name": "5A",
      "category": "at_risk",
      "issue_type": "غياب متكرر",
      "risk_score": 38,
      "parent_id": "uuid"
    }
  ],
  "root_causes": {
    "homework": 40,
    "attendance": 25,
    "participation": 20,
    "exams": 15
  },
  "last_updated": "2026-04-13T10:30:00Z"
}
```

**المنطق الداخلي:**
1. جلب كل الطلاب النشطين في المدرسة (`tenant_id`)
2. لكل طالب: حساب Risk Score باستخدام `analyze_student_risk()` من Hakim Engine
3. تصنيف كل طالب حسب الفئات الأربع
4. حساب إحداثيات الـ Scatter Plot (academic_score, engagement_score)
5. تجميع أسباب التعثر للمتعثرين
6. ترتيب قائمة التدخل تنازلياً

**تحسينات الأداء:**
- Batch processing: جلب attendance, grades, behaviour لكل الطلاب في 3-4 queries بدل N+1
- Cache النتائج لمدة 5 دقائق (in-memory TTL cache)
- حد أقصى 500 طالب للـ risk_map (الأكثر خطورة أولاً)

#### `GET /ai/student-performance/recommendations`
**الوصف**: توصيات حكيم الذكية عبر OpenAI

**Response:**
```json
{
  "recommendations": [
    {"type": "quantitative", "text": "5 طلاب يحتاجون متابعة مستمرة للواجبات المنزلية", "icon": "📊"},
    {"type": "statistical_alert", "text": "ارتفاع نسبة الغياب 12% عن الأسبوع الماضي", "icon": "⚠️"},
    {"type": "positive", "text": "تحسن ملحوظ لـ 3 طلاب بعد التدخل المبكر", "icon": "✅"},
    {"type": "administrative", "text": "يُنصح بالتواصل مع أولياء أمور الطلاب ذوي الخطر العالي", "icon": "📋"}
  ],
  "generated_at": "2026-04-13T10:30:00Z"
}
```

#### `POST /ai/student-performance/intervention`
**الوصف**: تنفيذ إجراء تدخل لطالب

**Request Body:**
```json
{
  "student_id": "uuid",
  "action_type": "notify_parent | remedial_plan | schedule_followup",
  "data": {
    // لـ notify_parent:
    "message": "نص الرسالة",
    // لـ remedial_plan:
    "description": "وصف الخطة",
    "target_date": "2026-04-20",
    "milestones": ["خطوة 1", "خطوة 2"],
    // لـ schedule_followup:
    "follow_up_date": "2026-04-20",
    "notes": "ملاحظات"
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "تم إرسال الرسالة لولي الأمر بنجاح",
  "intervention_id": "uuid"
}
```

---

### 4.2 Backend — Collection جديد

#### `remedial_plans` (GenericDocument)
```json
{
  "collection": "remedial_plans",
  "data": {
    "student_id": "uuid",
    "created_by": "uuid",
    "school_id": "uuid",
    "issue_type": "attendance|homework|participation|exams",
    "description": "وصف الخطة العلاجية",
    "start_date": "2026-04-13",
    "target_date": "2026-04-27",
    "status": "active|completed|cancelled",
    "milestones": [
      {"text": "خطوة 1", "completed": false},
      {"text": "خطوة 2", "completed": false}
    ],
    "follow_up_date": "2026-04-20",
    "follow_up_notes": "",
    "created_at": "2026-04-13T10:30:00Z",
    "updated_at": "2026-04-13T10:30:00Z"
  }
}
```

---

### 4.3 Frontend — Components جديدة

#### هيكل الملفات
```
frontend/src/
├── components/
│   └── student-performance/
│       ├── StudentPerformanceDashboard.jsx    ← المكون الرئيسي (التبويب)
│       ├── ExecutiveSummaryCards.jsx           ← بطاقات KPI الأربع
│       ├── StudentRiskMap.jsx                 ← خريطة المخاطر (Scatter Chart)
│       ├── InterventionList.jsx               ← قائمة الطلاب المتعثرين
│       ├── InterventionActionModal.jsx        ← Modal إجراءات التدخل
│       ├── RootCauseChart.jsx                 ← مخطط أسباب التعثر (Pie Chart)
│       └── HakimRecommendations.jsx           ← توصيات حكيم الذكية
└── pages/
    └── AIInsightsPage.jsx                     ← تعديل: إضافة نظام التبويبات
```

#### تعديل AIInsightsPage.jsx
- إضافة نظام تبويبات (Tabs) باستخدام Radix UI `Tabs`
- التبويب الأول "الرؤى الذكية": المحتوى الحالي بالكامل (بدون تغيير)
- التبويب الثاني "تحليل أداء الطلاب": يحمّل `StudentPerformanceDashboard`
- التبويب الثاني يظهر فقط لأدوار `school_admin` و `school_sub_admin`
- خط التبويب النشط بلون تركوازي (`#46C1BE`)

#### StudentPerformanceDashboard.jsx (المكون الرئيسي)
```
المسؤوليات:
- جلب البيانات من /ai/student-performance/dashboard
- جلب التوصيات من /ai/student-performance/recommendations
- إدارة حالة التحميل والتحديث
- زر "تحديث البيانات" اليدوي
- تمرير البيانات للمكونات الفرعية
- عرض الأقسام الخمسة بالتسلسل

State:
- dashboardData: بيانات اللوحة الرئيسية
- recommendations: توصيات حكيم
- loading: حالة التحميل الأولي
- refreshing: حالة التحديث اليدوي
- selectedStudent: الطالب المحدد للإجراء
- actionModalOpen: حالة فتح modal الإجراء
- actionType: نوع الإجراء المحدد
```

---

### 4.4 خطة ترجمة المفاتيح (i18n)

مفاتيح جديدة تُضاف إلى `ar.json` و `en.json`:

```json
{
  "studentPerformance": "تحليل أداء الطلاب",
  "executiveSummary": "ملخص تنفيذي",
  "stable": "مستقر",
  "needsFollowup": "يحتاج متابعة",
  "educationalRisk": "خطر تعليمي",
  "excelling": "متفوقون",
  "riskMap": "خريطة المخاطر",
  "studentsNeedIntervention": "طلاب يحتاجون تدخلاً",
  "takeAction": "اتخاذ إجراء",
  "sendParentMessage": "رسالة لولي الأمر",
  "createRemedialPlan": "خطة علاجية",
  "scheduleFollowup": "متابعة الأسبوع القادم",
  "rootCauseAnalysis": "أسباب التعثر",
  "homework": "الواجبات",
  "attendance": "الغياب",
  "participation": "المشاركة",
  "exams": "الاختبارات",
  "nassaqSuggestions": "اقتراحات نسق",
  "refreshData": "تحديث البيانات",
  "lastUpdated": "آخر تحديث",
  "interventionSuccess": "تم تنفيذ الإجراء بنجاح",
  "messageSentToParent": "تم إرسال الرسالة لولي الأمر بنجاح",
  "remedialPlanCreated": "تم إنشاء الخطة العلاجية بنجاح",
  "followupScheduled": "تمت جدولة المتابعة بنجاح",
  "planDescription": "وصف الخطة",
  "targetDate": "تاريخ الهدف",
  "milestones": "خطوات المتابعة",
  "followupDate": "تاريخ المتابعة",
  "followupNotes": "ملاحظات المتابعة",
  "noStudentsAtRisk": "لا يوجد طلاب في فئة الخطر حالياً",
  "academicScore": "الأداء الأكاديمي",
  "engagementScore": "المشاركة والحضور"
}
```

---

## 5. مخطط تدفق البيانات

```
┌──────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│   Frontend   │────▸│  Backend API         │────▸│   Database       │
│              │     │                      │     │                  │
│ Dashboard    │ GET │ /student-performance │     │ students         │
│ Component    │────▸│ /dashboard           │────▸│ attendance       │
│              │     │                      │     │ student_grades   │
│              │     │ ┌──────────────────┐ │     │ behaviour_records│
│              │     │ │ Hakim AI Engine  │ │     │ student_daily_   │
│              │     │ │ analyze_student_ │ │     │   scores         │
│              │     │ │ risk() × N       │ │     │ session_         │
│              │     │ └──────────────────┘ │     │   interactions   │
│              │     │                      │     └──────────────────┘
│              │ GET │ /student-performance │     ┌──────────────────┐
│ Recommen-    │────▸│ /recommendations     │────▸│   OpenAI API     │
│ dations      │     │                      │     │   (via Hakim)    │
│              │     │                      │     └──────────────────┘
│              │POST │ /student-performance │     ┌──────────────────┐
│ Intervention │────▸│ /intervention        │────▸│ notifications    │
│ Modal        │     │                      │     │ remedial_plans   │
│              │     │                      │     │ behaviour_records│
└──────────────┘     └─────────────────────┘     └──────────────────┘
```

---

## 6. خطوات التنفيذ المقترحة

### المرحلة 1: البنية التحتية (Backend)
1. **إنشاء endpoint الـ dashboard** — جلب وتصنيف الطلاب، حساب Risk Scores بالجملة، بناء الاستجابة
2. **إنشاء endpoint التوصيات** — تجميع الإحصائيات، بناء الـ prompt، استدعاء OpenAI، هيكلة الاستجابة
3. **إنشاء endpoint التدخل** — ربط إرسال الرسائل بـ NotificationEngine، إنشاء collection الخطط العلاجية، ربط جدولة المتابعات بنظام المتابعات الحالي
4. **تحسين الأداء** — Batch queries، caching، حدود الـ pagination

### المرحلة 2: الواجهة الأمامية (Frontend)
5. **تعديل AIInsightsPage** — إضافة نظام التبويبات مع فحص الأدوار
6. **بناء المكون الرئيسي** — StudentPerformanceDashboard مع state management وdata fetching
7. **بناء بطاقات KPI** — ExecutiveSummaryCards مع الألوان والأيقونات
8. **بناء خريطة المخاطر** — StudentRiskMap مع Recharts ScatterChart والتفاعل
9. **بناء قائمة التدخل** — InterventionList مع أزرار الإجراء والقائمة المنسدلة
10. **بناء modal الإجراءات** — InterventionActionModal مع النماذج الثلاثة (رسالة، خطة، متابعة)
11. **بناء مخطط الأسباب** — RootCauseChart مع Recharts PieChart
12. **بناء التوصيات** — HakimRecommendations مع البطاقات الملونة
13. **إضافة مفاتيح i18n** — ترجمة كل النصوص في ar.json و en.json

### المرحلة 3: التكامل والاختبار
14. **ربط Frontend بالـ Backend** — استدعاء الـ APIs، معالجة الأخطاء، حالات التحميل والفراغ
15. **اختبار الأدوار** — التأكد من ظهور التبويب فقط لـ school_admin و school_sub_admin
16. **اختبار الإجراءات** — التأكد من إرسال الرسائل فعلياً، إنشاء الخطط، جدولة المتابعات
17. **اختبار الأداء** — التأكد من سرعة التحميل مع بيانات كبيرة

---

## 7. الملفات المتأثرة

### ملفات موجودة (تعديل)
- `frontend/src/pages/AIInsightsPage.jsx` — إضافة نظام التبويبات
- `frontend/src/locales/ar.json` — مفاتيح ترجمة جديدة
- `frontend/src/locales/en.json` — مفاتيح ترجمة جديدة
- `backend/app/routes.py` — تسجيل الـ router الجديد
- `backend/engines/hakim_ai_engine.py` — دالة batch risk scoring جديدة

### ملفات جديدة
- `frontend/src/components/student-performance/StudentPerformanceDashboard.jsx`
- `frontend/src/components/student-performance/ExecutiveSummaryCards.jsx`
- `frontend/src/components/student-performance/StudentRiskMap.jsx`
- `frontend/src/components/student-performance/InterventionList.jsx`
- `frontend/src/components/student-performance/InterventionActionModal.jsx`
- `frontend/src/components/student-performance/RootCauseChart.jsx`
- `frontend/src/components/student-performance/HakimRecommendations.jsx`
- `backend/routes/student_performance_routes.py`

---

## 8. خارج النطاق (Out of Scope)

- تصدير التقارير بصيغة PDF/Excel (يمكن إضافته لاحقاً)
- تحديث لحظي عبر WebSocket (اختيار: تحديث يدوي)
- عرض اللوحة للمعلمين أو أولياء الأمور (اختيار: admin + sub_admin فقط)
- تاريخ التدخلات السابقة وتتبعها (يمكن إضافته كمرحلة ثانية)
- مقارنة بين الفصول أو بين الفترات الزمنية
- إشعارات push تلقائية عند تغير حالة طالب

---

## 9. المخاطر والاعتبارات

| المخاطر | التخفيف |
|---------|---------|
| بطء حساب Risk Score لكل الطلاب | Batch processing + caching 5 دقائق |
| تكلفة OpenAI للتوصيات | Cache التوصيات لمدة 15 دقيقة، حد أقصى 6 توصيات |
| عدم وجود بيانات كافية لطلاب جدد | إظهار "بيانات غير كافية" بدل تصنيف خاطئ |
| Tenant isolation | كل الـ queries تتضمن `school_id`/`tenant_id` |
| حجم ملف AIInsightsPage (951 سطر) | التبويب الجديد في مكون منفصل يُحمل lazily |

---

## 10. معايير القبول

- [ ] بطاقات KPI تعرض أرقام حقيقية من قاعدة البيانات
- [ ] خريطة المخاطر تفاعلية ويمكن النقر على أي نقطة
- [ ] قائمة التدخل تعرض الطلاب مرتبة حسب درجة الخطورة
- [ ] زر "إرسال رسالة لولي الأمر" يُرسل إشعار فعلي
- [ ] زر "خطة علاجية" يُنشئ خطة فعلية في قاعدة البيانات
- [ ] زر "جدولة متابعة" يُنشئ موعد متابعة فعلي
- [ ] المخطط الدائري يعرض نسب حقيقية من تحليل البيانات
- [ ] توصيات حكيم تُولّد عبر OpenAI باللغة العربية
- [ ] التبويب يظهر فقط لـ school_admin و school_sub_admin
- [ ] الواجهة RTL بالكامل وتتبع ألوان نسق
- [ ] جميع النصوص مترجمة (ar + en)
- [ ] الأداء مقبول (< 3 ثوانٍ للتحميل الأولي)

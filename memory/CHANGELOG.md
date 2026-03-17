# NASSAQ Changelog

## March 10, 2026 - Session 3 Updates

### ✅ تحديث صفحة تسجيل الدخول

تم إضافة جميع الحسابات التجريبية:

| الدور | البريد الإلكتروني | كلمة المرور |
|-------|------------------|-------------|
| 👑 مدير المنصة | admin@nassaq.com | Admin@123 |
| 👨‍💼 مدير مدرسة النور | principal1@nassaq.com | Principal@123 |
| 👨‍💼 مدير مدرسة العلي | principal2@nassaq.com | Principal@123 |
| 👨‍💼 مدير مدرسة المنارة | principal3@nassaq.com | Principal@123 |
| 👨‍💼 مدير مدرسة الاحساء | principal4@nassaq.com | Principal@123 |
| 👨‍💼 مدير مدرسة الحديثة | principal5@nassaq.com | Principal@123 |
| 👨‍🏫 معلم | teacher1@nor.edu.sa | Teacher@123 |
| 👨‍🎓 طالب | student1@nor.edu.sa | Student@123 |
| 👨‍👩‍👧 ولي أمر | parent1@nor.edu.sa | Parent@123 |

---

### ✅ إنشاء صفحة إدارة حضور المعلمين

تم إنشاء صفحة جديدة `/admin/teacher-attendance` مخصصة لمدير المدرسة:

**الوظائف:**
- تسجيل حضور المعلمين (حاضر، غائب، متأخر، بعذر)
- إضافة ملاحظات لكل معلم
- إحصائيات الحضور (إجمالي، حاضر، غائب، متأخر)
- شريط تقدم نسبة الحضور
- زر "الكل حاضر" لتسجيل جماعي
- تقارير حضور المعلمين

**تغيير الاسم:**
- **القديم:** إدارة الحضور والانصراف
- **الجديد:** إدارة الحضور (Attendance Management)

**ملاحظة معمارية:**
- صفحة حضور المعلمين → مدير المدرسة
- تحضير الطلاب → المعلمين داخل الحصة (Teacher Interface)

---

### ✅ تحسين صفحة الجدول المدرسي (Teacher Grid View)

تم إضافة عرض جديد للجدول: **Teacher Schedule Grid**

**العرض الجديد (Teacher View):**
- الصفوف = المعلمين
- الأعمدة = أيام الأسبوع (الأحد → الخميس)
- كل يوم = 7 حصص
- شريط نصاب المعلم (مثال: 24/30)
- ألوان مميزة لكل مادة

**ميزات كروت الحصص:**
- اسم المادة
- اسم الفصل
- دعم السحب والإفلات (Drag & Drop)
- كشف التعارضات
- أيقونة القفل للحصص المثبتة

**أزرار التبديل:**
- **"المعلمين"** - عرض الجدول من منظور المعلمين
- **"الفصول"** - العرض التقليدي (الأيام × الحصص)

---

### ✅ Backend APIs الجديدة

تم إضافة APIs لحضور المعلمين:

```
GET  /api/attendance/teacher-attendance?date=YYYY-MM-DD
POST /api/attendance/teacher-attendance/bulk
GET  /api/attendance/teacher-attendance/report/summary
```

---

## ملفات تم إنشاؤها/تعديلها

### ملفات جديدة:
- `/app/frontend/src/pages/TeacherAttendancePage.jsx` - صفحة حضور المعلمين
- `/app/frontend/src/components/schedule/TeacherScheduleGrid.jsx` - مكون شبكة جدول المعلمين

### ملفات معدّلة:
- `/app/frontend/src/pages/LoginPage.jsx` - إضافة حسابات تجريبية
- `/app/frontend/src/pages/SchedulePage.jsx` - إضافة Teacher Grid View
- `/app/frontend/src/components/layout/Sidebar.jsx` - تغيير اسم "إدارة الحضور"
- `/app/frontend/src/App.js` - إضافة route جديد
- `/app/backend/routes/attendance_routes.py` - إضافة APIs حضور المعلمين

---

## Test Results

### Pages Working:
- ✅ Login Page - جميع الحسابات التجريبية
- ✅ Schedule Page - عرض المعلمين + عرض الفصول
- ✅ Teacher Attendance Page - تسجيل حضور المعلمين
- ✅ Teachers Page - Tenant Isolation
- ✅ Students Page - Tenant Isolation
- ✅ Classes Page - Tenant Isolation

---

## Last Updated: March 10, 2026

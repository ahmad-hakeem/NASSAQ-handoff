# 📋 تقرير الفحص والتدقيق الفني والمعماري للـ Backend (NASSAQ Backend Defects & Architecture Audit)

**تاريخ التقرير**: 14 أغسطس 2026  
**النطاق**: كود الـ Backend، طبقة البيانات، إدارة الـ Lifecycle، الأمان، وهيكل الموديولات  
**الحالة العامة**: النظام يعمل وظيفياً، لكن توجد مشاكل نشطة وتراكمات معمارية تحتاج إلى معالجة.

---

## 📑 فهرس التقرير
1. [🔴 عيوب برمجية نشطة (Active Runtime Bugs)](#1-عيوب-برمجية-نشطة-active-runtime-bugs)
2. [🟠 عيوب معمارية في التعامل مع البيانات (Database & ORM Layer)](#2-عيوب-معمارية-في-التعامل-مع-البيانات-database--orm-layer)
3. [🟡 تضخم الملفات البرمجية والـ God Files](#3-تضخم-الملفات-البرمجية-والـ-god-files)
4. [🔵 اكتمال بنية الـ NestJS والـ Clean Architecture](#4-اكتمال-بنية-الـ-nestjs-والـ-clean-architecture)
5. [🟣 الأداء، التخزين المؤقت (Caching) والأمان](#5-الأداء-التخزين-المؤقت-caching-والأمان)
6. [🛠️ خطة العمل المقترحة (Action & Remediation Plan)](#6-خطة-العمل-المقترحة-action--remediation-plan)

---

## 🔴 1. عيوب برمجية نشطة (Active Runtime Bugs)

### 1.1 فشل إيقاف السيرفر (`CancelledError` في `shutdown_tasks`)
* **الخطورة**: 🔴 **عالية (High)**
* **الملف المتأثر**: `app/lifecycle.py` و `src/core/lifecycle/hooks.py`
* **الأثر عند التشغيل**: في كل مرة يتم فيها عمل Reload أو إيقاف السيرفر بـ `Ctrl+C`، ينهار الـ Process بهذا الخطأ:
  ```text
  File ".../backend/app/lifecycle.py", line 1136, in shutdown_tasks
      await _revoked_token_cleanup_task
  ...
  asyncio.exceptions.CancelledError
  ERROR:    Application shutdown failed. Exiting.
  ```
* **السبب الجذري**:
  دالة `shutdown_tasks` تستخدم:
  ```python
  try:
      await _revoked_token_cleanup_task
  except Exception:
      pass
  ```
  في Python 3.8 وما بعده، يرث `asyncio.CancelledError` من `BaseException` وليس `Exception`، وبالتالي لا تلتقطه كتلة `except Exception:`، فيطفو الخطأ ويلغي إيقاف التطبيق الطبيعي.
* **الحل الجذري**:
  استخدام الدالة المساعدة الموجودة مسبقاً `_cancel_background_task`:
  ```python
  global _revoked_token_cleanup_task
  await _cancel_background_task(_revoked_token_cleanup_task)
  _revoked_token_cleanup_task = None
  ```

---

### 1.2 تحذير فشل تحديد إصدار Alembic عند الإقلاع (Alembic Head Revision Warning)
* **الخطورة**: 🟠 **متوسطة (Medium)**
* **الملف المتأثر**: `src/core/database/db.py`
* **الأثر عند التشغيل**:
  ```text
  {"level": "WARNING", "logger": "nassaq.db", "msg": "Could not determine Alembic head revision: No 'script_location' key found in configuration."}
  ```
* **السبب الجذري**:
  الدالة تبحث عن ملف `alembic.ini` في المسار `os.path.join(os.path.dirname(__file__), "alembic.ini")`. وحيث أن `db.py` نُقل إلى `src/core/database/`، أصبح يبحث عن الملف داخل مجلد `database` بدلاً من المجلد الرئيسي `backend/`.
* **الحل الجذري**:
  تصحيح المسار ليكون ديناميكياً يشير لجذر المشروع:
  ```python
  from pathlib import Path
  ini_path = str(Path(__file__).resolve().parents[3] / "alembic.ini")
  ```

---

## 🟠 2. عيوب معمارية في التعامل مع البيانات (Database & ORM Layer)

### 2.1 الاعتماد على NoSQL-like Helpers (`sql_utils.py`) فوق PostgreSQL
* **الخطورة**: 🟠 **عالية (Architectural Debt)**
* **الملف المتأثر**: `engines/sql_utils.py` (58 KB)
* **المشكلة**:
  يتم تنفيذ معظم عمليات القراءة والكتابة عبر دوال مثل `gd_find`, `gd_find_one`, `gd_insert`, `gd_update_one`, `gd_delete_one` وتمرير نصوص الجداول وقواميس (`dicts`) بدلاً من استخدام استعلامات SQLAlchemy ORM Type-safe.
* **السلبيات**:
  1. **فقدان الـ Type-Safety**: غياب التحقق المسبق من أسماء الحقول وأنواعها أثناء الكتابة والتطوير.
  2. **تجاوز قيود الـ ORM**: لا يتم تشغيل دوال الـ `@validates` المعرفة داخل كلاسات الـ Entities.
  3. **تعقيد الاستعلامات المركبة**: صعوبة عمل Joins و Grouping وتحسين أداء الـ SQL.

---

### 2.2 إدارة الـ Sessions العامة عبر `contextvars` و `db = Repos()`
* **الخطورة**: 🟡 **متوسطة (Code Smell)**
* **المكان**: `src/core/database/repository.py` و `dependencies.py`
* **المشكلة**:
  إنشاء كائن جلوبال `db = Repos()` والاعتماد على `db.session` السحري المعتمد على `contextvars` بدلاً من تمرير وحقن الـ `AsyncSession` عبر `Depends(get_pg_session)` داخل دوال الـ Services والـ Repositories.

---

## 🟡 3. تضخم الملفات البرمجية والـ God Files

توجد ملفات ضخمة جداً تحتوي على آلاف الأسطر ومئات الوظائف المتشابكة، مما يصعب صيانتها واختبارها:

| الملف | الحجم | عدد الأسطر | التوصيف والمشكلة |
|---|---|---|---|
| `engines/session_engine.py` | **288 KB** | ~4,200 | كلاس عملاق يحتوي منطق إدارة الحصص، التحضير، النقاط، الملاحظات، والمزامنة |
| `src/modules/ai/controllers/ai_routes_mod.py` | **262 KB** | ~3,800 | ملف تحكم ضخم يجمع جميع مسارات الذكاء الاصطناعي وخطط حكيم |
| `src/modules/portals/controllers/role_dashboards_mod.py` | **224 KB** | ~3,400 | يجمع إحصائيات ومسارات لوحات التحكم لجميع الأدوار (مدير، معلم، ولي أمر، طالب) |
| `engines/smart_scheduling_engine.py` | **210 KB** | ~3,100 | خوارزمية الجداول المدرسية متداخلة مع معالجة القيود والحفظ في قاعدة البيانات |
| `src/modules/portals/controllers/parent_portal_routes.py` | **199 KB** | ~2,900 | جميع خدمات ولي الأمر (الدرجات، الحضور، الرسائل، الجدول) في ملف مسار واحد |
| `dependencies.py` | **35 KB** | 778 | يستورد كافة المحركات والمودلز في ملف واحد كـ Central Dependency Hub |

---

## 🔵 4. اكتمال بنية الـ NestJS والـ Clean Architecture

1. **انتقال منطق الأعمال (Business Logic)**:
   - تم تنظيم الـ Entities والـ DTOs والـ Controllers داخل `src/modules/`.
   - الخطوة التالية المتبقية هي استخراج الدوال المنطقية من `engines/` ومن داخل الـ Controllers ووضعها في دوال نقية داخل فئات الـ `xxx_service.py`.
2. **تفعيل طبقة الـ Repositories**:
   - تحويل كلاسات `xxx_repository.py` في كل موديول لتشمل استعلامات SQLAlchemy الصريحة الخاصة بكل دومين (بدلاً من استدعاء `sql_utils`).

---

## 🟣 5. الأداء، التخزين المؤقت (Caching) والأمان

### 5.1 فحص التوكينات الملغاة (Token Revocation) في قاعدة البيانات
* **الوضع الحالي**: عند كل طلب يحمل Bearer Token، يتم التحقق من جدول `revoked_tokens` عبر استعلام SQL في PostgreSQL.
* **المشكلة**: مع زيادة عدد المستخدمين المتزامنين، يشكل هذا ضغطاً غير ضروري على قاعدة البيانات.
* **الحل**: استخدام **Redis In-Memory Key-Value Store** مع TTL مساوٍ لوقت انتهاء التوكن للتحقق بـ `O(1)` وزمن استجابة `< 1ms`.

### 5.2 تحذيرات Pytest (Asyncio Mark Warnings)
* **المشكلة**: وجود 3 تحذيرات متكررة في ملف `backend/tests/test_security_phase1.py` بسبب وضع علامة `@pytest.mark.asyncio` على دوال اختبار متزامنة عادية (Synchronous).

---

## 🛠️ خطة العمل المقترحة (Action & Remediation Plan)

### ⚡ المرحلة 1: إصلاح العيوب الفورية (Quick Wins)
- [ ] إصلاح مسار `alembic.ini` في `src/core/database/db.py`.
- [ ] إصلاح معالجة `asyncio.CancelledError` في `app/lifecycle.py` لمنع خطأ الإيقاف.
- [ ] إزالة ديكوريتور `@pytest.mark.asyncio` من الدوال المتزامنة في الاختبارات.

### 🏗️ المرحلة 2: تفكيك الـ God Files وتقسيم الـ Services
- [ ] تقسيم `session_engine.py` (288KB) إلى Services متخصصة داخل `src/modules/sessions/`.
- [ ] تقسيم ملفات الكنترولر المتضخمة في `portals` و `ai`.

### 🚀 المرحلة 3: تحسين الأداء وقاعدة البيانات
- [ ] تحويل الاستعلامات تدريجياً من `sql_utils` إلى استعلامات SQLAlchemy ORM Typed داخل الـ Repositories.
- [ ] إضافة طبقة Redis للتخزين المؤقت والتحقق من التوكينات الملغاة.

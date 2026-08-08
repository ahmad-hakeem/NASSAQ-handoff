# NASSAQ Backend — نَسَّق (محرك الخدمة الخلفية)

طريقة تشغيل وتطوير خادم الخلفية (FastAPI Backend) لمنصة نَسَّق.

---

## 📋 المتطلبات الأساسية (Prerequisites)

- **Python 3.12**
- **Conda** (أو بيئة افتراضية virtual environment)
- **PostgreSQL 16** (محلياً أو عبر Docker)

---

## 🚀 تشغيل الباك إند محلياً بواسطة Conda (Local Development with Conda)

### 1. إعداد بيئة Conda وتثبيت الحزم

```bash
# إنشاء بيئة Conda جديدة باسم nassaq مع Python 3.12
conda create -n nassaq python=3.12 -y

# تفعيل البيئة
conda activate nassaq

# تثبيت مكتبة uv للتثبيت السريع (اختياري ولكن يفضل)
pip install uv

# تثبيت كامل حزم المشروع
uv pip install --system -r ../pyproject.toml -r requirements.txt
```

### 2. إعداد قاعدة البيانات (PostgreSQL)

تأكد من تشغيل حاوية قاعدة البيانات في Docker أو تشغيل خادم PostgreSQL محلي على المنفذ `5432`:

```bash
# تشغيل حاوية قاعدة البيانات فقط عبر Docker Compose من المجلد الرئيسي للمشروع:
docker compose up -d db
```

### 3. إعداد ملف المتغيرات البيئية (`.env`)

تأكد من وجود ملف `.env` داخل المجلد الرئيسي للمشروع أو داخل مجلد `backend/.env` يحتوي على `DATABASE_URL`:

```env
DATABASE_URL=postgresql+asyncpg://nassaq:cf5382a239eb5f0af2e8060ccd170a52@localhost:5432/nassaq
JWT_SECRET_KEY=your-secret-key
MFA_ENCRYPTION_KEY=your-mfa-key
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:8000,http://localhost:3000
ALLOWED_HOSTS=*
APP_PORT=8000
```

### 4. تطبيق ترحيلات قاعدة البيانات (Database Migrations)

قبل تشغيل السيرفر لأول مرة أو بعد إجراء أي التحديثات، نفّذ الأمر التالي لتطبيق Alembic Migrations:

```bash
# من داخل مجلد backend
python -c "import dotenv, subprocess; dotenv.load_dotenv('.env'); subprocess.run(['alembic', 'upgrade', 'head'], check=True)"
```

أو مباشرة إذا كانت المتغيرات مفعّلة في البيئة:
```bash
alembic upgrade head
```

### 5. تشغيل السيرفر (Start Backend Server)

من داخل مجلد `backend`:

```bash
# التشغيل مع القراءة التلقائية لملف .env والتحديث التلقائي عند تعديل الكود (--reload)
python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload --env-file .env
```

أو عبر المسار المباشر لبيئة conda:
```bash
/opt/anaconda3/envs/nassaq/bin/python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload --env-file .env
```

---

## 🐳 التشغيل الكامل عبر Docker Compose (Full Containerized Run)

إذا كنت تفضل تشغيل التطبيق بالكامل (الباك إند وقاعدة البيانات والفرونت إند المدمج) عبر Docker:

```bash
# من مجلد المشروع الرئيسي
docker compose up -d --build
```

---

## 🌐 روابط وواجهات الهامّة (Endpoints & Documentation)

عند تشغيل الخادم على الرابط `http://localhost:8000`:

- **فحص صحة الخدمة (Health Check):** `http://localhost:8000/system/health`
- **توثيق التفاعلات والواجهات (Swagger OpenAPI):** `http://localhost:8000/docs`
- **توثيق ReDoc:** `http://localhost:8000/redoc`

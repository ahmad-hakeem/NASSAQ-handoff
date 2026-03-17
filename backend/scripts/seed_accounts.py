"""
سكريبت إنشاء الحسابات الأساسية لنظام نَسَّق
Creates all role-based accounts for testing and initial use
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from dotenv import load_dotenv
import bcrypt
import uuid
from datetime import datetime, timezone

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'test_database')

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def now():
    return datetime.now(timezone.utc).isoformat()

def main():
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=10000)
    db = client[DB_NAME]

    print("🔌 Connected to MongoDB:", DB_NAME)

    # ==========================================
    # SCHOOL DATA
    # ==========================================
    school_id = "school-demo-001"
    school = {
        "id": school_id,
        "name_ar": "مدرسة النور النموذجية",
        "name_en": "Al-Noor Model School",
        "type": "mixed",
        "status": "active",
        "license_number": "EDU-2024-001",
        "city": "الرياض",
        "address": "حي النزهة، شارع الملك فهد",
        "phone": "+966112345678",
        "email": "info@alnoor.edu.sa",
        "principal_name": "أ. محمد العتيبي",
        "student_count": 500,
        "teacher_count": 30,
        "subscription_plan": "premium",
        "created_at": now(),
        "academic_year": "2024-2025",
    }
    db.schools.update_one({"id": school_id}, {"$set": school}, upsert=True)
    print(f"✅ School created: {school['name_ar']}")

    # ==========================================
    # ACCOUNTS
    # ==========================================
    accounts = [
        # --- مدير المنصة ---
        {
            "id": str(uuid.uuid4()),
            "email": "admin@nassaq.com",
            "password": "Admin@1234",
            "role": "platform_admin",
            "full_name": "مدير المنصة الرئيسي",
            "school_id": None,
            "is_active": True,
            "must_change_password": False,
        },
        # --- مدير عمليات المنصة ---
        {
            "id": str(uuid.uuid4()),
            "email": "ops@nassaq.com",
            "password": "Ops@1234",
            "role": "platform_operations_manager",
            "full_name": "مدير عمليات المنصة",
            "school_id": None,
            "is_active": True,
            "must_change_password": False,
        },
        # --- مدير المدرسة ---
        {
            "id": str(uuid.uuid4()),
            "email": "schooladmin@alnoor.edu.sa",
            "password": "School@1234",
            "role": "school_admin",
            "full_name": "مدير مدرسة النور",
            "school_id": school_id,
            "tenant_id": school_id,
            "is_active": True,
            "must_change_password": False,
        },
        # --- مدير فرعي للمدرسة ---
        {
            "id": str(uuid.uuid4()),
            "email": "subadmin@alnoor.edu.sa",
            "password": "Sub@1234",
            "role": "school_sub_admin",
            "full_name": "المدير الفرعي للمدرسة",
            "school_id": school_id,
            "tenant_id": school_id,
            "is_active": True,
            "must_change_password": False,
        },
        # --- المدير / الناظر ---
        {
            "id": str(uuid.uuid4()),
            "email": "principal@alnoor.edu.sa",
            "password": "Principal@1234",
            "role": "school_principal",
            "full_name": "أ. محمد العتيبي",
            "school_id": school_id,
            "tenant_id": school_id,
            "is_active": True,
            "must_change_password": False,
        },
        # --- معلم ---
        {
            "id": str(uuid.uuid4()),
            "email": "teacher@alnoor.edu.sa",
            "password": "Teacher@1234",
            "role": "teacher",
            "full_name": "أحمد محمد القحطاني",
            "school_id": school_id,
            "tenant_id": school_id,
            "is_active": True,
            "must_change_password": False,
        },
        # --- طالب ---
        {
            "id": str(uuid.uuid4()),
            "email": "student@alnoor.edu.sa",
            "password": "Student@1234",
            "role": "student",
            "full_name": "علي سعد الغامدي",
            "school_id": school_id,
            "tenant_id": school_id,
            "is_active": True,
            "must_change_password": False,
        },
        # --- ولي أمر ---
        {
            "id": str(uuid.uuid4()),
            "email": "parent@alnoor.edu.sa",
            "password": "Parent@1234",
            "role": "parent",
            "full_name": "سعد عبدالله الغامدي",
            "school_id": school_id,
            "tenant_id": school_id,
            "is_active": True,
            "must_change_password": False,
        },
    ]

    print("\n📋 إنشاء الحسابات:")
    print("-" * 60)

    for acc in accounts:
        password_plain = acc.pop("password")
        acc["password_hash"] = hash_password(password_plain)
        acc["created_at"] = now()
        acc["updated_at"] = now()

        existing = db.users.find_one({"email": acc["email"]})
        if existing:
            db.users.update_one({"email": acc["email"]}, {"$set": acc})
            print(f"🔄 Updated: {acc['email']}  |  password: {password_plain}  |  role: {acc['role']}")
        else:
            db.users.insert_one(acc)
            print(f"✅ Created: {acc['email']}  |  password: {password_plain}  |  role: {acc['role']}")

    print("\n" + "=" * 60)
    print("✅ تم إنشاء جميع الحسابات بنجاح!")
    print("=" * 60)
    print("\n📌 ملخص الحسابات:")
    print(f"{'الدور':<30} {'البريد الإلكتروني':<35} {'كلمة المرور'}")
    print("-" * 85)
    summary = [
        ("مدير المنصة (Platform Admin)",      "admin@nassaq.com",           "Admin@1234"),
        ("مدير عمليات (Ops Manager)",          "ops@nassaq.com",             "Ops@1234"),
        ("مدير مدرسة (School Admin)",          "schooladmin@alnoor.edu.sa",  "School@1234"),
        ("مدير فرعي (Sub Admin)",              "subadmin@alnoor.edu.sa",     "Sub@1234"),
        ("مدير / ناظر (Principal)",            "principal@alnoor.edu.sa",    "Principal@1234"),
        ("معلم (Teacher)",                     "teacher@alnoor.edu.sa",      "Teacher@1234"),
        ("طالب (Student)",                     "student@alnoor.edu.sa",      "Student@1234"),
        ("ولي أمر (Parent)",                   "parent@alnoor.edu.sa",       "Parent@1234"),
    ]
    for role, email, pwd in summary:
        print(f"{role:<30} {email:<35} {pwd}")

    client.close()

if __name__ == "__main__":
    main()

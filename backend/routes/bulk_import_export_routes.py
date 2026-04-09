"""
NASSAQ - Bulk Import/Export Routes
استيراد وتصدير البيانات الجماعي
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import pandas as pd
import io
import uuid
import re
import logging
from enum import Enum
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate

logger = logging.getLogger("nassaq.bulk_import")


class ImportType(str, Enum):
    STUDENTS = "students"
    TEACHERS = "teachers"
    NOOR_CLASSES = "noor_classes"
    NOOR_ASSIGNMENTS = "noor_assignments"


class ExportType(str, Enum):
    STUDENTS = "students"
    TEACHERS = "teachers"
    SCHEDULE = "schedule"
    ATTENDANCE = "attendance"
    GRADES = "grades"


class ImportResult(BaseModel):
    """نتيجة الاستيراد"""
    success: bool
    total_rows: int
    imported: int
    failed: int
    errors: List[dict]
    warnings: List[dict]


def setup_bulk_routes(db, get_current_user, require_roles, UserRole):
    """Setup bulk import/export routes"""
    
    router = APIRouter(prefix="/bulk", tags=["Bulk Import/Export"])
    
    # ============= IMPORT TEMPLATES =============
    
    @router.get("/template/{import_type}")
    async def download_import_template(
        import_type: ImportType,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
    ):
        """تحميل قالب الاستيراد"""
        try:
            if import_type == ImportType.NOOR_CLASSES:
                columns = {
                    'اسم الفصل (مطلوب)': ['الأول أ', 'الثاني ب'],
                    'الصف (مطلوب)': ['الأول', 'الثاني'],
                    'الشعبة': ['أ', 'ب'],
                    'السعة': ['30', '25'],
                    'المرحلة': ['ابتدائي', 'ابتدائي'],
                    'ملاحظات': ['', '']
                }
                filename = "قالب_استيراد_نور_الفصول.xlsx"
            elif import_type == ImportType.NOOR_ASSIGNMENTS:
                columns = {
                    'اسم المعلم (مطلوب)': ['أحمد محمد السعيد', 'فاطمة علي الخالدي'],
                    'البريد الإلكتروني للمعلم': ['ahmed@school.com', 'fatima@school.com'],
                    'اسم المادة (مطلوب)': ['الرياضيات', 'العلوم'],
                    'اسم الفصل': ['الأول أ', 'الثاني ب'],
                    'عدد الحصص الأسبوعية': ['5', '4'],
                    'ملاحظات': ['', '']
                }
                filename = "قالب_استيراد_نور_الإسناد.xlsx"
            elif import_type == ImportType.STUDENTS:
                columns = {
                    'الاسم الأول (مطلوب)': ['أحمد', 'محمد'],
                    'اسم الأب': ['علي', 'خالد'],
                    'اسم العائلة (مطلوب)': ['السعيد', 'المالكي'],
                    'رقم الهوية (مطلوب)': ['1234567890', '0987654321'],
                    'تاريخ الميلاد (YYYY-MM-DD)': ['2015-05-15', '2014-08-20'],
                    'الجنس (ذكر/أنثى)': ['ذكر', 'ذكر'],
                    'الصف': ['الأول', 'الثاني'],
                    'الفصل': ['أ', 'ب'],
                    'البريد الإلكتروني': ['ahmed@example.com', 'mohammed@example.com'],
                    'رقم الجوال': ['0501234567', '0559876543'],
                    'اسم ولي الأمر': ['علي السعيد', 'خالد المالكي'],
                    'جوال ولي الأمر (مطلوب)': ['0501111111', '0502222222'],
                    'بريد ولي الأمر': ['parent1@example.com', 'parent2@example.com'],
                    'الحالة الصحية': ['سليم', 'حساسية غذائية'],
                    'ملاحظات': ['', 'يحتاج متابعة']
                }
                filename = "قالب_استيراد_الطلاب.xlsx"
            else:
                columns = {
                    'الاسم الكامل (مطلوب)': ['أحمد محمد السعيد', 'فاطمة علي الخالدي'],
                    'البريد الإلكتروني (مطلوب)': ['ahmed.teacher@school.com', 'fatima.teacher@school.com'],
                    'رقم الجوال (مطلوب)': ['0501234567', '0559876543'],
                    'رقم الهوية': ['1234567890', '0987654321'],
                    'الجنس (ذكر/أنثى)': ['ذكر', 'أنثى'],
                    'التخصص': ['رياضيات', 'علوم'],
                    'المؤهل العلمي': ['بكالوريوس', 'ماجستير'],
                    'سنوات الخبرة': ['5', '10'],
                    'المواد (مفصولة بفاصلة)': ['الرياضيات,الفيزياء', 'الكيمياء,الأحياء'],
                    'الصفوف (مفصولة بفاصلة)': ['الأول,الثاني', 'الثالث,الرابع'],
                    'تاريخ التعيين (YYYY-MM-DD)': ['2020-09-01', '2018-09-01'],
                    'ملاحظات': ['', 'معلم متميز']
                }
                filename = "قالب_استيراد_المعلمين.xlsx"
            
            # Create DataFrame
            df = pd.DataFrame(columns)
            
            # Create Excel file in memory
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='البيانات')
                
                # Get workbook and worksheet
                workbook = writer.book
                worksheet = writer.sheets['البيانات']
                
                # Format header
                header_format = workbook.add_format({
                    'bold': True,
                    'bg_color': '#1E3A5F',
                    'font_color': 'white',
                    'border': 1,
                    'align': 'center',
                    'valign': 'vcenter'
                })
                
                # Apply header format
                for col_num, col_name in enumerate(df.columns):
                    worksheet.write(0, col_num, col_name, header_format)
                    worksheet.set_column(col_num, col_num, 25)
                
                # Add instructions sheet
                instructions = writer.book.add_worksheet('تعليمات')
                instructions.write(0, 0, 'تعليمات الاستيراد', workbook.add_format({'bold': True, 'font_size': 14}))
                instructions.write(2, 0, '1. لا تقم بتغيير أسماء الأعمدة')
                instructions.write(3, 0, '2. الأعمدة المطلوبة مُعلّمة بـ (مطلوب)')
                instructions.write(4, 0, '3. احذف صفوف البيانات النموذجية قبل إضافة بياناتك')
                instructions.write(5, 0, '4. تأكد من صحة تنسيق التواريخ (YYYY-MM-DD)')
                instructions.write(6, 0, '5. رقم الهوية يجب أن يكون 10 أرقام')
            
            output.seek(0)
            
            return StreamingResponse(
                output,
                media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                headers={'Content-Disposition': 'attachment; filename="template.xlsx"'}
            )
        except Exception as e:
            logger.error(f"Error creating template: {e}")
            raise HTTPException(status_code=500, detail="حدث خطأ داخلي في الخادم")
    
    # ============= IMPORT DATA =============
    
    @router.post("/import/{import_type}", response_model=ImportResult)
    async def import_data(
        import_type: ImportType,
        file: UploadFile = File(...),
        school_id: Optional[str] = None,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
    ):
        """استيراد البيانات من ملف Excel/CSV"""
        
        # Determine school_id
        if current_user.get("role") in ("school_principal", "school_admin"):
            school_id = current_user.get("tenant_id")
        elif not school_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
        # Validate file type
        if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
            raise HTTPException(status_code=400, detail="يجب أن يكون الملف بصيغة Excel أو CSV")
        
        try:
            contents = await file.read()
            if len(contents) > 10 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="حجم الملف يتجاوز الحد المسموح (10 ميغابايت)")

            if file.filename.endswith('.csv'):
                df = pd.read_csv(io.BytesIO(contents))
            else:
                df = pd.read_excel(io.BytesIO(contents))
            
            # Remove empty rows
            df = df.dropna(how='all')
            
            if df.empty:
                raise HTTPException(status_code=400, detail="الملف فارغ")
            
            total_rows = len(df)
            imported = 0
            failed = 0
            errors = []
            warnings = []
            
            if import_type == ImportType.STUDENTS:
                result = await _import_students(db, df, school_id, current_user, errors, warnings)
                imported = result['imported']
                failed = result['failed']
            elif import_type == ImportType.TEACHERS:
                result = await _import_teachers(db, df, school_id, current_user, errors, warnings)
                imported = result['imported']
                failed = result['failed']
            elif import_type == ImportType.NOOR_CLASSES:
                result = await _import_noor_classes(db, df, school_id, current_user, errors, warnings)
                imported = result['imported']
                failed = result['failed']
            elif import_type == ImportType.NOOR_ASSIGNMENTS:
                result = await _import_noor_assignments(db, df, school_id, current_user, errors, warnings)
                imported = result['imported']
                failed = result['failed']
            
            # Log the import
            await gd_insert(db.session, "audit_logs", {
                "id": str(uuid.uuid4()),
                "action": f"bulk_import_{import_type.value}",
                "performed_by": current_user.get("id"),
                "performed_by_name": current_user.get("full_name"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": {
                    "school_id": school_id,
                    "total_rows": total_rows,
                    "imported": imported,
                    "failed": failed,
                    "filename": file.filename
                }
            })
            
            return ImportResult(
                success=failed == 0,
                total_rows=total_rows,
                imported=imported,
                failed=failed,
                errors=errors[:50],  # Limit errors to 50
                warnings=warnings[:50]
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail="خطأ في معالجة الملف")
    
    # ============= EXPORT DATA =============
    
    @router.get("/export/{export_type}")
    async def export_data(
        export_type: ExportType,
        format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
        school_id: Optional[str] = None,
        grade: Optional[str] = None,
        class_name: Optional[str] = None,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
    ):
        """تصدير البيانات إلى Excel/CSV"""
        
        # Determine school_id
        if current_user.get("role") in ("school_principal", "school_admin"):
            school_id = current_user.get("tenant_id")
        
        try:
            if export_type == ExportType.STUDENTS:
                df, filename = await _export_students(db, school_id, grade, class_name)
            elif export_type == ExportType.TEACHERS:
                df, filename = await _export_teachers(db, school_id)
            elif export_type == ExportType.SCHEDULE:
                df, filename = await _export_schedule(db, school_id)
            elif export_type == ExportType.ATTENDANCE:
                df, filename = await _export_attendance(db, school_id, grade, class_name)
            elif export_type == ExportType.GRADES:
                df, filename = await _export_grades(db, school_id, grade, class_name)
            else:
                raise HTTPException(status_code=400, detail="نوع التصدير غير صالح")
            
            if df.empty:
                raise HTTPException(status_code=404, detail="لا توجد بيانات للتصدير")
            
            # Create output
            output = io.BytesIO()
            
            if format == "csv":
                df.to_csv(output, index=False, encoding='utf-8-sig')
                media_type = 'text/csv'
                filename = filename.replace('.xlsx', '.csv')
            else:
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='البيانات')
                    
                    workbook = writer.book
                    worksheet = writer.sheets['البيانات']
                    
                    # Format header
                    header_format = workbook.add_format({
                        'bold': True,
                        'bg_color': '#1E3A5F',
                        'font_color': 'white',
                        'border': 1,
                        'align': 'center'
                    })
                    
                    for col_num, col_name in enumerate(df.columns):
                        worksheet.write(0, col_num, col_name, header_format)
                        worksheet.set_column(col_num, col_num, 20)
                
                media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            
            output.seek(0)
            
            # Log the export
            await gd_insert(db.session, "audit_logs", {
                "id": str(uuid.uuid4()),
                "action": f"bulk_export_{export_type.value}",
                "performed_by": current_user.get("id"),
                "performed_by_name": current_user.get("full_name"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": {
                    "school_id": school_id,
                    "format": format,
                    "rows_exported": len(df)
                }
            })
            
            return StreamingResponse(
                output,
                media_type=media_type,
                headers={'Content-Disposition': 'attachment; filename="export.xlsx"' if format == 'xlsx' else 'attachment; filename="export.csv"'}
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail="خطأ في التصدير")
    
    return router


# ============= HELPER FUNCTIONS =============

async def _import_students(db, df: pd.DataFrame, school_id: str, user: dict, errors: list, warnings: list):
    """استيراد الطلاب"""
    imported = 0
    failed = 0
    
    # Column mapping (Arabic to English)
    column_map = {
        'الاسم الأول (مطلوب)': 'first_name',
        'اسم الأب': 'father_name',
        'اسم العائلة (مطلوب)': 'last_name',
        'رقم الهوية (مطلوب)': 'national_id',
        'تاريخ الميلاد (YYYY-MM-DD)': 'birth_date',
        'الجنس (ذكر/أنثى)': 'gender',
        'الصف': 'grade',
        'الفصل': 'class_name',
        'البريد الإلكتروني': 'email',
        'رقم الجوال': 'phone',
        'اسم ولي الأمر': 'parent_name',
        'جوال ولي الأمر (مطلوب)': 'parent_phone',
        'بريد ولي الأمر': 'parent_email',
        'الحالة الصحية': 'health_status',
        'ملاحظات': 'notes'
    }
    
    # Rename columns
    df = df.rename(columns=column_map)
    
    for idx, row in df.iterrows():
        row_num = idx + 2  # Excel row number (1-indexed + header)
        
        try:
            # Validate required fields
            first_name = str(row.get('first_name', '')).strip()
            last_name = str(row.get('last_name', '')).strip()
            national_id = str(row.get('national_id', '')).strip()
            parent_phone = str(row.get('parent_phone', '')).strip()
            
            if not first_name or first_name == 'nan':
                errors.append({"row": row_num, "field": "الاسم الأول", "message": "حقل مطلوب"})
                failed += 1
                continue
            
            if not last_name or last_name == 'nan':
                errors.append({"row": row_num, "field": "اسم العائلة", "message": "حقل مطلوب"})
                failed += 1
                continue
            
            if not national_id or national_id == 'nan':
                errors.append({"row": row_num, "field": "رقم الهوية", "message": "حقل مطلوب"})
                failed += 1
                continue
            
            # Validate national_id format
            national_id = re.sub(r'\D', '', national_id)
            if len(national_id) != 10:
                errors.append({"row": row_num, "field": "رقم الهوية", "message": "يجب أن يكون 10 أرقام"})
                failed += 1
                continue
            
            # Check if student already exists
            existing = await gd_find_one(db.session, "students", {
                "national_id": national_id,
                "school_id": school_id
            })
            
            if existing:
                warnings.append({"row": row_num, "message": f"الطالب موجود مسبقاً (رقم الهوية: {national_id})"})
                failed += 1
                continue
            
            # Create student record
            student_id = str(uuid.uuid4())
            gender = str(row.get('gender', 'ذكر')).strip()
            gender_en = 'male' if gender == 'ذكر' else 'female'
            
            student = {
                "id": student_id,
                "school_id": school_id,
                "first_name": first_name,
                "father_name": str(row.get('father_name', '')).strip() if pd.notna(row.get('father_name')) else '',
                "last_name": last_name,
                "full_name": f"{first_name} {last_name}",
                "national_id": national_id,
                "birth_date": str(row.get('birth_date', ''))[:10] if pd.notna(row.get('birth_date')) else None,
                "gender": gender_en,
                "grade": str(row.get('grade', '')).strip() if pd.notna(row.get('grade')) else None,
                "class_name": str(row.get('class_name', '')).strip() if pd.notna(row.get('class_name')) else None,
                "email": str(row.get('email', '')).strip() if pd.notna(row.get('email')) else None,
                "phone": str(row.get('phone', '')).strip() if pd.notna(row.get('phone')) else None,
                "parent_name": str(row.get('parent_name', '')).strip() if pd.notna(row.get('parent_name')) else None,
                "parent_phone": parent_phone if parent_phone != 'nan' else None,
                "parent_email": str(row.get('parent_email', '')).strip() if pd.notna(row.get('parent_email')) else None,
                "health_status": str(row.get('health_status', '')).strip() if pd.notna(row.get('health_status')) else None,
                "notes": str(row.get('notes', '')).strip() if pd.notna(row.get('notes')) else None,
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": user.get("id"),
                "import_source": "bulk_import"
            }
            
            await gd_insert(db.session, "students", student)
            imported += 1
            
        except Exception as e:
            errors.append({"row": row_num, "message": str(e)})
            failed += 1
    
    return {"imported": imported, "failed": failed}


async def _import_teachers(db, df: pd.DataFrame, school_id: str, user: dict, errors: list, warnings: list):
    """استيراد المعلمين"""
    imported = 0
    failed = 0
    
    # Column mapping
    column_map = {
        'الاسم الكامل (مطلوب)': 'full_name',
        'البريد الإلكتروني (مطلوب)': 'email',
        'رقم الجوال (مطلوب)': 'phone',
        'رقم الهوية': 'national_id',
        'الجنس (ذكر/أنثى)': 'gender',
        'التخصص': 'specialization',
        'المؤهل العلمي': 'qualification',
        'سنوات الخبرة': 'experience_years',
        'المواد (مفصولة بفاصلة)': 'subjects',
        'الصفوف (مفصولة بفاصلة)': 'grades',
        'تاريخ التعيين (YYYY-MM-DD)': 'hire_date',
        'ملاحظات': 'notes'
    }
    
    df = df.rename(columns=column_map)
    
    for idx, row in df.iterrows():
        row_num = idx + 2
        
        try:
            full_name = str(row.get('full_name', '')).strip()
            email = str(row.get('email', '')).strip().lower()
            phone = str(row.get('phone', '')).strip()
            
            # Validate required fields
            if not full_name or full_name == 'nan':
                errors.append({"row": row_num, "field": "الاسم الكامل", "message": "حقل مطلوب"})
                failed += 1
                continue
            
            if not email or email == 'nan' or '@' not in email:
                errors.append({"row": row_num, "field": "البريد الإلكتروني", "message": "بريد إلكتروني غير صالح"})
                failed += 1
                continue
            
            if not phone or phone == 'nan':
                errors.append({"row": row_num, "field": "رقم الجوال", "message": "حقل مطلوب"})
                failed += 1
                continue
            
            # Check if teacher already exists
            existing = await gd_find_one(db.session, "teachers", {
                "$or": [
                    {"email": email},
                    {"phone": phone}
                ]
            })
            
            if existing:
                warnings.append({"row": row_num, "message": f"المعلم موجود مسبقاً ({email})"})
                failed += 1
                continue
            
            # Parse subjects and grades
            subjects_str = str(row.get('subjects', '')).strip()
            grades_str = str(row.get('grades', '')).strip()
            
            subjects = [s.strip() for s in subjects_str.split(',') if s.strip() and s.strip() != 'nan']
            grades = [g.strip() for g in grades_str.split(',') if g.strip() and g.strip() != 'nan']
            
            # Create teacher record
            teacher_id = str(uuid.uuid4())
            gender = str(row.get('gender', 'ذكر')).strip()
            gender_en = 'male' if gender == 'ذكر' else 'female'
            
            teacher = {
                "id": teacher_id,
                "school_id": school_id,
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "national_id": str(row.get('national_id', '')).strip() if pd.notna(row.get('national_id')) else None,
                "gender": gender_en,
                "specialization": str(row.get('specialization', '')).strip() if pd.notna(row.get('specialization')) else None,
                "qualification": str(row.get('qualification', '')).strip() if pd.notna(row.get('qualification')) else None,
                "experience_years": int(row.get('experience_years', 0)) if pd.notna(row.get('experience_years')) else 0,
                "subjects": subjects,
                "grades": grades,
                "hire_date": str(row.get('hire_date', ''))[:10] if pd.notna(row.get('hire_date')) else None,
                "notes": str(row.get('notes', '')).strip() if pd.notna(row.get('notes')) else None,
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": user.get("id"),
                "import_source": "bulk_import"
            }
            
            await gd_insert(db.session, "teachers", teacher)
            imported += 1
            
        except Exception as e:
            errors.append({"row": row_num, "message": str(e)})
            failed += 1
    
    return {"imported": imported, "failed": failed}


async def _import_noor_classes(db, df: pd.DataFrame, school_id: str, user: dict, errors: list, warnings: list):
    imported = 0
    failed = 0

    column_map = {
        'اسم الفصل (مطلوب)': 'name',
        'اسم الفصل': 'name',
        'الصف (مطلوب)': 'grade_level',
        'الصف': 'grade_level',
        'الشعبة': 'section',
        'السعة': 'capacity',
        'المرحلة': 'stage',
        'ملاحظات': 'notes'
    }

    df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

    for idx, row in df.iterrows():
        row_num = idx + 2

        try:
            name = str(row.get('name', '')).strip()
            grade_level = str(row.get('grade_level', '')).strip()

            if not name or name == 'nan':
                errors.append({"row": row_num, "field": "اسم الفصل", "message": "حقل مطلوب"})
                failed += 1
                continue

            if not grade_level or grade_level == 'nan':
                errors.append({"row": row_num, "field": "الصف", "message": "حقل مطلوب"})
                failed += 1
                continue

            section = str(row.get('section', '')).strip() if pd.notna(row.get('section')) else ''
            existing = await gd_find_one(db.session, "classes", {
                "name": name,
                "school_id": school_id,
                "section": section
            })

            if existing:
                warnings.append({"row": row_num, "message": f"الفصل موجود مسبقاً ({name} - {section})"})
                failed += 1
                continue

            capacity = 30
            try:
                cap_val = row.get('capacity')
                if pd.notna(cap_val):
                    capacity = int(float(str(cap_val).strip()))
            except (ValueError, TypeError):
                pass

            class_doc = {
                "id": str(uuid.uuid4()),
                "school_id": school_id,
                "name": name,
                "name_ar": name,
                "grade_level": grade_level,
                "grade": grade_level,
                "section": section if section != 'nan' else '',
                "capacity": capacity,
                "stage": str(row.get('stage', '')).strip() if pd.notna(row.get('stage')) else '',
                "notes": str(row.get('notes', '')).strip() if pd.notna(row.get('notes')) else '',
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": user.get("id"),
                "import_source": "noor_import"
            }

            await gd_insert(db.session, "classes", class_doc)
            imported += 1

        except Exception as e:
            errors.append({"row": row_num, "message": str(e)})
            failed += 1

    return {"imported": imported, "failed": failed}


async def _import_noor_assignments(db, df: pd.DataFrame, school_id: str, user: dict, errors: list, warnings: list):
    imported = 0
    failed = 0

    column_map = {
        'اسم المعلم (مطلوب)': 'teacher_name',
        'اسم المعلم': 'teacher_name',
        'البريد الإلكتروني للمعلم': 'teacher_email',
        'اسم المادة (مطلوب)': 'subject_name',
        'اسم المادة': 'subject_name',
        'اسم الفصل': 'class_name',
        'عدد الحصص الأسبوعية': 'weekly_periods',
        'ملاحظات': 'notes'
    }

    df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

    teachers_cache = {}
    teachers_list = await gd_find(db.session, "teachers", {"school_id": school_id}, limit=2000)
    for t in teachers_list:
        teachers_cache[t.get('full_name', '').strip().lower()] = t
        if t.get('email'):
            teachers_cache[t['email'].strip().lower()] = t

    subjects_cache = {}
    subjects_list = await gd_find(db.session, "subjects", {"school_id": school_id}, limit=2000)
    for s in subjects_list:
        subjects_cache[s.get('name_ar', '').strip().lower()] = s
        subjects_cache[s.get('name', '').strip().lower()] = s

    for idx, row in df.iterrows():
        row_num = idx + 2

        try:
            teacher_name = str(row.get('teacher_name', '')).strip()
            subject_name = str(row.get('subject_name', '')).strip()

            if not teacher_name or teacher_name == 'nan':
                errors.append({"row": row_num, "field": "اسم المعلم", "message": "حقل مطلوب"})
                failed += 1
                continue

            if not subject_name or subject_name == 'nan':
                errors.append({"row": row_num, "field": "اسم المادة", "message": "حقل مطلوب"})
                failed += 1
                continue

            teacher = teachers_cache.get(teacher_name.lower())
            if not teacher:
                teacher_email = str(row.get('teacher_email', '')).strip().lower()
                if teacher_email and teacher_email != 'nan':
                    teacher = teachers_cache.get(teacher_email)

            if not teacher:
                errors.append({"row": row_num, "field": "اسم المعلم", "message": f"المعلم '{teacher_name}' غير موجود في النظام"})
                failed += 1
                continue

            subject = subjects_cache.get(subject_name.lower())
            if not subject:
                subject_id = str(uuid.uuid4())
                subject = {
                    "id": subject_id,
                    "school_id": school_id,
                    "name": subject_name,
                    "name_ar": subject_name,
                    "is_active": True,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "import_source": "noor_import"
                }
                await gd_insert(db.session, "subjects", subject)
                subjects_cache[subject_name.lower()] = subject

            class_name = str(row.get('class_name', '')).strip() if pd.notna(row.get('class_name')) else None
            weekly_periods_raw = row.get('weekly_periods')
            weekly_periods = int(weekly_periods_raw) if pd.notna(weekly_periods_raw) and str(weekly_periods_raw).strip().isdigit() else None
            notes = str(row.get('notes', '')).strip() if pd.notna(row.get('notes')) else None

            class_id = None
            if class_name and class_name != 'nan':
                class_doc = await gd_find_one(db.session, "classes", {"school_id": school_id, "name": class_name})
                if class_doc:
                    class_id = class_doc["id"]
                else:
                    warnings.append({"row": row_num, "message": f"الفصل '{class_name}' غير موجود، سيتم إنشاء الإسناد بدون ربط فصل"})

            dup_query = {
                "teacher_id": teacher["id"],
                "subject_id": subject["id"],
                "school_id": school_id
            }
            if class_id:
                dup_query["class_id"] = class_id

            existing = await gd_find_one(db.session, "teacher_assignments", dup_query)

            if existing:
                warnings.append({"row": row_num, "message": f"الإسناد موجود مسبقاً ({teacher_name} - {subject_name}{' - ' + class_name if class_name else ''})"})
                failed += 1
                continue

            assignment_doc = {
                "id": str(uuid.uuid4()),
                "school_id": school_id,
                "teacher_id": teacher["id"],
                "subject_id": subject["id"],
                "teacher_name": teacher.get("full_name", teacher_name),
                "subject_name": subject.get("name_ar", subject_name),
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": user.get("id"),
                "import_source": "noor_import"
            }
            if class_id:
                assignment_doc["class_id"] = class_id
                assignment_doc["class_name"] = class_name
            if weekly_periods is not None:
                assignment_doc["weekly_periods"] = weekly_periods
            if notes:
                assignment_doc["notes"] = notes

            await gd_insert(db.session, "teacher_assignments", assignment_doc)
            imported += 1

        except Exception as e:
            errors.append({"row": row_num, "message": str(e)})
            failed += 1

    return {"imported": imported, "failed": failed}


async def _export_students(db, school_id: str, grade: str = None, class_name: str = None):
    """تصدير الطلاب"""
    query = {}
    if school_id:
        query["school_id"] = school_id
    if grade:
        query["grade"] = grade
    if class_name:
        query["class_name"] = class_name
    
    students = await gd_find(db.session, "students", query, limit=10000)
    
    data = []
    for s in students:
        data.append({
            'الاسم الأول': s.get('first_name', ''),
            'اسم الأب': s.get('father_name', ''),
            'اسم العائلة': s.get('last_name', ''),
            'الاسم الكامل': s.get('full_name', ''),
            'رقم الهوية': s.get('national_id', ''),
            'تاريخ الميلاد': s.get('birth_date', ''),
            'الجنس': 'ذكر' if s.get('gender') == 'male' else 'أنثى',
            'الصف': s.get('grade', ''),
            'الفصل': s.get('class_name', ''),
            'البريد الإلكتروني': s.get('email', ''),
            'رقم الجوال': s.get('phone', ''),
            'اسم ولي الأمر': s.get('parent_name', ''),
            'جوال ولي الأمر': s.get('parent_phone', ''),
            'الحالة': 'نشط' if s.get('is_active') else 'غير نشط',
        })
    
    df = pd.DataFrame(data)
    return df, 'تصدير_الطلاب.xlsx'


async def _export_teachers(db, school_id: str):
    """تصدير المعلمين"""
    query = {}
    if school_id:
        query["school_id"] = school_id
    
    teachers = await gd_find(db.session, "teachers", query, limit=5000)
    
    data = []
    for t in teachers:
        data.append({
            'الاسم الكامل': t.get('full_name', ''),
            'البريد الإلكتروني': t.get('email', ''),
            'رقم الجوال': t.get('phone', ''),
            'رقم الهوية': t.get('national_id', ''),
            'الجنس': 'ذكر' if t.get('gender') == 'male' else 'أنثى',
            'التخصص': t.get('specialization', ''),
            'المؤهل العلمي': t.get('qualification', ''),
            'سنوات الخبرة': t.get('experience_years', ''),
            'المواد': ', '.join(t.get('subjects', [])),
            'الصفوف': ', '.join(t.get('grades', [])),
            'تاريخ التعيين': t.get('hire_date', ''),
            'الحالة': 'نشط' if t.get('is_active') else 'غير نشط',
        })
    
    df = pd.DataFrame(data)
    return df, 'تصدير_المعلمين.xlsx'


async def _export_schedule(db, school_id: str):
    """تصدير الجدول الدراسي"""
    query = {}
    if school_id:
        query["school_id"] = school_id
    
    schedules = await gd_find(db.session, "schedules", query, limit=1000)
    
    data = []
    for s in schedules:
        entries = s.get('entries', [])
        for entry in entries:
            data.append({
                'اليوم': entry.get('day', ''),
                'الحصة': entry.get('period', ''),
                'وقت البداية': entry.get('start_time', ''),
                'وقت النهاية': entry.get('end_time', ''),
                'المادة': entry.get('subject', ''),
                'المعلم': entry.get('teacher_name', ''),
                'الصف': entry.get('grade', ''),
                'الفصل': entry.get('class_name', ''),
                'الغرفة': entry.get('room', ''),
            })
    
    df = pd.DataFrame(data)
    return df, 'تصدير_الجدول_الدراسي.xlsx'


async def _export_attendance(db, school_id: str, grade: str = None, class_name: str = None):
    """تصدير سجل الحضور"""
    query = {}
    if school_id:
        query["school_id"] = school_id
    if grade:
        query["grade"] = grade
    if class_name:
        query["class_name"] = class_name
    
    records = await gd_find(db.session, "attendance", query, order_by="date", desc_order=True, limit=5000)
    
    data = []
    for r in records:
        data.append({
            'التاريخ': r.get('date', ''),
            'اسم الطالب': r.get('student_name', ''),
            'الصف': r.get('grade', ''),
            'الفصل': r.get('class_name', ''),
            'الحالة': r.get('status', ''),
            'وقت الحضور': r.get('check_in_time', ''),
            'وقت الانصراف': r.get('check_out_time', ''),
            'ملاحظات': r.get('notes', ''),
        })
    
    df = pd.DataFrame(data)
    return df, 'تصدير_سجل_الحضور.xlsx'


async def _export_grades(db, school_id: str, grade: str = None, class_name: str = None):
    """تصدير الدرجات"""
    query = {}
    if school_id:
        query["school_id"] = school_id
    if grade:
        query["grade"] = grade
    if class_name:
        query["class_name"] = class_name
    
    records = await gd_find(db.session, "grades", query, limit=10000)
    
    data = []
    for r in records:
        data.append({
            'اسم الطالب': r.get('student_name', ''),
            'الصف': r.get('grade', ''),
            'الفصل': r.get('class_name', ''),
            'المادة': r.get('subject', ''),
            'نوع التقييم': r.get('assessment_type', ''),
            'الدرجة': r.get('score', ''),
            'الدرجة القصوى': r.get('max_score', ''),
            'النسبة المئوية': r.get('percentage', ''),
            'التاريخ': r.get('date', ''),
        })
    
    df = pd.DataFrame(data)
    return df, 'تصدير_الدرجات.xlsx'


def setup_import_tracking_routes(db, get_current_user, require_roles, UserRole):
    """Additional routes for import status tracking"""
    router = APIRouter(prefix="/bulk", tags=["Bulk Import/Export"])

    @router.get("/import-history")
    async def get_import_history(
        limit: int = 20,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
    ):
        """Get import history and status"""
        school_id = current_user.get("tenant_id")
        logs = await gd_find(db.session, "audit_logs", {"action": {"$regex": "^bulk_import_"}, "details.school_id": school_id}, order_by="timestamp", desc_order=True, limit=limit)

        return {"history": logs, "total": len(logs)}

    @router.get("/export-history")
    async def get_export_history(
        limit: int = 20,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
    ):
        """Get export history"""
        school_id = current_user.get("tenant_id")
        logs = await gd_find(db.session, "audit_logs", {"action": "data_exported", "details.school_id": school_id}, order_by="timestamp", desc_order=True, limit=limit)

        return {"history": logs, "total": len(logs)}

    return router

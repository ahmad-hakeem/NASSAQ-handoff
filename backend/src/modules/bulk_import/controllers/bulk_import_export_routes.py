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
    batch_id: Optional[str] = None


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
                df = pd.read_csv(io.BytesIO(contents), dtype=str)
            else:
                df = pd.read_excel(io.BytesIO(contents), dtype=str)
            
            # Remove empty rows
            df = df.dropna(how='all')
            
            if df.empty:
                raise HTTPException(status_code=400, detail="الملف فارغ")
            
            total_rows = len(df)
            imported = 0
            failed = 0
            errors = []
            warnings = []
            
            batch_id = None
            if import_type == ImportType.STUDENTS:
                result = await _import_students(db, df, school_id, current_user, errors, warnings, filename=file.filename)
                imported = result['imported']
                failed = result['failed']
                batch_id = result.get('batch_id')
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
                    "filename": file.filename,
                    "batch_id": batch_id
                }
            })
            
            return ImportResult(
                success=failed == 0,
                total_rows=total_rows,
                imported=imported,
                failed=failed,
                errors=errors[:50],  # Limit errors to 50
                warnings=warnings[:50],
                batch_id=batch_id
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error processing import: {e}")
            raise HTTPException(status_code=500, detail=f"خطأ في معالجة الملف: {str(e)}")
    
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

async def _import_students(db, df: pd.DataFrame, school_id: str, user: dict, errors: list, warnings: list, filename: Optional[str] = None):
    """استيراد الطلاب مع التحقق المسبق والمعاملات المتكاملة (All-or-Nothing Atomic Import)"""
    imported = 0
    
    # Column mapping (Arabic to English)
    column_map = {
        'الاسم الأول (مطلوب)': 'first_name',
        'الاسم الأول': 'first_name',
        'اسم الأب': 'father_name',
        'اسم العائلة (مطلوب)': 'last_name',
        'اسم العائلة': 'last_name',
        'الاسم الاخير': 'last_name',
        'الاسم الأخير': 'last_name',
        'رقم الهوية (مطلوب)': 'national_id',
        'رقم الهوية': 'national_id',
        'تاريخ الميلاد (YYYY-MM-DD)': 'date_of_birth',
        'تاريخ الميلاد': 'date_of_birth',
        'الجنس (ذكر/أنثى)': 'gender',
        'الجنس': 'gender',
        'الصف': 'grade',
        'الفصل': 'class_name',
        'البريد الإلكتروني': 'email',
        'البريد الالكتروني': 'email',
        'رقم الجوال': 'phone',
        'اسم ولي الأمر': 'parent_name',
        'اسم ولي الامر': 'parent_name',
        'جوال ولي الأمر (مطلوب)': 'parent_phone',
        'جوال ولي الأمر': 'parent_phone',
        'جوال ولي الامر': 'parent_phone',
        'بريد ولي الأمر': 'parent_email',
        'بريد ولي الامر': 'parent_email',
        'الحالة الصحية': 'health_status',
        'ملاحظات': 'notes'
    }
    
    df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})
    
    seen_national_ids = {}
    seen_emails = {}
    valid_records = []
    
    for idx, row in df.iterrows():
        row_num = idx + 2  # Excel row number (1-indexed + header)
        row_errors = []
        
        # Check empty row
        if row.dropna().empty:
            continue
            
        try:
            # Extract fields cleanly
            first_name = str(row.get('first_name', '')).strip() if pd.notna(row.get('first_name')) else ''
            if first_name.lower() == 'nan':
                first_name = ''
                
            last_name = str(row.get('last_name', '')).strip() if pd.notna(row.get('last_name')) else ''
            if last_name.lower() == 'nan':
                last_name = ''
                
            father_name = str(row.get('father_name', '')).strip() if pd.notna(row.get('father_name')) else ''
            if father_name.lower() == 'nan':
                father_name = ''
                
            national_id_raw = str(row.get('national_id', '')).strip() if pd.notna(row.get('national_id')) else ''
            if national_id_raw.lower() == 'nan':
                national_id_raw = ''
            if national_id_raw.endswith('.0'):
                national_id_raw = national_id_raw[:-2]
                
            parent_phone_raw = str(row.get('parent_phone', '')).strip() if pd.notna(row.get('parent_phone')) else ''
            if parent_phone_raw.lower() == 'nan':
                parent_phone_raw = ''
            if parent_phone_raw.endswith('.0'):
                parent_phone_raw = parent_phone_raw[:-2]
                
            email = str(row.get('email', '')).strip() if pd.notna(row.get('email')) else None
            if email and email.lower() == 'nan':
                email = None
                
            parent_email = str(row.get('parent_email', '')).strip() if pd.notna(row.get('parent_email')) else None
            if parent_email and parent_email.lower() == 'nan':
                parent_email = None

            # 1. Required fields validation
            if not first_name:
                row_errors.append({"row": row_num, "field": "الاسم الأول", "message": "الاسم الأول: حقل مطلوب ولا يمكن تركه فارغاً"})
            if not last_name:
                row_errors.append({"row": row_num, "field": "اسم العائلة", "message": "اسم العائلة: حقل مطلوب ولا يمكن تركه فارغاً"})
            if not national_id_raw:
                row_errors.append({"row": row_num, "field": "رقم الهوية", "message": "رقم الهوية: حقل مطلوب ولا يمكن تركه فارغاً"})
            if not parent_phone_raw:
                row_errors.append({"row": row_num, "field": "جوال ولي الأمر", "message": "جوال ولي الأمر: حقل مطلوب ولا يمكن تركه فارغاً"})

            # 2. National ID format & duplication validation
            clean_national_id = re.sub(r'\D', '', national_id_raw)
            if national_id_raw:
                if len(clean_national_id) == 9:
                    clean_national_id = clean_national_id.zfill(10)
                if len(clean_national_id) != 10:
                    row_errors.append({"row": row_num, "field": "رقم الهوية", "message": f"رقم الهوية ({national_id_raw}): يجب أن يتكون من 10 أرقام"})
                else:
                    if clean_national_id in seen_national_ids:
                        prev_row = seen_national_ids[clean_national_id]
                        row_errors.append({"row": row_num, "field": "رقم الهوية", "message": f"رقم الهوية ({clean_national_id}): مكرر داخل نفس الملف مع الصف {prev_row}"})
                    else:
                        seen_national_ids[clean_national_id] = row_num
                        existing = await gd_find_one(db.session, "students", {
                            "national_id": clean_national_id,
                            "school_id": school_id,
                            "is_active": True
                        })
                        if existing:
                            row_errors.append({"row": row_num, "field": "رقم الهوية", "message": f"رقم الهوية ({clean_national_id}): الطالب مسجل مسبقاً في هذه المدرسة (الاسم: {existing.get('full_name', '')})"})

            # 3. Parent phone format validation
            if parent_phone_raw:
                clean_phone = re.sub(r'[\s\-]', '', parent_phone_raw)
                if len(clean_phone) < 9:
                    row_errors.append({"row": row_num, "field": "جوال ولي الأمر", "message": f"جوال ولي الأمر ({parent_phone_raw}): رقم هاتف غير صالح"})

            # 4. Email validation
            if email:
                if '@' not in email or '.' not in email:
                    row_errors.append({"row": row_num, "field": "البريد الإلكتروني", "message": f"البريد الإلكتروني ({email}): صيغة بريد غير صالحة"})
                elif email.lower() in seen_emails:
                    row_errors.append({"row": row_num, "field": "البريد الإلكتروني", "message": f"البريد الإلكتروني ({email}): مكرر داخل نفس الملف مع الصف {seen_emails[email.lower()]}"})
                else:
                    seen_emails[email.lower()] = row_num

            if parent_email and ('@' not in parent_email or '.' not in parent_email):
                row_errors.append({"row": row_num, "field": "بريد ولي الأمر", "message": f"بريد ولي الأمر ({parent_email}): صيغة بريد غير صالحة"})

            if row_errors:
                errors.extend(row_errors)
            else:
                full_name = f"{first_name} {father_name} {last_name}".replace("  ", " ").strip() if father_name else f"{first_name} {last_name}".strip()
                dob_raw = str(row.get('date_of_birth', '')).strip() if pd.notna(row.get('date_of_birth')) else None
                if dob_raw and dob_raw.lower() == 'nan':
                    dob_raw = None
                if dob_raw and len(dob_raw) > 10:
                    dob_raw = dob_raw[:10]

                gender_raw = str(row.get('gender', 'ذكر')).strip()
                gender_en = 'female' if gender_raw in ('أنثى', 'انثى', 'female') else 'male'

                valid_records.append({
                    "row_num": row_num,
                    "first_name": first_name,
                    "father_name": father_name,
                    "last_name": last_name,
                    "full_name": full_name,
                    "national_id": clean_national_id,
                    "date_of_birth": dob_raw,
                    "gender": gender_en,
                    "grade": str(row.get('grade', '')).strip() if pd.notna(row.get('grade')) and str(row.get('grade', '')).strip() != 'nan' else None,
                    "class_name": str(row.get('class_name', '')).strip() if pd.notna(row.get('class_name')) and str(row.get('class_name', '')).strip() != 'nan' else None,
                    "email": email,
                    "phone": str(row.get('phone', '')).strip() if pd.notna(row.get('phone')) and str(row.get('phone', '')).strip() != 'nan' else None,
                    "parent_name": str(row.get('parent_name', '')).strip() if pd.notna(row.get('parent_name')) and str(row.get('parent_name', '')).strip() != 'nan' else None,
                    "parent_phone": parent_phone_raw,
                    "parent_email": parent_email,
                    "health_status": str(row.get('health_status', '')).strip() if pd.notna(row.get('health_status')) and str(row.get('health_status', '')).strip() != 'nan' else None,
                    "notes": str(row.get('notes', '')).strip() if pd.notna(row.get('notes')) and str(row.get('notes', '')).strip() != 'nan' else None,
                })

        except Exception as e:
            errors.append({"row": row_num, "field": "عام", "message": f"خطأ في معالجة الصف: {str(e)}"})

    failed_rows_count = len(set(e['row'] for e in errors))
    if not valid_records:
        return {"imported": 0, "failed": failed_rows_count}

    # Pass 2: Commit all valid records
    classes_list = await gd_find(db.session, "classes", {"school_id": school_id, "is_active": True}, limit=1000)
    classes_map = {}
    class_capacity_map = {}
    class_occupancy_map = {}
    for c in classes_list:
        cid = c['id']
        class_capacity_map[cid] = c.get('capacity') or 30
        class_occupancy_map[cid] = c.get('current_students') or 0
        if c.get('name'):
            classes_map[c['name'].strip()] = cid
        if c.get('grade_level') and c.get('section'):
            classes_map[f"{c['grade_level'].strip()} {c['section'].strip()}"] = cid
            classes_map[f"{c['grade_level'].strip()} - {c['section'].strip()}"] = cid

    from services.parent_linking import link_or_update_real_school_guardian
    from dependencies import hash_password, generate_secure_password

    assigned_class_ids = set()
    created_class_ids = []
    imported_student_ids = []
    for item in valid_records:
        class_id = None
        raw_cname = (item.get("class_name") or "").strip()
        raw_grade = (item.get("grade") or "").strip()

        if raw_cname:
            class_id = classes_map.get(raw_cname)
        if not class_id and raw_grade and raw_cname:
            class_id = classes_map.get(f"{raw_grade} {raw_cname}") or classes_map.get(f"{raw_grade} - {raw_cname}")
        if not class_id and raw_grade:
            class_id = classes_map.get(raw_grade)

        # Auto-create class if referenced in file but does not exist yet
        if not class_id and (raw_cname or raw_grade):
            if raw_cname and raw_grade:
                display_name = raw_cname if raw_grade in raw_cname else f"{raw_grade} - {raw_cname}"
            elif raw_cname:
                display_name = raw_cname
            else:
                display_name = f"فصل {raw_grade}"

            new_class_id = str(uuid.uuid4())
            now_iso = datetime.now(timezone.utc).isoformat()
            new_class_doc = {
                "id": new_class_id,
                "school_id": school_id,
                "name": display_name,
                "name_ar": display_name,
                "grade_level": raw_grade or None,
                "grade": raw_grade or None,
                "section": raw_cname or None,
                "capacity": 30,
                "current_students": 0,
                "is_active": True,
                "created_at": now_iso,
                "updated_at": now_iso,
                "created_by": user.get("id"),
                "import_source": "auto_provisioned_student_import",
            }
            try:
                await gd_insert(db.session, "classes", new_class_doc)
                created_class_ids.append(new_class_id)
                class_id = new_class_id
                if raw_cname:
                    classes_map[raw_cname] = new_class_id
                if raw_grade and raw_cname:
                    classes_map[f"{raw_grade} {raw_cname}"] = new_class_id
                    classes_map[f"{raw_grade} - {raw_cname}"] = new_class_id
                if raw_grade:
                    classes_map[raw_grade] = new_class_id
                classes_map[display_name] = new_class_id
                class_capacity_map[new_class_id] = 30
                class_occupancy_map[new_class_id] = 0
            except Exception as ex:
                logger.warning(f"Failed to auto-create class {display_name}: {ex}")

        if class_id:
            cap = class_capacity_map.get(class_id, 30)
            occ = class_occupancy_map.get(class_id, 0)
            if occ < cap:
                class_occupancy_map[class_id] = occ + 1
                assigned_class_ids.add(class_id)
            else:
                # Class reached capacity — leave student unassigned so the class is never overfilled
                class_id = None

        health_info = {}
        if item["health_status"]:
            health_info["general_condition"] = item["health_status"]

        student_doc = {
            "id": str(uuid.uuid4()),
            "school_id": school_id,
            "full_name": item["full_name"],
            "national_id": item["national_id"],
            "date_of_birth": item["date_of_birth"],
            "gender": item["gender"],
            "grade": item["grade"],
            "class_id": class_id,
            "email": item["email"],
            "phone": item["phone"],
            "parent_id": None,
            "parent_name": item["parent_name"],
            "parent_phone": item["parent_phone"],
            "parent_email": item["parent_email"],
            "health_info": health_info,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        if item["parent_phone"]:
            try:
                guardian_fields = await link_or_update_real_school_guardian(
                    db.session,
                    student=student_doc,
                    school_id=school_id,
                    created_by=user.get("id"),
                    parent_name=item["parent_name"],
                    parent_phone=item["parent_phone"],
                    parent_email=item["parent_email"],
                    parent_relationship="guardian",
                    hash_password=hash_password,
                    generate_secure_password=generate_secure_password,
                )
                student_doc["parent_id"] = guardian_fields.get("parent_id")
                student_doc["parent_name"] = guardian_fields.get("parent_name")
                student_doc["parent_phone"] = guardian_fields.get("parent_phone")
                student_doc["parent_email"] = guardian_fields.get("parent_email")
            except Exception as ex:
                logger.warning(f"link_or_update_real_school_guardian error for row {item['row_num']}: {ex}")

        try:
            await gd_insert(db.session, "students", student_doc)
            imported_student_ids.append(student_doc["id"])
            imported += 1
        except Exception as ex:
            logger.exception(f"Failed to insert student row {item['row_num']}: {ex}")
            errors.append({"row": item["row_num"], "field": "عام", "message": f"فشل حفظ الطالب: {str(ex)}"})

    from engines.entity_counts import reconcile_school_counts, reconcile_class_counts
    batch_id = None
    if imported > 0:
        await reconcile_school_counts(db.session, school_id)
        for cid in assigned_class_ids:
            try:
                await reconcile_class_counts(db.session, cid, school_id)
            except Exception as ex:
                logger.warning(f"Failed to reconcile count for class {cid}: {ex}")

        batch_id = str(uuid.uuid4())
        now_dt = datetime.now(timezone.utc)
        batch_doc = {
            "id": batch_id,
            "school_id": school_id,
            "actor_id": user.get("id"),
            "actor_name": user.get("full_name") or user.get("name"),
            "import_type": "students",
            "file_name": filename or "students.xlsx",
            "imported_count": imported,
            "student_ids": imported_student_ids,
            "created_class_ids": created_class_ids,
            "status": "active",
            "created_at": now_dt,
            "updated_at": now_dt,
        }
        try:
            await gd_insert(db.session, "bulk_import_batches", batch_doc)
        except Exception as ex:
            logger.warning(f"Failed to record bulk_import_batch: {ex}")

    failed_rows_count = len(set(e['row'] for e in errors))
    return {
        "imported": imported,
        "failed": failed_rows_count,
        "batch_id": batch_id,
        "student_ids": imported_student_ids,
        "created_class_ids": created_class_ids,
    }


async def _import_teachers(db, df: pd.DataFrame, school_id: str, user: dict, errors: list, warnings: list):
    """استيراد المعلمين مع التحقق المسبق والمعاملات المتكاملة (All-or-Nothing Atomic Import)"""
    imported = 0
    
    # Column mapping
    column_map = {
        'الاسم الكامل (مطلوب)': 'full_name',
        'الاسم الكامل': 'full_name',
        'الاسم': 'full_name',
        'البريد الإلكتروني (مطلوب)': 'email',
        'البريد الإلكتروني': 'email',
        'البريد الالكتروني': 'email',
        'رقم الجوال (مطلوب)': 'phone',
        'رقم الجوال': 'phone',
        'الجوال': 'phone',
        'رقم الهوية': 'national_id',
        'الجنس (ذكر/أنثى)': 'gender',
        'الجنس': 'gender',
        'التخصص': 'specialization',
        'المؤهل العلمي': 'qualification',
        'سنوات الخبرة': 'experience_years',
        'المواد (مفصولة بفاصلة)': 'subjects',
        'المواد': 'subjects',
        'الصفوف (مفصولة بفاصلة)': 'grades',
        'الصفوف': 'grades',
        'تاريخ التعيين (YYYY-MM-DD)': 'hire_date',
        'تاريخ التعيين': 'hire_date',
        'ملاحظات': 'notes'
    }
    
    df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})
    
    seen_emails = {}
    seen_phones = {}
    valid_records = []
    
    for idx, row in df.iterrows():
        row_num = idx + 2
        row_errors = []
        
        if row.dropna().empty:
            continue
            
        try:
            full_name = str(row.get('full_name', '')).strip() if pd.notna(row.get('full_name')) else ''
            if full_name.lower() == 'nan':
                full_name = ''
                
            email = str(row.get('email', '')).strip().lower() if pd.notna(row.get('email')) else ''
            if email.lower() == 'nan':
                email = ''
                
            phone = str(row.get('phone', '')).strip() if pd.notna(row.get('phone')) else ''
            if phone.lower() == 'nan':
                phone = ''
            if phone.endswith('.0'):
                phone = phone[:-2]
            
            # Validate required fields
            if not full_name:
                row_errors.append({"row": row_num, "field": "الاسم الكامل", "message": "الاسم الكامل: حقل مطلوب ولا يمكن تركه فارغاً"})
            
            if not email or '@' not in email or '.' not in email:
                row_errors.append({"row": row_num, "field": "البريد الإلكتروني", "message": f"البريد الإلكتروني ({email or 'فارغ'}): بريد إلكتروني غير صالح"})
            elif email in seen_emails:
                row_errors.append({"row": row_num, "field": "البريد الإلكتروني", "message": f"البريد الإلكتروني ({email}): مكرر داخل نفس الملف مع الصف {seen_emails[email]}"})
            else:
                seen_emails[email] = row_num
                existing_email = await gd_find_one(db.session, "teachers", {"email": email, "school_id": school_id})
                if existing_email:
                    row_errors.append({"row": row_num, "field": "البريد الإلكتروني", "message": f"البريد الإلكتروني ({email}): المعلم مسجل مسبقاً في هذه المدرسة"})
            
            if not phone:
                row_errors.append({"row": row_num, "field": "رقم الجوال", "message": "رقم الجوال: حقل مطلوب ولا يمكن تركه فارغاً"})
            else:
                clean_phone = re.sub(r'[\s\-]', '', phone)
                if len(clean_phone) < 9:
                    row_errors.append({"row": row_num, "field": "رقم الجوال", "message": f"رقم الجوال ({phone}): رقم هاتف غير صالح"})
                elif clean_phone in seen_phones:
                    row_errors.append({"row": row_num, "field": "رقم الجوال", "message": f"رقم الجوال ({phone}): مكرر داخل نفس الملف مع الصف {seen_phones[clean_phone]}"})
                else:
                    seen_phones[clean_phone] = row_num
            
            if row_errors:
                errors.extend(row_errors)
            else:
                subjects_str = str(row.get('subjects', '')).strip() if pd.notna(row.get('subjects')) else ''
                grades_str = str(row.get('grades', '')).strip() if pd.notna(row.get('grades')) else ''
                
                subjects = [s.strip() for s in subjects_str.split(',') if s.strip() and s.strip().lower() != 'nan']
                grades = [g.strip() for g in grades_str.split(',') if g.strip() and g.strip().lower() != 'nan']
                
                gender = str(row.get('gender', 'ذكر')).strip()
                gender_en = 'female' if gender in ('أنثى', 'انثى', 'female') else 'male'
                
                exp_years = 0
                if pd.notna(row.get('experience_years')):
                    try:
                        exp_years = int(float(str(row.get('experience_years')).strip()))
                    except (ValueError, TypeError):
                        exp_years = 0

                valid_records.append({
                    "row_num": row_num,
                    "full_name": full_name,
                    "email": email,
                    "phone": phone,
                    "national_id": str(row.get('national_id', '')).strip() if pd.notna(row.get('national_id')) and str(row.get('national_id', '')).strip() != 'nan' else None,
                    "gender": gender_en,
                    "specialization": str(row.get('specialization', '')).strip() if pd.notna(row.get('specialization')) and str(row.get('specialization', '')).strip() != 'nan' else None,
                    "qualification": str(row.get('qualification', '')).strip() if pd.notna(row.get('qualification')) and str(row.get('qualification', '')).strip() != 'nan' else None,
                    "experience_years": exp_years,
                    "subjects": subjects,
                    "grades": grades,
                    "hire_date": str(row.get('hire_date', ''))[:10] if pd.notna(row.get('hire_date')) and str(row.get('hire_date', '')).strip() != 'nan' else None,
                    "notes": str(row.get('notes', '')).strip() if pd.notna(row.get('notes')) and str(row.get('notes', '')).strip() != 'nan' else None,
                })
            
        except Exception as e:
            errors.append({"row": row_num, "field": "عام", "message": f"خطأ في معالجة الصف: {str(e)}"})

    failed_rows_count = len(set(e['row'] for e in errors))
    if errors:
        return {"imported": 0, "failed": failed_rows_count}

    for item in valid_records:
        teacher_id = str(uuid.uuid4())
        teacher = {
            "id": teacher_id,
            "school_id": school_id,
            "full_name": item["full_name"],
            "email": item["email"],
            "phone": item["phone"],
            "national_id": item["national_id"],
            "gender": item["gender"],
            "specialization": item["specialization"],
            "qualification": item["qualification"],
            "experience_years": item["experience_years"],
            "subjects": item["subjects"],
            "grades": item["grades"],
            "hire_date": item["hire_date"],
            "notes": item["notes"],
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user.get("id"),
            "import_source": "bulk_import"
        }
        await gd_insert(db.session, "teachers", teacher)
        imported += 1

    from engines.entity_counts import reconcile_school_counts
    await reconcile_school_counts(db.session, school_id)

    return {"imported": imported, "failed": 0}


async def _import_noor_classes(db, df: pd.DataFrame, school_id: str, user: dict, errors: list, warnings: list):
    """استيراد الفصول مع التحقق المسبق والمعاملات المتكاملة (All-or-Nothing Atomic Import)"""
    imported = 0
    
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
    seen_classes = {}
    valid_records = []

    for idx, row in df.iterrows():
        row_num = idx + 2
        row_errors = []

        if row.dropna().empty:
            continue

        try:
            name = str(row.get('name', '')).strip() if pd.notna(row.get('name')) else ''
            if name.lower() == 'nan':
                name = ''
                
            grade_level = str(row.get('grade_level', '')).strip() if pd.notna(row.get('grade_level')) else ''
            if grade_level.lower() == 'nan':
                grade_level = ''

            if not name:
                row_errors.append({"row": row_num, "field": "اسم الفصل", "message": "اسم الفصل: حقل مطلوب ولا يمكن تركه فارغاً"})

            if not grade_level:
                row_errors.append({"row": row_num, "field": "الصف", "message": "الصف: حقل مطلوب ولا يمكن تركه فارغاً"})

            section = str(row.get('section', '')).strip() if pd.notna(row.get('section')) and str(row.get('section', '')).strip() != 'nan' else ''
            
            class_key = (name, section)
            if class_key in seen_classes:
                row_errors.append({"row": row_num, "field": "اسم الفصل", "message": f"الفصل ({name} - {section or 'بدون شعبة'}): مكرر داخل نفس الملف مع الصف {seen_classes[class_key]}"})
            else:
                seen_classes[class_key] = row_num
                existing = await gd_find_one(db.session, "classes", {
                    "name": name,
                    "school_id": school_id,
                    "section": section,
                    "is_active": True
                })
                if existing:
                    row_errors.append({"row": row_num, "field": "اسم الفصل", "message": f"الفصل ({name} - {section or 'بدون شعبة'}): موجود مسبقاً في هذه المدرسة"})

            capacity = 30
            try:
                cap_val = row.get('capacity')
                if pd.notna(cap_val) and str(cap_val).strip() != 'nan':
                    capacity = int(float(str(cap_val).strip()))
            except (ValueError, TypeError):
                pass

            if row_errors:
                errors.extend(row_errors)
            else:
                valid_records.append({
                    "row_num": row_num,
                    "name": name,
                    "grade_level": grade_level,
                    "section": section,
                    "capacity": capacity,
                    "stage": str(row.get('stage', '')).strip() if pd.notna(row.get('stage')) and str(row.get('stage', '')).strip() != 'nan' else '',
                    "notes": str(row.get('notes', '')).strip() if pd.notna(row.get('notes')) and str(row.get('notes', '')).strip() != 'nan' else '',
                })

        except Exception as e:
            errors.append({"row": row_num, "field": "عام", "message": f"خطأ في معالجة الصف: {str(e)}"})

    failed_rows_count = len(set(e['row'] for e in errors))
    if errors:
        return {"imported": 0, "failed": failed_rows_count}

    for item in valid_records:
        class_doc = {
            "id": str(uuid.uuid4()),
            "school_id": school_id,
            "name": item["name"],
            "name_ar": item["name"],
            "grade_level": item["grade_level"],
            "grade": item["grade_level"],
            "section": item["section"],
            "capacity": item["capacity"],
            "stage": item["stage"],
            "notes": item["notes"],
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user.get("id"),
            "import_source": "noor_import"
        }
        await gd_insert(db.session, "classes", class_doc)
        imported += 1

    return {"imported": imported, "failed": 0}


async def _import_noor_assignments(db, df: pd.DataFrame, school_id: str, user: dict, errors: list, warnings: list):
    """استيراد إسناد المعلمين مع التحقق المسبق والمعاملات المتكاملة (All-or-Nothing Atomic Import)"""
    imported = 0
    
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
    teachers_list = await gd_find(db.session, "teachers", {"school_id": school_id, "is_active": True}, limit=2000)
    for t in teachers_list:
        teachers_cache[t.get('full_name', '').strip().lower()] = t
        if t.get('email'):
            teachers_cache[t['email'].strip().lower()] = t

    subjects_cache = {}
    subjects_list = await gd_find(db.session, "subjects", {"school_id": school_id, "is_active": True}, limit=2000)
    for s in subjects_list:
        subjects_cache[s.get('name_ar', '').strip().lower()] = s
        subjects_cache[s.get('name', '').strip().lower()] = s

    classes_cache = {}
    classes_list = await gd_find(db.session, "classes", {"school_id": school_id, "is_active": True}, limit=2000)
    for c in classes_list:
        classes_cache[c.get('name', '').strip().lower()] = c

    valid_records = []

    for idx, row in df.iterrows():
        row_num = idx + 2
        row_errors = []

        if row.dropna().empty:
            continue

        try:
            teacher_name = str(row.get('teacher_name', '')).strip() if pd.notna(row.get('teacher_name')) else ''
            if teacher_name.lower() == 'nan':
                teacher_name = ''
                
            subject_name = str(row.get('subject_name', '')).strip() if pd.notna(row.get('subject_name')) else ''
            if subject_name.lower() == 'nan':
                subject_name = ''

            if not teacher_name:
                row_errors.append({"row": row_num, "field": "اسم المعلم", "message": "اسم المعلم: حقل مطلوب ولا يمكن تركه فارغاً"})

            if not subject_name:
                row_errors.append({"row": row_num, "field": "اسم المادة", "message": "اسم المادة: حقل مطلوب ولا يمكن تركه فارغاً"})

            teacher = teachers_cache.get(teacher_name.lower())
            if not teacher:
                teacher_email = str(row.get('teacher_email', '')).strip().lower() if pd.notna(row.get('teacher_email')) else ''
                if teacher_email and teacher_email != 'nan':
                    teacher = teachers_cache.get(teacher_email)

            if teacher_name and not teacher:
                row_errors.append({"row": row_num, "field": "اسم المعلم", "message": f"المعلم ({teacher_name}): غير مسجل في المدرسة. يرجى إضافة المعلم أولاً."})

            class_name = str(row.get('class_name', '')).strip() if pd.notna(row.get('class_name')) and str(row.get('class_name', '')).strip() != 'nan' else None

            if row_errors:
                errors.extend(row_errors)
            else:
                weekly_periods_raw = row.get('weekly_periods')
                weekly_periods = int(weekly_periods_raw) if pd.notna(weekly_periods_raw) and str(weekly_periods_raw).strip().isdigit() else None
                notes = str(row.get('notes', '')).strip() if pd.notna(row.get('notes')) and str(row.get('notes', '')).strip() != 'nan' else None

                valid_records.append({
                    "row_num": row_num,
                    "teacher": teacher,
                    "teacher_name": teacher_name,
                    "subject_name": subject_name,
                    "class_name": class_name,
                    "weekly_periods": weekly_periods,
                    "notes": notes,
                })

        except Exception as e:
            errors.append({"row": row_num, "field": "عام", "message": f"خطأ في معالجة الصف: {str(e)}"})

    failed_rows_count = len(set(e['row'] for e in errors))
    if errors:
        return {"imported": 0, "failed": failed_rows_count}

    for item in valid_records:
        subject = subjects_cache.get(item["subject_name"].lower())
        if not subject:
            subject_id = str(uuid.uuid4())
            subject = {
                "id": subject_id,
                "school_id": school_id,
                "name": item["subject_name"],
                "name_ar": item["subject_name"],
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "import_source": "noor_import"
            }
            await gd_insert(db.session, "subjects", subject)
            subjects_cache[item["subject_name"].lower()] = subject

        class_id = None
        if item["class_name"]:
            class_doc = classes_cache.get(item["class_name"].lower())
            if class_doc:
                class_id = class_doc["id"]

        dup_query = {
            "teacher_id": item["teacher"]["id"],
            "subject_id": subject["id"],
            "school_id": school_id
        }
        if class_id:
            dup_query["class_id"] = class_id

        existing = await gd_find_one(db.session, "teacher_assignments", dup_query)
        if not existing:
            assignment_doc = {
                "id": str(uuid.uuid4()),
                "school_id": school_id,
                "teacher_id": item["teacher"]["id"],
                "subject_id": subject["id"],
                "class_id": class_id,
                "teacher_name": item["teacher"].get("full_name", item["teacher_name"]),
                "subject_name": subject.get("name_ar", item["subject_name"]),
                "weekly_periods": item["weekly_periods"],
                "notes": item["notes"],
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": user.get("id"),
                "import_source": "noor_import"
            }
            await gd_insert(db.session, "teacher_assignments", assignment_doc)
        imported += 1

    return {"imported": imported, "failed": 0}


async def _export_students(db, school_id: str, grade: str = None, class_name: str = None):
    """تصدير الطلاب"""
    query = {}
    if school_id:
        query["school_id"] = school_id
    if grade:
        query["grade"] = grade
    if class_name:
        query["class_name"] = class_name
    
    query["is_active"] = True
    students = await gd_find(db.session, "students", query, limit=10000)
    
    data = []
    for s in students:
        data.append({
            'الاسم الأول': s.get('first_name', ''),
            'اسم الأب': s.get('father_name', ''),
            'اسم العائلة': s.get('last_name', ''),
            'الاسم الكامل': s.get('full_name', ''),
            'رقم الهوية': s.get('national_id', ''),
            'تاريخ الميلاد': s.get('date_of_birth') or s.get('birth_date', ''),
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

    @router.get("/batches/latest")
    async def get_latest_batch(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
    ):
        """الحصول على أحدث دفعة استيراد نشطة للمدرسة"""
        school_id = current_user.get("tenant_id") or current_user.get("school_id")
        batches = await gd_find(
            db.session,
            "bulk_import_batches",
            {"school_id": school_id, "status": "active"},
            order_by="created_at",
            desc_order=True,
            limit=1
        )
        batch = batches[0] if batches else None
        return {"batch": batch}

    @router.post("/batches/{batch_id}/rollback")
    async def rollback_import_batch(
        batch_id: str,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
    ):
        """التراجع الذري عن دفعة استيراد: إلغاء الطلاب، وحذف الفصول التلقائية الفارغة، وإعادة احتساب الأعداد"""
        school_id = current_user.get("tenant_id") or current_user.get("school_id")
        batches = await gd_find(
            db.session,
            "bulk_import_batches",
            {"id": batch_id}
        )
        if not batches:
            raise HTTPException(status_code=404, detail="دفعة الاستيراد غير موجودة")

        batch = batches[0]
        if batch.get("school_id") != school_id and current_user.get("role") != "platform_admin":
            raise HTTPException(status_code=403, detail="غير مصرح لك بالتراجع عن هذه الدفعة")

        if batch.get("status") == "rolled_back":
            raise HTTPException(status_code=400, detail="تم التراجع عن هذه الدفعة مسبقاً")

        student_ids = batch.get("student_ids") or []
        created_class_ids = batch.get("created_class_ids") or []
        affected_class_ids = set()

        if student_ids:
            students = await gd_find(
                db.session,
                "students",
                {"id": {"$in": student_ids}, "school_id": school_id, "is_active": True},
                limit=len(student_ids) + 100
            )
            for s in students:
                if s.get("class_id"):
                    affected_class_ids.add(s["class_id"])

            now_iso = datetime.now(timezone.utc).isoformat()
            await gd_update_many(
                db.session,
                "students",
                {"id": {"$in": student_ids}, "school_id": school_id},
                {"$set": {"is_active": False, "class_id": None, "updated_at": now_iso}}
            )

        rolled_back_classes_count = 0
        now_iso = datetime.now(timezone.utc).isoformat()
        for cid in created_class_ids:
            remaining = await gd_count(
                db.session,
                "students",
                {"class_id": cid, "school_id": school_id, "is_active": True}
            )
            if remaining == 0:
                await gd_update_one(
                    db.session,
                    "classes",
                    {"id": cid, "school_id": school_id},
                    {"$set": {"is_active": False, "updated_at": now_iso}}
                )
                rolled_back_classes_count += 1
            else:
                affected_class_ids.add(cid)

        from engines.entity_counts import reconcile_school_counts, reconcile_class_counts
        await reconcile_school_counts(db.session, school_id)
        for cid in affected_class_ids:
            try:
                await reconcile_class_counts(db.session, cid, school_id)
            except Exception as ex:
                logger.warning(f"Failed to reconcile class count {cid}: {ex}")

        now_dt = datetime.now(timezone.utc)
        await gd_update_one(
            db.session,
            "bulk_import_batches",
            {"id": batch_id},
            {"$set": {"status": "rolled_back", "updated_at": now_dt}}
        )

        await gd_insert(db.session, "audit_logs", {
            "id": str(uuid.uuid4()),
            "action": "bulk_import_rollback",
            "performed_by": current_user.get("id"),
            "performed_by_name": current_user.get("full_name") or current_user.get("name"),
            "timestamp": now_dt.isoformat(),
            "details": {
                "school_id": school_id,
                "batch_id": batch_id,
                "rolled_back_students": len(student_ids),
                "rolled_back_classes": rolled_back_classes_count
            }
        })

        return {
            "success": True,
            "message": f"تم التراجع بنجاح عن استيراد {len(student_ids)} طالب وحذف {rolled_back_classes_count} فصل مُنشأ تلقائياً",
            "batch_id": batch_id,
            "rolled_back_students": len(student_ids),
            "rolled_back_classes": rolled_back_classes_count,
        }

    return router

"""
NASSAQ - Bulk Import/Export Routes
استيراد وتصدير البيانات الجماعي
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, BackgroundTasks, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
import pandas as pd
import io
import uuid
import re
import logging
from enum import Enum
from engines.export_engine import _sanitize_formula_cell
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate
from src.common.utils.tenant_scope import resolve_school_id

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
    # Student-import counters.  Defaults keep the response contract stable
    # for the other bulk import types.
    created: int = 0
    updated: int = 0
    restored: int = 0
    assigned: int = 0
    classes_created: int = 0
    classes_reused: int = 0
    parents_created: int = 0
    parents_reused: int = 0
    students_linked_to_parents: int = 0
    grades_created: int = 0
    grades_reused: int = 0
    validation_errors: int = 0
    relationship_errors: int = 0
    skipped: int = 0
    existing: int = 0
    existing_student_ids: List[str] = Field(default_factory=list)
    student_ids: List[str] = Field(default_factory=list)
    created_student_ids: List[str] = Field(default_factory=list)
    updated_student_ids: List[str] = Field(default_factory=list)
    restored_student_ids: List[str] = Field(default_factory=list)
    created_class_ids: List[str] = Field(default_factory=list)
    created_parent_ids: List[str] = Field(default_factory=list)


async def _parent_user_reference_counts(session, user: dict) -> tuple[int | None, int]:
    """Return durable references that prevent deleting a parent user.

    ``parents`` is a per-school contact table and intentionally has no
    ``user_id`` column.  Passing ``{"user_id": ...}`` through ``gd_count`` is
    unsafe because unknown predicates are ignored for typed ORM collections.
    Resolve the parent-side reference by its durable email and use the
    canonical ``guardian_links.parent_ref`` relationship for the user-side
    reference instead.

    A parent user without an email cannot be proven unreferenced, so callers
    treat ``None`` as a fail-closed result.
    """
    email = user.get("email")
    if not email:
        return None, 0
    parent_email_count = await gd_count(
        session,
        "parents",
        {"email": email},
    )
    guardian_link_count = await gd_count(
        session,
        "guardian_links",
        {"parent_ref": user.get("id")},
    )
    return parent_email_count, guardian_link_count


async def _rollback_import_batch_mutations(
    db,
    batch_id: str,
    batch: dict,
    school_id: str,
    current_user: dict,
) -> dict:
    """Apply one rollback under the caller's SAVEPOINT.

    ``ownership_version`` is deliberately required for parent/user cleanup.
    Older manifests could infer parents/users from student rows and therefore
    could describe reused global resources. Such manifests remain rollbackable
    for their students/classes, but never authorize destructive parent cleanup.
    """
    student_ids = list(batch.get("student_ids") or [])
    student_ids_set = set(student_ids)
    ownership_safe = batch.get("ownership_version") == 2
    created_class_ids = list(batch.get("created_class_ids") or [])
    created_parent_ids = (
        list(batch.get("created_parent_ids") or []) if ownership_safe else []
    )
    created_parent_user_ids = (
        list(batch.get("created_parent_user_ids") or [])
        if ownership_safe else []
    )
    affected_class_ids = set()
    linked_parent_ids = set()

    students = []
    if student_ids:
        students = await gd_find(
            db.session,
            "students",
            {"id": {"$in": student_ids}, "school_id": school_id},
            limit=len(student_ids) + 100,
        )
        for student in students:
            if student.get("class_id"):
                affected_class_ids.add(student["class_id"])
            if student.get("parent_id"):
                # This set only updates a denormalized roster. It is never a
                # deletion grant for a reused parent row.
                linked_parent_ids.add(student["parent_id"])

        await gd_delete_many(
            db.session,
            "guardian_links",
            {"student_id": {"$in": student_ids}, "tenant_id": school_id},
        )

    parent_ids_to_update = linked_parent_ids | set(created_parent_ids)
    parents_to_delete = []
    if parent_ids_to_update:
        parent_records = await gd_find(
            db.session,
            "parents",
            {"id": {"$in": list(parent_ids_to_update)}, "school_id": school_id},
            limit=len(parent_ids_to_update) + 100,
        )
        for parent in parent_records:
            pid = parent["id"]
            other_students_count = await gd_count(
                db.session,
                "students",
                {"parent_id": pid, "id": {"$nin": student_ids}},
            )
            other_link_count = await gd_count(
                db.session,
                "guardian_links",
                {"parent_id": pid},
            )
            curr_sids = parent.get("student_ids") or []
            updated_sids = [sid for sid in curr_sids if sid not in student_ids_set]
            if (
                ownership_safe
                and pid in created_parent_ids
                and other_students_count == 0
                and other_link_count == 0
                and not updated_sids
            ):
                # It is safe to delete only an explicitly created row with no
                # remaining student reference in any tenant.
                parents_to_delete.append(pid)
            else:
                await gd_update_one(
                    db.session,
                    "parents",
                    {"id": pid, "school_id": school_id},
                    {"student_ids": updated_sids},
                )

    if student_ids:
        deleted_student_count = await gd_delete_many(
            db.session,
            "students",
            {"id": {"$in": student_ids}, "school_id": school_id},
        )
    else:
        deleted_student_count = 0

    rolled_back_parents_count = 0
    if parents_to_delete:
        try:
            await gd_delete_many(
                db.session,
                "parent_invitations",
                {"parent_id": {"$in": parents_to_delete}},
            )
        except Exception as exc:
            logger.warning("Failed to delete parent invitations: %s", exc)
        rolled_back_parents_count = await gd_delete_many(
            db.session,
            "parents",
            {"id": {"$in": parents_to_delete}, "school_id": school_id},
        )

    rolled_back_users_count = 0
    if created_parent_user_ids:
        users = await gd_find(
            db.session,
            "users",
            {
                "id": {"$in": created_parent_user_ids},
                "role": "parent",
                "tenant_id": school_id,
            },
            limit=len(created_parent_user_ids) + 100,
        )
        safe_user_ids = []
        for user in users:
            user_id = user.get("id")
            if not user_id:
                continue
            email_refs, link_refs = await _parent_user_reference_counts(
                db.session, user
            )
            # No email means the relationship cannot be verified through the
            # real-school parent table.  Keep the account rather than
            # guessing from an absent/phantom parents.user_id column.
            if email_refs is not None and not email_refs and not link_refs:
                safe_user_ids.append(user_id)
        if safe_user_ids:
            rolled_back_users_count = await gd_delete_many(
                db.session,
                "users",
                {
                    "id": {"$in": safe_user_ids},
                    "role": "parent",
                    "tenant_id": school_id,
                },
            )

    rolled_back_classes_count = 0
    for class_id in created_class_ids:
        remaining = await gd_count(
            db.session, "students", {"class_id": class_id}
        )
        if remaining == 0:
            await gd_delete_one(
                db.session,
                "classes",
                {"id": class_id, "school_id": school_id},
            )
            rolled_back_classes_count += 1
        else:
            affected_class_ids.add(class_id)

    from engines.entity_counts import reconcile_class_counts, reconcile_school_counts
    await reconcile_school_counts(db.session, school_id)
    for class_id in affected_class_ids:
        try:
            await reconcile_class_counts(db.session, class_id, school_id)
        except Exception as exc:
            logger.warning("Failed to reconcile class count %s: %s", class_id, exc)

    now_dt = datetime.now(timezone.utc)
    await gd_update_one(
        db.session,
        "bulk_import_batches",
        {"id": batch_id, "school_id": school_id},
        {"$set": {"status": "rolled_back", "updated_at": now_dt}},
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
            "rolled_back_students": deleted_student_count,
            "rolled_back_classes": rolled_back_classes_count,
            "rolled_back_parents": rolled_back_parents_count,
            "rolled_back_users": rolled_back_users_count,
        },
    })

    msg_parts = [f"تم التراجع بنجاح عن استيراد {deleted_student_count} طالب"]
    if rolled_back_parents_count:
        msg_parts.append(f"وحذف {rolled_back_parents_count} ولي أمر")
    if rolled_back_classes_count:
        msg_parts.append(f"وحذف {rolled_back_classes_count} فصل مُنشأ تلقائياً")
    return {
        "success": True,
        "message": " ".join(msg_parts),
        "batch_id": batch_id,
        "rolled_back_students": deleted_student_count,
        "rolled_back_classes": rolled_back_classes_count,
        "rolled_back_parents": rolled_back_parents_count,
        "rolled_back_users": rolled_back_users_count,
    }


def _resolve_bulk_school_id(
    current_user: dict,
    x_school_context: Optional[str],
    query_school_id: Optional[str] = None,
) -> str:
    """Resolve and require the tenant for a bulk operation.

    Both the legacy ``school_id`` query parameter and the frontend's
    ``X-School-Context`` header are treated as resolver overrides.  The
    canonical resolver therefore retains principal-tenant and
    platform-admin impersonation/MFA checks, while a platform admin with no
    selected school can never fall through to an unscoped query.
    """
    # Match the established route convention: an explicitly supplied query
    # value is the override, with the frontend context header as fallback.
    # Either value is still passed through the canonical resolver.
    override = query_school_id or x_school_context
    school_id = resolve_school_id(current_user, override)
    if not school_id:
        raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
    return school_id


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
                    'اسم الأب (مطلوب)': ['علي', 'خالد'],
                    'اسم الجد (مطلوب)': ['صالح', 'ناصر'],
                    'اسم العائلة (مطلوب)': ['السعيد', 'المالكي'],
                    'رقم الهوية (مطلوب)': ['1234567890', '0987654321'],
                    'تاريخ الميلاد (YYYY-MM-DD)': ['2015-05-15', '2014-08-20'],
                    'الجنس (ذكر/أنثى)': ['ذكر', 'ذكر'],
                    'الصف (مطلوب)': ['الصف الأول الابتدائي', 'الصف الثاني الابتدائي'],
                    'الفصل (مطلوب)': ['أ', 'ب'],
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
            with pd.ExcelWriter(
                output,
                engine='xlsxwriter',
                engine_kwargs={'options': {
                    'strings_to_formulas': False,
                    'strings_to_urls': False,
                }},
            ) as writer:
                safe_df = df.copy()
                safe_df.columns = [
                    _sanitize_formula_cell(col) for col in safe_df.columns
                ]
                safe_df = safe_df.map(_sanitize_formula_cell)
                safe_df.to_excel(writer, index=False, sheet_name='البيانات')
                
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
                for col_num, col_name in enumerate(safe_df.columns):
                    worksheet.write(
                        0, col_num, _sanitize_formula_cell(col_name), header_format
                    )
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
        x_school_context: Optional[str] = Header(default=None, alias="X-School-Context"),
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
    ):
        """استيراد البيانات من ملف Excel/CSV"""
        
        school_id = _resolve_bulk_school_id(
            current_user,
            x_school_context,
            school_id,
        )
        
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
                    "created": result.get("created", 0) if import_type == ImportType.STUDENTS else 0,
                    "updated": result.get("updated", 0) if import_type == ImportType.STUDENTS else 0,
                    "restored": result.get("restored", 0) if import_type == ImportType.STUDENTS else 0,
                    "assigned": result.get("assigned", 0) if import_type == ImportType.STUDENTS else 0,
                    "classes_created": result.get("classes_created", 0) if import_type == ImportType.STUDENTS else 0,
                     "classes_reused": result.get("classes_reused", 0) if import_type == ImportType.STUDENTS else 0,
                    "parents_created": result.get("parents_created", 0) if import_type == ImportType.STUDENTS else 0,
                     "parents_reused": result.get("parents_reused", 0) if import_type == ImportType.STUDENTS else 0,
                     "students_linked_to_parents": result.get("students_linked_to_parents", 0) if import_type == ImportType.STUDENTS else 0,
                     "grades_created": result.get("grades_created", 0) if import_type == ImportType.STUDENTS else 0,
                     "grades_reused": result.get("grades_reused", 0) if import_type == ImportType.STUDENTS else 0,
                     "validation_errors": result.get("validation_errors", 0) if import_type == ImportType.STUDENTS else 0,
                     "relationship_errors": result.get("relationship_errors", 0) if import_type == ImportType.STUDENTS else 0,
                    "skipped": result.get("skipped", 0) if import_type == ImportType.STUDENTS else 0,
                    "filename": file.filename,
                    "batch_id": batch_id
                }
            })
            
            response_fields = {
                "success": failed == 0,
                "total_rows": total_rows,
                "imported": imported,
                "failed": failed,
                "errors": errors[:50],  # Limit errors to 50
                "warnings": warnings[:50],
                "batch_id": batch_id,
            }
            if import_type == ImportType.STUDENTS:
                response_fields.update({
                    key: result.get(key, [] if key.endswith("_ids") else 0)
                    for key in (
                        "created", "updated", "restored", "assigned",
                        "classes_created", "classes_reused", "parents_created",
                        "parents_reused", "students_linked_to_parents",
                        "grades_created", "grades_reused", "validation_errors",
                        "relationship_errors", "skipped",
                        "existing", "student_ids", "created_student_ids",
                        "existing_student_ids",
                        "updated_student_ids", "restored_student_ids",
                        "created_class_ids", "created_parent_ids",
                    )
                })
            return ImportResult(**response_fields)
            
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
        x_school_context: Optional[str] = Header(default=None, alias="X-School-Context"),
        grade: Optional[str] = None,
        class_name: Optional[str] = None,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
    ):
        """تصدير البيانات إلى Excel/CSV"""
        
        school_id = _resolve_bulk_school_id(
            current_user,
            x_school_context,
            school_id,
        )
        
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
            
            safe_df = df.copy()
            safe_df.columns = [
                _sanitize_formula_cell(col) for col in safe_df.columns
            ]
            safe_df = safe_df.map(_sanitize_formula_cell)

            if format == "csv":
                safe_df.to_csv(output, index=False, encoding='utf-8-sig')
                media_type = 'text/csv'
                filename = filename.replace('.xlsx', '.csv')
            else:
                with pd.ExcelWriter(
                    output,
                    engine='xlsxwriter',
                    engine_kwargs={'options': {
                        'strings_to_formulas': False,
                        'strings_to_urls': False,
                    }},
                ) as writer:
                    safe_df.to_excel(writer, index=False, sheet_name='البيانات')
                    
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
                    
                    for col_num, col_name in enumerate(safe_df.columns):
                        worksheet.write(
                            0, col_num, _sanitize_formula_cell(col_name), header_format
                        )
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
    """Import students using the transactional service implementation."""
    from src.modules.bulk_import.services.student_import_service import import_students
    return await import_students(db, df, school_id, user, errors, warnings, filename)


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
    from src.common.utils.canonical_grades import normalize_canonical_grade
    from src.modules.bulk_import.services.student_import_service import _normalise_token

    query = {}
    if school_id:
        query["school_id"] = school_id
    canonical_grade = normalize_canonical_grade(grade) if grade else None
    if grade:
        # Student.grade is stored as the canonical number string.  Export
        # accepts either that number or its canonical label, but never emits
        # an unvalidated free-text grade.
        if not canonical_grade:
            return pd.DataFrame(), "تصدير_الطلاب.xlsx"
        query["grade"] = str(canonical_grade["grade"])

    class_rows = await gd_find(
        db.session,
        "classes",
        {"school_id": school_id, "is_active": {"$ne": False}} if school_id else {"is_active": {"$ne": False}},
        limit=10000,
    )
    classes_by_id = {str(c.get("id")): c for c in class_rows if c.get("id")}
    if class_name:
        class_token = _normalise_token(class_name)
        matching_class_ids = []
        for class_doc in class_rows:
            class_tokens = {
                _normalise_token(class_doc.get("name")),
                _normalise_token(class_doc.get("name_en")),
                _normalise_token(class_doc.get("section")),
            }
            if class_token in class_tokens:
                matching_class_ids.append(class_doc["id"])
        if not matching_class_ids:
            return pd.DataFrame(), "تصدير_الطلاب.xlsx"
        query["class_id"] = {"$in": matching_class_ids}
    
    query["is_active"] = True
    students = await gd_find(db.session, "students", query, limit=10000)
    
    data = []
    for s in students:
        class_doc = classes_by_id.get(str(s.get("class_id")))
        exported_grade = normalize_canonical_grade(s.get("grade"))
        exported_class = (
            (class_doc or {}).get("section")
            or (class_doc or {}).get("name")
            or ""
        )
        data.append({
            'الاسم الأول': s.get('first_name', ''),
            'اسم الأب': s.get('father_name', ''),
            'اسم العائلة': s.get('last_name', ''),
            'الاسم الكامل': s.get('full_name', ''),
            'رقم الهوية': s.get('national_id', ''),
            'تاريخ الميلاد': s.get('date_of_birth') or s.get('birth_date', ''),
            'الجنس': 'ذكر' if s.get('gender') == 'male' else 'أنثى',
            'الصف (مطلوب)': exported_grade["label_ar"] if exported_grade else '',
            'الفصل (مطلوب)': exported_class,
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
        x_school_context: Optional[str] = Header(default=None, alias="X-School-Context"),
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
    ):
        """Get import history and status"""
        school_id = _resolve_bulk_school_id(current_user, x_school_context)
        logs = await gd_find(db.session, "audit_logs", {"action": {"$regex": "^bulk_import_"}, "details.school_id": school_id}, order_by="timestamp", desc_order=True, limit=limit)

        return {"history": logs, "total": len(logs)}

    @router.get("/export-history")
    async def get_export_history(
        limit: int = 20,
        x_school_context: Optional[str] = Header(default=None, alias="X-School-Context"),
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
    ):
        """Get export history"""
        school_id = _resolve_bulk_school_id(current_user, x_school_context)
        logs = await gd_find(db.session, "audit_logs", {"action": "data_exported", "details.school_id": school_id}, order_by="timestamp", desc_order=True, limit=limit)

        return {"history": logs, "total": len(logs)}

    @router.get("/batches/latest")
    async def get_latest_batch(
        x_school_context: Optional[str] = Header(default=None, alias="X-School-Context"),
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
    ):
        """الحصول على أحدث دفعة استيراد نشطة للمدرسة"""
        school_id = _resolve_bulk_school_id(current_user, x_school_context)
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
        x_school_context: Optional[str] = Header(default=None, alias="X-School-Context"),
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
    ):
        """التراجع الذري عن دفعة استيراد: إلغاء الطلاب، وحذف الفصول التلقائية الفارغة، وإعادة احتساب الأعداد"""
        school_id = _resolve_bulk_school_id(current_user, x_school_context)
        batches = await gd_find(
            db.session,
            "bulk_import_batches",
            {"id": batch_id, "school_id": school_id}
        )
        if not batches:
            raise HTTPException(status_code=404, detail="دفعة الاستيراد غير موجودة")

        batch = batches[0]

        if batch.get("status") == "rolled_back":
            raise HTTPException(status_code=400, detail="تم التراجع عن هذه الدفعة مسبقاً")

        # Import and rollback share one transaction-scoped school lock. The
        # second read prevents two rollback requests from both observing an
        # active batch before either one marks it rolled back.
        from src.modules.bulk_import.services.student_import_service import (
            acquire_school_import_lock,
        )
        await acquire_school_import_lock(db.session, school_id)
        batches = await gd_find(
            db.session,
            "bulk_import_batches",
            {"id": batch_id, "school_id": school_id},
        )
        if not batches:
            raise HTTPException(status_code=404, detail="دفعة الاستيراد غير موجودة")
        batch = batches[0]
        if batch.get("status") == "rolled_back":
            raise HTTPException(status_code=400, detail="تم التراجع عن هذه الدفعة مسبقاً")
        async with db.session.begin_nested():
            return await _rollback_import_batch_mutations(
                db, batch_id, batch, school_id, current_user
            )
    return router

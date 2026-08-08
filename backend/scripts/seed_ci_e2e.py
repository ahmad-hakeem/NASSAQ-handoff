"""CI-only E2E seed. Creates the accounts frontend/e2e expects and writes
their credentials to an env file consumed by the e2e gate script.

SAFETY: refuses to run unless ENVIRONMENT=development AND CI_E2E_SEED=1.
Never run against a real database.

Account states (see frontend/e2e/lib/credentials.ts + frontend/e2e/README.md):

* E2E_IT_BOOTSTRAPPED_*   — independent_teacher, mfa_enrolled_at stamped but
  NO active mfa_factors row (the login challenge gate fires only on active
  factor rows — spec 1/6 sign in without an MFA challenge), workspace
  materialised (itw_{user_id}).
* E2E_IT_PRE_BOOTSTRAP_*  — independent_teacher, mfa_enrolled_at stamped,
  tenant_id NULL (spec 2 expects /teacher/onboarding).
* E2E_PRINCIPAL_*         — school_admin of a seeded real school with 2
  classes, one holding a student (student-transfer drag spec).
* E2E_PARENT_*            — real-school parent linked to a student.
* E2E_PLATFORM_ADMIN_* / E2E_PLATFORM_OPS_MANAGER_* / E2E_PLATFORM_SUB_ADMIN_*
* E2E_MFA_USER_* + E2E_MFA_USER_RECOVERY_CODE — independent_teacher with an
  ACTIVE TOTP factor + fresh recovery codes, workspace bootstrapped and
  carrying an active reactivation-banner snapshot (last_reactivated_at set,
  banner not dismissed) so post-login-redirect spec 5 sees the same-paint
  banner.

Idempotent: re-running rotates passwords/recovery codes in place and
re-asserts the required states; it never duplicates rows.
"""
import asyncio
import os
import secrets
import sys
import uuid
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import order matters: ``dependencies`` must be fully imported BEFORE any
# ``engines.*`` import, otherwise engines/__init__ → session_engine →
# parent_resolution → dependencies → engines.session_engine forms a circular
# import and blows up with a partially-initialized module error.
import dependencies  # noqa: E402,F401


def _now():
    return datetime.now(timezone.utc)


# Fixed, obviously-synthetic CI addresses. TEST_CREDENTIALS.md accounts are
# NOT touched — this seed owns its own namespace.
EMAILS = {
    "platform_admin": "ci-e2e-platform-admin@ci.nassaq.com",
    "platform_ops": "ci-e2e-platform-ops@ci.nassaq.com",
    "platform_sub": "ci-e2e-platform-sub@ci.nassaq.com",
    "principal": "ci-e2e-principal@ci.nassaq.com",
    "parent": "ci-e2e-parent@ci.nassaq.com",
    "it_boot": "ci-e2e-it-bootstrapped@ci.nassaq.com",
    "it_pre": "ci-e2e-it-prebootstrap@ci.nassaq.com",
    "mfa_user": "ci-e2e-mfa-user@ci.nassaq.com",
}

SCHOOL_CODE = "CI-E2E-001"
RECOVERY_CODES_BATCH = 10


async def _upsert_user(session, *, email, role, full_name, password,
                       tenant_id=None, extra=None):
    """Find-or-create a users row by email; always rotates the password and
    re-asserts role/tenant/active state so a stale DB cannot fail the suite."""
    from engines.sql_utils import gd_find_one, gd_insert, gd_update_one
    from dependencies import hash_password

    now_iso = _now().isoformat()
    base = {
        "full_name": full_name,
        "password_hash": hash_password(password),
        "role": role,
        "linked_roles": [role],
        "tenant_id": tenant_id,
        "status": "active",
        "is_active": True,
        "must_change_password": False,
        "preferred_language": "ar",
        "email_verified": True,
        # The E2E gate runs with MFA enforcement ON (no kill switch). The
        # Task #443 enrollment gate 403s every protected API call while
        # mfa_enrolled_at IS NULL, so every seeded account is stamped as
        # enrolled. The login CHALLENGE only fires on active mfa_factors
        # rows — only the dedicated MFA user gets one (via _enroll_totp),
        # so all other accounts sign in with password alone.
        "mfa_enrolled_at": now_iso,
        "updated_at": now_iso,
    }
    if extra:
        base.update(extra)
    existing = await gd_find_one(session, "users", {"email": email})
    if existing:
        await gd_update_one(session, "users", {"id": existing["id"]}, base)
        return existing["id"]
    user_id = str(uuid.uuid4())
    await gd_insert(session, "users", {
        "id": user_id, "email": email, "created_at": now_iso, **base,
    })
    return user_id


async def _upsert_row(session, table, lookup, data):
    from engines.sql_utils import gd_find_one, gd_insert, gd_update_one
    existing = await gd_find_one(session, table, lookup)
    if existing:
        await gd_update_one(session, table, lookup, data)
        return existing.get("id") or lookup.get("id")
    row = {**lookup, **data}
    if "id" not in row:
        row["id"] = str(uuid.uuid4())
    await gd_insert(session, table, row)
    return row["id"]


async def _materialise_it_workspace(session, user_id, *, name_ar):
    """Mirror the bootstrap route's materialisation (§6.a–6.g.bis of
    independent_teacher_bootstrap_routes.bootstrap_independent_teacher_workspace)
    for a CI account: schools + school_settings + academic year/term +
    teachers row + workspace_quota, then users.tenant_id."""
    from engines.sql_utils import gd_find_one, gd_update_one
    from quotas.independent_teacher import MAX_STUDENTS, DB_DEFAULT_MAX_CLASSES

    workspace_id = f"itw_{user_id}"
    now = _now()
    now_iso = now.isoformat()
    user = await gd_find_one(session, "users", {"id": user_id})

    await _upsert_row(session, "schools", {"id": workspace_id}, {
        "name": name_ar,
        "code": workspace_id[:24],
        "email": user.get("email"),
        "country": "SA",
        "language": "ar",
        "calendar_system": "hijri_gregorian",
        "status": "active",
        "school_type": "independent_teacher",
        "tenant_type": "independent_teacher",
        "setup_completed": True,
        "principal_id": user_id,
        "principal_name": user.get("full_name"),
        "principal_email": user.get("email"),
        "created_by": user_id,
        "created_at": now_iso,
        "updated_at": now_iso,
    })
    await _upsert_row(session, "school_settings", {"school_id": workspace_id}, {
        "working_days": ["sunday", "monday", "tuesday", "wednesday", "thursday"],
        "periods_per_day": 6,
        "language": "ar",
        "calendar": "hijri_gregorian",
        "created_at": now_iso,
        "updated_at": now_iso,
    })
    year_id = await _upsert_row(
        session, "academic_years",
        {"school_id": workspace_id, "name": "2026-2027"},
        {
            "start_date": now_iso,
            "end_date": (now + timedelta(days=300)).isoformat(),
            "is_current": True,
            "status": "active",
            "created_at": now_iso,
            "updated_at": now_iso,
        })
    await _upsert_row(
        session, "academic_terms",
        {"school_id": workspace_id, "term_number": 1},
        {
            "academic_year_id": year_id,
            "name": "الفصل الأول",
            "start_date": now_iso,
            "end_date": (now + timedelta(days=150)).isoformat(),
            "is_current": True,
            "status": "active",
            "created_at": now_iso,
            "updated_at": now_iso,
        })
    teacher_id = await _upsert_row(
        session, "teachers",
        {"school_id": workspace_id, "user_id": user_id},
        {
            "full_name": user.get("full_name"),
            "email": user.get("email"),
            "is_active": True,
            "created_at": now_iso,
            "updated_at": now_iso,
        })
    await _upsert_row(
        session, "workspace_quota", {"workspace_school_id": workspace_id},
        {
            "max_students": MAX_STUDENTS,
            "max_classes": DB_DEFAULT_MAX_CLASSES,
            "max_imports_per_day": 5,
            "max_rows_per_import": 200,
            "imports_today": 0,
            "created_at": now_iso,
            "updated_at": now_iso,
        })
    await gd_update_one(session, "users", {"id": user_id}, {
        "tenant_id": workspace_id,
        "teacher_id": teacher_id,
        "updated_at": now_iso,
    })
    return workspace_id


async def _enroll_totp(session, user_id):
    """Create an ACTIVE TOTP factor the same shape mfa_routes enroll
    begin+confirm produce (encrypted secret via services.mfa_crypto)."""
    from engines.sql_utils import gd_find, gd_update_one, gd_insert
    from services import mfa_crypto

    now = _now()
    # Retire any prior CI factors so re-runs stay at exactly one active row.
    for f in await gd_find(session, "mfa_factors", {"user_id": user_id}) or []:
        await gd_update_one(session, "mfa_factors", {"id": f["id"]}, {"is_active": False})

    secret = mfa_crypto.generate_totp_secret()
    await gd_insert(session, "mfa_factors", {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "kind": "totp",
        "label": "CI TOTP",
        "is_primary": True,
        "is_active": True,
        "totp_secret_encrypted": mfa_crypto.encrypt_totp_secret(secret),
        "verified_at": now,
        "created_at": now,
    })
    await gd_update_one(session, "users", {"id": user_id}, {"mfa_enrolled_at": now})
    return secret


async def _mint_recovery_codes(session, user_id):
    """Burn old codes, insert a fresh batch (bcrypt-hashed like
    mfa_routes.recovery_codes_regenerate), return the plaintext codes.

    Multiple plaintexts are exported so Playwright retries (retry #1 after
    a flake) don't fail on the single-use semantics of the first code."""
    from sqlalchemy import text as sa_text
    from engines.sql_utils import gd_insert, gd_update_one
    from services import mfa_crypto

    now = _now()
    await session.execute(
        sa_text("UPDATE mfa_recovery_codes SET consumed_at = :now "
                "WHERE user_id = :uid AND consumed_at IS NULL"),
        {"now": now, "uid": user_id},
    )
    plaintexts = []
    for _ in range(RECOVERY_CODES_BATCH):
        code = mfa_crypto.generate_recovery_code()
        plaintexts.append(code)
        await gd_insert(session, "mfa_recovery_codes", {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "code_hash": mfa_crypto.hash_recovery_code(code),
            "created_at": now,
            "consumed_at": None,
        })
    await gd_update_one(session, "users", {"id": user_id}, {
        "mfa_recovery_codes_generated_at": now,
        "mfa_recovery_codes_acknowledged": True,
    })
    return plaintexts


async def seed() -> dict:
    from db import async_session_factory
    from engines.sql_utils import gd_find_one, gd_update_one

    pw = {k: secrets.token_urlsafe(16) for k in EMAILS}
    creds: dict = {}
    now = _now()
    now_iso = now.isoformat()

    async with async_session_factory() as session:
        # ── Platform roles ────────────────────────────────────────────
        for key, role, env in (
            ("platform_admin", "platform_admin", "E2E_PLATFORM_ADMIN"),
            ("platform_ops", "platform_operations_manager", "E2E_PLATFORM_OPS_MANAGER"),
            ("platform_sub", "platform_sub_admin", "E2E_PLATFORM_SUB_ADMIN"),
        ):
            await _upsert_user(
                session, email=EMAILS[key], role=role,
                full_name="حساب منصة تجريبي", password=pw[key])
            creds[f"{env}_EMAIL"] = EMAILS[key]
            creds[f"{env}_PASSWORD"] = pw[key]

        # ── Principal school (2 classes, 1 student) ───────────────────
        school_id = await _upsert_row(session, "schools", {"code": SCHOOL_CODE}, {
            "name": "مدرسة الاختبار الآلي",
            "name_en": "CI E2E School",
            "country": "SA",
            "language": "ar",
            "calendar_system": "hijri_gregorian",
            "school_type": "public",
            "tenant_type": "production",
            "status": "active",
            "setup_completed": True,
            "created_at": now_iso,
            "updated_at": now_iso,
        })
        principal_id = await _upsert_user(
            session, email=EMAILS["principal"], role="school_admin",
            full_name="مدير مدرسة الاختبار", password=pw["principal"],
            tenant_id=school_id, extra={"primary_tenant_id": school_id})
        creds["E2E_PRINCIPAL_EMAIL"] = EMAILS["principal"]
        creds["E2E_PRINCIPAL_PASSWORD"] = pw["principal"]

        class_ids = []
        for name, grade in (("الصف الأول أ", "1"), ("الصف الأول ب", "1")):
            cid = await _upsert_row(
                session, "classes", {"school_id": school_id, "name": name},
                {
                    "grade_level": grade,
                    "capacity": 30,
                    "current_students": 0,
                    "is_active": True,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                })
            class_ids.append(cid)

        # ── Parent + linked student ───────────────────────────────────
        parent_id = await _upsert_row(
            session, "parents", {"email": EMAILS["parent"]},
            {
                "full_name": "ولي أمر الاختبار",
                "phone": "0550000001",
                "school_id": school_id,
                "student_ids": [],
                "is_active": True,
                "created_at": now_iso,
                "updated_at": now_iso,
            })
        parent_user_id = await _upsert_user(
            session, email=EMAILS["parent"], role="parent",
            full_name="ولي أمر الاختبار", password=pw["parent"],
            tenant_id=school_id,
            extra={"primary_tenant_id": school_id, "parent_id": parent_id,
                   # Pre-accept the mandatory Parent Charter so E2E specs
                   # land on /parent/* directly instead of the blocking
                   # CharterGuard modal.
                   "charter_accepted_at": now})
        # Parents are MFA Tier C — with enforcement ON (the E2E gate never
        # sets the kill switch) a parent without an active factor cannot
        # satisfy the change-password step-up gate (stepup/start 409s with
        # no factor). Enroll a real TOTP factor and export its secret so
        # Playwright completes the genuine login challenge, which also
        # stamps mfa_recent_at into the token for the ≤5-min step-up.
        parent_totp_secret = await _enroll_totp(session, parent_user_id)
        creds["E2E_PARENT_EMAIL"] = EMAILS["parent"]
        creds["E2E_PARENT_PASSWORD"] = pw["parent"]
        creds["E2E_PARENT_TOTP_SECRET"] = parent_totp_secret

        student_id = await _upsert_row(
            session, "students",
            {"school_id": school_id, "student_number": "CIE2E-001"},
            {
                "full_name": "طالب الاختبار الآلي",
                "class_id": class_ids[0],
                "grade": "1",
                "gender": "male",
                "parent_id": parent_id,
                "parent_name": "ولي أمر الاختبار",
                "parent_email": EMAILS["parent"],
                "is_active": True,
                "created_at": now_iso,
                "updated_at": now_iso,
            })
        await gd_update_one(session, "parents", {"id": parent_id},
                            {"student_ids": [student_id]})

        # ── IT bootstrapped (no active factor → no login challenge) ───
        it_boot_id = await _upsert_user(
            session, email=EMAILS["it_boot"], role="independent_teacher",
            full_name="معلم مستقل مهيأ", password=pw["it_boot"],
            extra={"mfa_enrolled_at": now})
        await _materialise_it_workspace(session, it_boot_id, name_ar="مساحة معلم الاختبار")
        creds["E2E_IT_BOOTSTRAPPED_EMAIL"] = EMAILS["it_boot"]
        creds["E2E_IT_BOOTSTRAPPED_PASSWORD"] = pw["it_boot"]

        # ── IT pre-bootstrap (tenant_id NULL) ─────────────────────────
        it_pre_id = await _upsert_user(
            session, email=EMAILS["it_pre"], role="independent_teacher",
            full_name="معلم مستقل جديد", password=pw["it_pre"],
            tenant_id=None, extra={"mfa_enrolled_at": now, "teacher_id": None})
        # A stale re-run may have left a tenant; force pre-bootstrap state.
        await gd_update_one(session, "users", {"id": it_pre_id},
                            {"tenant_id": None, "teacher_id": None})
        creds["E2E_IT_PRE_BOOTSTRAP_EMAIL"] = EMAILS["it_pre"]
        creds["E2E_IT_PRE_BOOTSTRAP_PASSWORD"] = pw["it_pre"]

        # ── MFA user: active TOTP + recovery codes + banner snapshot ──
        mfa_id = await _upsert_user(
            session, email=EMAILS["mfa_user"], role="independent_teacher",
            full_name="معلم مستقل موثّق", password=pw["mfa_user"])
        mfa_ws = await _materialise_it_workspace(session, mfa_id, name_ar="مساحة معلم موثّق")
        await _enroll_totp(session, mfa_id)
        recovery_codes = await _mint_recovery_codes(session, mfa_id)
        # Genuine archive→reactivate cycle snapshot (the exact fields
        # reactivate_workspace writes): status active, archived_at NULL,
        # last_reactivated_at now, cycle archive stamp 5 days ago, banner
        # never dismissed → _build_lifecycle_payload arms the banner.
        await gd_update_one(session, "schools", {"id": mfa_ws}, {
            "status": "active",
            "archived_at": None,
            "last_reactivated_at": now_iso,
            "last_archive_cycle_archived_at": (now - timedelta(days=5)).isoformat(),
            "reactivation_banner_dismissed_at": None,
            "updated_at": now_iso,
        })
        creds["E2E_MFA_USER_EMAIL"] = EMAILS["mfa_user"]
        creds["E2E_MFA_USER_PASSWORD"] = pw["mfa_user"]
        creds["E2E_MFA_USER_RECOVERY_CODE"] = recovery_codes[0]
        # Comma-separated pool: specs consume codes[testInfo.retry] so a
        # Playwright retry never replays an already-consumed code.
        creds["E2E_MFA_USER_RECOVERY_CODES"] = ",".join(recovery_codes[:4])

        await session.commit()

    return creds


def main() -> None:
    if os.environ.get("ENVIRONMENT") != "development" or os.environ.get("CI_E2E_SEED") != "1":
        sys.exit("seed_ci_e2e: refusing to run (need ENVIRONMENT=development and CI_E2E_SEED=1)")
    out_path = os.environ.get("CI_E2E_ENV_FILE", "/tmp/ci_e2e.env")
    creds = asyncio.run(seed())
    with open(out_path, "w") as f:
        for k, v in creds.items():
            f.write(f"{k}={v}\n")
    os.chmod(out_path, 0o600)
    print(f"seed_ci_e2e: wrote {len(creds)} vars to {out_path}")


if __name__ == "__main__":
    main()

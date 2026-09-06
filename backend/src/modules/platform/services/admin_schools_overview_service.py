"""
Admin Schools Overview Service
Handles aggregation, filtering, pagination, metrics calculation, and formatting
for the Platform Admin Command Center Schools Overview.
"""
from datetime import datetime, timezone
import logging
import math
from typing import Any, Dict, List, Optional
from sqlalchemy import text as sql

from src.common.utils.avatar_serving import signed_image_url
from src.common.utils.platform_admin_preview import assess_principal_preview_eligibility

logger = logging.getLogger("nassaq.admin_schools_overview")


class AdminSchoolsOverviewService:
    """Service providing aggregated schools data for the platform admin command center."""

    ORDER_MAP: Dict[str, str] = {
        "name_asc":      "ORDER BY s.name ASC NULLS LAST",
        "name_desc":     "ORDER BY s.name DESC NULLS LAST",
        "students_desc": "ORDER BY student_count DESC NULLS LAST",
        "teachers_desc": "ORDER BY teacher_count DESC NULLS LAST",
        "classes_desc":  "ORDER BY class_count DESC NULLS LAST",
        "newest":        "ORDER BY s.created_at DESC NULLS LAST",
    }

    @classmethod
    async def get_schools_overview(
        cls,
        session,
        page: int = 1,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Orchestrates fetching all data required for the schools overview screen:
        1. Global platform statistics.
        2. Unique cities for dropdown filtering.
        3. Draft/setup schools list.
        4. Paginated matching schools with analytics counts.
        """
        filters = filters or {}
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # ── 1. Pagination calculation ──────────────────────────────────────────
        page = max(1, int(page or 1))
        limit = max(1, min(1000, int(limit or 10)))
        offset = (page - 1) * limit

        # ── 2. Platform-wide stats & filter metadata ───────────────────────────
        stats_summary = await cls._fetch_platform_stats(session)
        cities_list = await cls._fetch_cities(session)
        drafts_list = await cls._fetch_drafts(session)

        # ── 3. Build filter & sort SQL ─────────────────────────────────────────
        where_sql, params = cls._build_filter_clauses(filters)
        order_sql = cls.ORDER_MAP.get(sort_by or "", "ORDER BY s.created_at DESC NULLS LAST")

        # ── 4. Total count for pagination ──────────────────────────────────────
        total_matching = (
            await session.execute(sql(f"SELECT COUNT(*) FROM schools s {where_sql}"), params)
        ).scalar() or 0

        # ── 5. Main paginated query ────────────────────────────────────────────
        rows = await cls._fetch_paginated_schools_rows(
            session=session,
            where_sql=where_sql,
            order_sql=order_sql,
            params=params,
            limit=limit,
            offset=offset,
        )

        # ── 6. Today's sessions lookup ─────────────────────────────────────────
        school_ids = [r["id"] for r in rows]
        sessions_today_map = await cls._fetch_sessions_today(session, school_ids, today)

        # ── 7. Transform & build result items ──────────────────────────────────
        schools = [
            cls._format_school_record(row=r, sessions_count=sessions_today_map.get(r["id"], 0))
            for r in rows
        ]

        total_pages = math.ceil(total_matching / limit) if limit > 0 else 1

        return {
            "schools": schools,
            "drafts": drafts_list,
            "cities": cities_list,
            "total": total_matching,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "stats": stats_summary,
        }

    @classmethod
    async def _fetch_platform_stats(cls, session) -> Dict[str, int]:
        """Fetch unfiltered platform-wide statistics for top summary counters."""
        stats_row = (await session.execute(sql("""
            SELECT
                COUNT(*)                                          AS total_schools,
                COUNT(*) FILTER (WHERE status = 'active')        AS active_schools,
                COUNT(*) FILTER (WHERE status = 'suspended')     AS suspended_schools,
                COUNT(*) FILTER (WHERE status = 'pending')       AS pending_schools,
                COUNT(*) FILTER (WHERE status = 'setup')         AS draft_schools,
                COALESCE((SELECT COUNT(*) FROM students), 0)     AS total_students,
                COALESCE((SELECT COUNT(*) FROM teachers), 0)     AS total_teachers,
                COALESCE((SELECT COUNT(*) FROM classes),  0)     AS total_classes
            FROM schools
        """))).mappings().first() or {}

        draft_count = int(stats_row.get("draft_schools") or 0)
        return {
            "total": max(0, int(stats_row.get("total_schools") or 0) - draft_count),
            "active": int(stats_row.get("active_schools") or 0),
            "suspended": int(stats_row.get("suspended_schools") or 0),
            "pending": int(stats_row.get("pending_schools") or 0),
            "drafts": draft_count,
            "totalStudents": int(stats_row.get("total_students") or 0),
            "totalTeachers": int(stats_row.get("total_teachers") or 0),
            "totalClasses": int(stats_row.get("total_classes") or 0),
        }

    @classmethod
    async def _fetch_cities(cls, session) -> List[str]:
        """Fetch distinct non-empty cities for filter dropdown."""
        return [
            c for c in (await session.execute(sql("""
                SELECT DISTINCT city FROM schools
                WHERE city IS NOT NULL AND TRIM(city) != ''
                ORDER BY city ASC
            """))).scalars().all()
            if c
        ]

    @classmethod
    async def _fetch_drafts(cls, session, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch schools in setup/draft status."""
        return [
            dict(d) for d in (await session.execute(sql("""
                SELECT id, name, name_en, code, status, city, region,
                       email, phone, principal_name, created_at, updated_at
                FROM schools
                WHERE status = 'setup'
                ORDER BY created_at DESC
                LIMIT :limit
            """), {"limit": limit})).mappings().all()
        ]

    @classmethod
    def _build_filter_clauses(cls, filters: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """Build dynamic WHERE clauses and parameter mappings from filter inputs."""
        where_clauses: List[str] = []
        params: Dict[str, Any] = {}

        status = filters.get("status")
        if status and status != "all":
            where_clauses.append("s.status = :status")
            params["status"] = status
        else:
            where_clauses.append("s.status != 'setup'")

        city = filters.get("city")
        if city and city != "all":
            where_clauses.append("s.city = :city")
            params["city"] = city

        school_type = filters.get("school_type")
        if school_type and school_type != "all":
            where_clauses.append("s.school_type = :school_type")
            params["school_type"] = school_type

        stage = filters.get("stage")
        if stage and stage != "all":
            where_clauses.append("s.stage = :stage")
            params["stage"] = stage

        search = filters.get("search")
        if search and str(search).strip():
            where_clauses.append(
                "(s.name ILIKE :search OR s.name_en ILIKE :search"
                " OR s.code ILIKE :search OR s.city ILIKE :search"
                " OR s.email ILIKE :search)"
            )
            params["search"] = f"%{str(search).strip()}%"

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        return where_sql, params

    @classmethod
    async def _fetch_paginated_schools_rows(
        cls,
        session,
        where_sql: str,
        order_sql: str,
        params: Dict[str, Any],
        limit: int,
        offset: int,
    ) -> List[Dict[str, Any]]:
        """Execute the aggregated multi-join query to retrieve school rows."""
        query_params = dict(params)
        query_params["limit"] = limit
        query_params["offset"] = offset

        return (await session.execute(sql(f"""
            SELECT
                s.id, s.name, s.name_en, s.code, s.status,
                s.city, s.region, s.address, s.country,
                s.phone, s.email, s.logo_url,
                s.school_type, s.stage, s.language,
                s.calendar_system, s.student_capacity,
                s.principal_name, s.principal_email, s.principal_phone,
                s.educational_pathway,
                s.created_at, s.updated_at,
                COALESCE(st.cnt, 0)         AS student_count,
                COALESCE(t.cnt,  0)         AS teacher_count,
                COALESCE(c.cnt,  0)         AS class_count,
                COALESCE(p.cnt,  0)         AS parent_count,
                COALESCE(tt.published, 0)   AS published_timetable_count,
                COALESCE(pr.cnt, 0)         AS active_principal_count
            FROM schools s
            LEFT JOIN (SELECT school_id, COUNT(*) AS cnt FROM students GROUP BY school_id) st ON st.school_id = s.id
            LEFT JOIN (SELECT school_id, COUNT(*) AS cnt FROM teachers GROUP BY school_id) t  ON t.school_id  = s.id
            LEFT JOIN (SELECT school_id, COUNT(*) AS cnt FROM classes  GROUP BY school_id) c  ON c.school_id  = s.id
            LEFT JOIN (SELECT school_id, COUNT(*) AS cnt FROM parents  GROUP BY school_id) p  ON p.school_id  = s.id
            LEFT JOIN (
                SELECT school_id, COUNT(*) AS published
                FROM timetable_runs WHERE status = 'published'
                GROUP BY school_id
            ) tt ON tt.school_id = s.id
            LEFT JOIN (
                SELECT tenant_id, COUNT(*)::int AS cnt
                FROM users
                WHERE role = 'school_principal'
                  AND is_active = TRUE
                  AND tenant_id IS NOT NULL
                GROUP BY tenant_id
            ) pr ON pr.tenant_id = s.id
            {where_sql}
            {order_sql}
            LIMIT :limit OFFSET :offset
        """), query_params)).mappings().all()

    @classmethod
    async def _fetch_sessions_today(
        cls, session, school_ids: List[str], today: str
    ) -> Dict[str, int]:
        """Fetch count of today's sessions for the specified school IDs."""
        if not school_ids:
            return {}

        sessions_rs = await session.execute(sql("""
            SELECT data->>'school_id' AS sid, COUNT(*) AS cnt
            FROM generic_documents
            WHERE collection = 'class_sessions'
              AND data->>'date' = :today
              AND data->>'school_id' = ANY(:sids)
            GROUP BY data->>'school_id'
        """), {"today": today, "sids": school_ids})

        return {sid: int(cnt) for sid, cnt in sessions_rs.all()}

    @classmethod
    def _format_school_record(cls, row: Dict[str, Any], sessions_count: int) -> Dict[str, Any]:
        """Transform a raw SQL database row into the standardized school record schema."""
        sid = row["id"]
        student_count = int(row.get("student_count") or 0)
        teacher_count = int(row.get("teacher_count") or 0)
        class_count = int(row.get("class_count") or 0)
        parent_count = int(row.get("parent_count") or 0)
        principal_count = int(row.get("active_principal_count") or 0)
        has_timetable = (row.get("published_timetable_count") or 0) > 0

        setup_score = sum([
            teacher_count > 0,
            student_count > 0,
            class_count > 0,
            has_timetable,
        ]) * 25

        phone = row.get("phone") or row.get("principal_phone") or ""
        preview = assess_principal_preview_eligibility(
            dict(row), active_principal_count=principal_count
        )

        created_at = row.get("created_at")
        updated_at = row.get("updated_at")

        return {
            "id": sid,
            "name": row.get("name") or "",
            "name_en": row.get("name_en") or "",
            "code": row.get("code") or "",
            "status": row.get("status") or "active",
            "city": row.get("city") or "",
            "region": row.get("region") or "",
            "address": row.get("address") or "",
            "country": row.get("country") or "SA",
            "phone": phone,
            "email": row.get("email") or "",
            "logo_url": signed_image_url("logo", sid, row.get("logo_url")),
            "school_type": row.get("school_type") or "public",
            "stage": row.get("stage") or "primary",
            "language": row.get("language") or "ar",
            "calendar_system": row.get("calendar_system") or "hijri_gregorian",
            "student_capacity": row.get("student_capacity") or 500,
            "principal_name": row.get("principal_name") or "",
            "principal_email": row.get("principal_email") or "",
            "principal_phone": row.get("principal_phone") or phone,
            "principal_mobile": phone,
            "educational_pathway": row.get("educational_pathway") or "",
            "student_count": student_count,
            "teacher_count": teacher_count,
            "class_count": class_count,
            "parent_count": parent_count,
            "sessions_today": sessions_count,
            "setup_score": setup_score,
            "has_timetable": has_timetable,
            "created_at": created_at.isoformat() if created_at else "",
            "last_activity": updated_at.isoformat() if updated_at else "",
            "can_preview_as_principal": preview["can_preview_as_principal"],
            "preview_block_reason": preview["preview_block_reason"],
            "entity_kind": preview["entity_kind"],
        }

    @classmethod
    def get_empty_fallback(cls, limit: int = 10) -> Dict[str, Any]:
        """Provides a safe empty fallback response structure upon exceptions."""
        return {
            "schools": [],
            "drafts": [],
            "cities": [],
            "total": 0,
            "page": 1,
            "limit": limit,
            "total_pages": 0,
            "stats": {
                "total": 0,
                "active": 0,
                "suspended": 0,
                "pending": 0,
                "drafts": 0,
                "totalStudents": 0,
                "totalTeachers": 0,
                "totalClasses": 0,
            },
        }

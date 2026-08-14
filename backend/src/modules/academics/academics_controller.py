"""
Academics Controller
= NestJS @Controller()

HTTP endpoints for Academics.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Academics"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.academics.controllers.academics_class_routes import router as _academics_class_routes_router
    router.include_router(_academics_class_routes_router)
    from src.modules.academics.controllers.academics_student_routes import router as _academics_student_routes_router
    router.include_router(_academics_student_routes_router)
    from src.modules.academics.controllers.academics_teacher_routes import router as _academics_teacher_routes_router
    router.include_router(_academics_teacher_routes_router)
    from src.modules.academics.controllers.academics_subject_routes import router as _academics_subject_routes_router
    router.include_router(_academics_subject_routes_router)
    from src.modules.academics.controllers.academics_year_term_routes import router as _academics_year_term_routes_router
    router.include_router(_academics_year_term_routes_router)
    from src.modules.academics.controllers.academics_structure_engine_routes import router as _academics_structure_engine_routes_router
    router.include_router(_academics_structure_engine_routes_router)

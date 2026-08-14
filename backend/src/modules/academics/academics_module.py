"""
Academics Module
= NestJS @Module()

Wires together academics controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register academics routes into api_router."""
    from src.modules.academics.controllers.academics_reference_routes import router as _academics_reference_routes_router
    api_router.include_router(_academics_reference_routes_router)
    from src.modules.academics.controllers.official_curriculum_routes import router as _official_curriculum_routes_router
    api_router.include_router(_official_curriculum_routes_router)
    from src.modules.academics.controllers.academic_structure_routes import router as _academic_structure_routes_router
    api_router.include_router(_academic_structure_routes_router)
    from src.modules.academics.controllers.academics_year_term_routes import router as _academics_year_term_routes_router
    api_router.include_router(_academics_year_term_routes_router)
    from src.modules.academics.controllers.academics_structure_engine_routes import router as _academics_structure_engine_routes_router
    api_router.include_router(_academics_structure_engine_routes_router)
    from src.modules.academics.controllers.academics_subject_routes import router as _academics_subject_routes_router
    api_router.include_router(_academics_subject_routes_router)
    from src.modules.academics.controllers.academics_student_routes import router as _academics_student_routes_router
    api_router.include_router(_academics_student_routes_router)
    from src.modules.academics.controllers.academics_class_routes import router as _academics_class_routes_router
    api_router.include_router(_academics_class_routes_router)
    from src.modules.academics.controllers.class_management_routes import router as _class_management_routes_router
    api_router.include_router(_class_management_routes_router)
    from src.modules.academics.controllers.academics_teacher_routes import router as _academics_teacher_routes_router
    api_router.include_router(_academics_teacher_routes_router)
    logger.info("AcademicsModule: registered")

# NASSAQ Backend Architecture Guide

## Overview

The NASSAQ backend has been refactored into a modular architecture following best practices for maintainability and scalability.

## Directory Structure

```
/backend/
├── models/              # Pydantic models & enums
│   ├── __init__.py     # Central exports
│   ├── enums.py        # All enumerations (UserRole, SchoolStatus, etc.)
│   ├── user.py         # User-related models
│   ├── school.py       # School/tenant models
│   ├── dashboard.py    # Dashboard & statistics models
│   ├── academic.py     # Teacher, Student, Class models
│   ├── registration.py # Registration request models
│   ├── common.py       # Shared utility models
│   ├── foundation.py   # Foundation phase models
│   └── scheduling.py   # Scheduling models
│
├── services/           # Business logic & utilities
│   ├── __init__.py     # Central exports
│   ├── auth_service.py # Authentication (JWT, password hashing)
│   ├── database_service.py # Database connection & utilities
│   ├── audit_service.py # Audit logging
│   └── scheduling_service.py # Scheduling logic
│
├── routes/             # API route handlers
│   ├── __init__.py     # Central exports
│   ├── auth_routes.py  # /api/auth/* endpoints
│   ├── user_routes.py  # /api/users/* endpoints
│   ├── school_routes.py # /api/schools/* endpoints
│   ├── dashboard_routes.py # /api/dashboard/* endpoints
│   ├── public_routes.py # /api/public/* (no auth)
│   ├── scheduling_routes.py
│   ├── attendance_routes.py
│   ├── assessment_routes.py
│   └── ... (more routes)
│
├── engines/            # Core business engines
│
├── middleware/         # Request middleware
│   ├── rbac.py        # Role-based access control
│   └── tenant_isolation.py # Multi-tenant isolation
│
├── scripts/            # Seed and migration scripts
│
├── repositories/       # Repository pattern layer (BaseRepository, Repos container)
│   ├── base.py         # BaseRepository with find_one, find, insert_one, update_one, etc.
│   └── __init__.py     # Repos container, MODEL_REGISTRY, get_repos dependency
├── db.py               # Async SQLAlchemy engine, session factory
├── pg_models.py        # 49 ORM table models
├── alembic/            # Database migrations
└── server.py           # Main FastAPI application
```

## Key Concepts

### 1. Multi-Tenant Architecture
- Each school is a separate tenant
- All data queries filtered by `school_id` or `tenant_id`
- Tenant isolation enforced at API level

### 2. Role-Based Access Control (RBAC)
- `UserRole` enum defines all roles
- `require_roles()` dependency for route protection
- Hierarchical permissions

### 3. Database Layer
- PostgreSQL via async SQLAlchemy + asyncpg
- Repository pattern: `Repos` container with `BaseRepository` per model
- Repos resolves sessions lazily via context var (thread/task-safe)
- Engines/routes access collections via `db.collection_name.method()`
- Alembic manages schema migrations

### 4. Services Layer
Import from `services` package:
```python
from services import hash_password, verify_password, log_action
```

### 5. Routes Layer
Each route module exports a factory function:
```python
def create_auth_routes(db, get_current_user):
    router = APIRouter(prefix="/auth")
    return router
```

## API Conventions

1. All routes prefixed with `/api`
2. Use Arabic error messages with English fallback
3. Return `{"message": "..."}` for success
4. Use `HTTPException` for errors
5. Always audit important actions

## Environment Variables

Required:
- `DATABASE_URL` - PostgreSQL connection string
- `JWT_SECRET_KEY` - JWT signing key
- `JWT_ALGORITHM` - JWT algorithm (default: HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES` - Token expiry (default: 30)

---
Last Updated: 2026-04

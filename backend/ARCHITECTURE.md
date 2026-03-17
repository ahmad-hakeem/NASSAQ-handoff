# NASSAQ Backend Architecture Guide
# دليل بنية الباك إند

## Overview | نظرة عامة

The NASSAQ backend has been refactored into a modular architecture following best practices for maintainability and scalability.

## Directory Structure | هيكل المجلدات

```
/app/backend/
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
│   ├── academic_engine.py
│   ├── attendance_engine.py
│   ├── scheduling_engine.py
│   └── ... (more engines)
│
├── middleware/         # Request middleware
│   ├── rbac.py        # Role-based access control
│   └── tenant_isolation.py # Multi-tenant isolation
│
├── scripts/            # Utility scripts
│   ├── seed_controlled_demo.py
│   └── ... (seeding scripts)
│
├── tests/              # Test files
│
└── server.py           # Main FastAPI application
```

## Key Concepts | المفاهيم الأساسية

### 1. Multi-Tenant Architecture | البنية متعددة المستأجرين
- Each school is a separate tenant
- All data queries filtered by `school_id` or `tenant_id`
- Tenant isolation enforced at API level

### 2. Role-Based Access Control (RBAC)
- `UserRole` enum defines all roles
- `require_roles()` dependency for route protection
- Hierarchical permissions

### 3. Models Layer
Import from `models` package:
```python
from models import UserRole, UserResponse, SchoolStatus
```

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
    # ... define routes
    return router
```

## Adding New Features | إضافة ميزات جديدة

### 1. Add a new Model
Create in `/models/` and export in `__init__.py`:
```python
# models/my_feature.py
from pydantic import BaseModel

class MyFeature(BaseModel):
    name: str
    value: int
```

### 2. Add a new Route
Create in `/routes/` and register in `server.py`:
```python
# routes/my_feature_routes.py
def create_my_feature_routes(db, get_current_user):
    router = APIRouter(prefix="/my-feature")
    
    @router.get("")
    async def get_features(current_user: dict = Depends(get_current_user)):
        # ... implementation
        pass
    
    return router
```

### 3. Add a new Service
Create in `/services/` and export in `__init__.py`:
```python
# services/my_service.py
async def my_utility_function(db, param1, param2):
    # ... implementation
    pass
```

## API Conventions | اتفاقيات API

1. All routes prefixed with `/api`
2. Use Arabic error messages with English fallback
3. Return `{"message": "..."}` for success
4. Use `HTTPException` for errors
5. Always audit important actions

## Testing | الاختبار

```bash
# Run all tests
pytest tests/

# Run specific test
pytest tests/test_auth_api.py

# Run with coverage
pytest --cov=. tests/
```

## Environment Variables | متغيرات البيئة

Required in `/app/backend/.env`:
- `MONGO_URL` - MongoDB connection string
- `DB_NAME` - Database name
- `JWT_SECRET_KEY` - JWT signing key
- `JWT_ALGORITHM` - JWT algorithm (default: HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES` - Token expiry (default: 30)

---
Last Updated: 2025-03

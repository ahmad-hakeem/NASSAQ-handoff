# NASSAQ Deployment Safety Policy

**Status: PERMANENT & NON-NEGOTIABLE**

## Core Rule

Production data must NEVER be lost, overwritten, or replaced during any deployment.

## Environment Separation

| Environment | Seed Scripts | Destructive Ops | Database |
|-------------|-------------|-----------------|----------|
| development | Allowed | Allowed | test_database |
| staging | BLOCKED | BLOCKED | staging DB |
| production | BLOCKED | BLOCKED | production DB |

## Safety Mechanisms

### 1. Seed Script Protection (`config.py`)
- `config.seed_allowed()` returns `False` for production and staging
- `server.py` startup checks this before running any seed operations
- All seed scripts in `backend/seeds/` are gated by environment

### 2. Destructive Operation Guard (`config.py`)
- `config.destructive_ops_allowed()` returns `False` for non-development
- Blocks: drop, delete, rename, remove, truncate, replace operations

### 3. Pre-Deployment Checklist (`config.py`)
- `config.deployment_checklist()` validates all safety requirements
- Runs automatically on startup; logs errors if checks fail
- Available via `GET /system/deployment-safety` endpoint (admin only)

### 4. Build Script Safety (`build.sh`)
- Validates JWT_SECRET_KEY is set in production
- Warns if DB_NAME is "test_database" in production
- Logs all safety check results

### 5. Startup Safety Logging (`server.py`)
- Logs environment, database name, seed status on every start
- Runs deployment checklist and logs failures in production

## Safe Migration Operations

**Allowed in production:**
- Add new fields to documents
- Add new collections
- Create indexes

**BLOCKED in production:**
- Drop collections/databases
- Delete data
- Rename fields without migration mapping
- Overwrite existing values
- Truncate collections

## Monitoring

- `GET /system/deployment-safety` — Full safety status (admin only)
- `GET /system/health` — Basic health check
- `GET /system/status` — System status with data counts

## Rollback

If unexpected behavior occurs after deployment:
1. Check `/system/deployment-safety` for data snapshot
2. Use Replit checkpoint rollback if needed
3. MongoDB data is persisted at `/home/runner/workspace/.mongodb/data`

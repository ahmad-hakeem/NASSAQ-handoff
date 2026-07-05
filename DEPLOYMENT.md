# NASSAQ — Self-Hosted Deployment Guide

NASSAQ ships as a single Docker image plus a Compose file. It runs on any
server with Docker and Docker Compose installed — no other software needed.

## What you received

| File | Purpose |
|---|---|
| `nassaq-app.tar.gz` | The application image |
| `docker-compose.yml` | Runs the app together with its PostgreSQL database |
| `.env.example` | Template for your configuration |
| `DEPLOYMENT.md` | This guide |

## 1. Load the image

```bash
docker load < nassaq-app.tar.gz
```

## 2. Configure

```bash
cp .env.example .env
```

Open `.env` and fill in every required value — each one is documented inline.
At minimum you must set:

- `POSTGRES_PASSWORD` — a strong database password
- `JWT_SECRET_KEY` and `MFA_ENCRYPTION_KEY` — generate with the commands shown in the file
- `CORS_ORIGINS` — the exact URL users will open in their browser
  (e.g. `https://nassaq.example.com` or `http://192.168.1.50:8000`)

## 3. First start (creates the admin accounts)

A fresh database is empty and account seeding is blocked in production mode,
so the very first start must run in bootstrap mode. In `.env`, set:

```
ENVIRONMENT=development
ADMIN_SEED_PASSWORD_ZALAT=<choose a strong password>
ADMIN_SEED_PASSWORD_HAKIM=<choose a strong password>
```

Then start everything:

```bash
docker compose up -d
```

The app applies its database migrations automatically, seeds the two
platform-administrator accounts, and serves on port 8000 (change with
`APP_PORT` in `.env`).

## 4. Switch to production mode

Edit `.env`: set `ENVIRONMENT=production` and blank out both
`ADMIN_SEED_PASSWORD_*` values. Then:

```bash
docker compose up -d --force-recreate app
```

Verify it is healthy:

```bash
curl http://localhost:8000/system/health
```

## 5. Log in

Open the app URL in a browser and sign in with one of the platform-admin
accounts created in step 3. From there you can create schools, principals,
teachers, students, and parents.

## Day-2 operations

- **Logs**: `docker compose logs -f app`
- **Restart**: `docker compose restart app`
- **Stop**: `docker compose down` (data is kept in the `nassaq_pgdata` volume)
- **Backup**: `docker compose exec db pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup.sql`
- **Upgrade**: load the new image, then `docker compose up -d --force-recreate app`
  (migrations run automatically at startup; they never delete existing data)

## Notes

- All data lives in the named Docker volume `nassaq_pgdata`. Deleting the
  containers does not delete the data; deleting the volume does.
- In production mode the app refuses destructive database operations and
  refuses to boot if configuration is incomplete — check
  `docker compose logs app` if it does not come up.
- For HTTPS, put any reverse proxy (nginx, Caddy, Traefik) in front of
  port 8000 and set `CORS_ORIGINS`/`FRONTEND_URL` to the https URL.

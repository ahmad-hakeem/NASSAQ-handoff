# ---------- Stage 1: build the React frontend ----------
FROM node:22-slim AS frontend-build
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --legacy-peer-deps
COPY frontend/ ./
# Never let dev-only flags leak into the production build
RUN rm -f .env .env.local .env.development && \
    GENERATE_SOURCEMAP=false DISABLE_ESLINT_PLUGIN=true npx craco build && \
    test -f build/index.html

# ---------- Stage 2: Python runtime ----------
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# Backend dependencies: union of pyproject.toml and backend/requirements.txt
COPY pyproject.toml ./
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache -r pyproject.toml -r backend/requirements.txt && \
    pip uninstall -y uv

# Backend source
COPY backend/ ./backend/

# Built frontend (FastAPI serves it from frontend/build, same origin)
COPY --from=frontend-build /fe/build ./frontend/build

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh && \
    useradd --create-home --uid 10001 nassaq && \
    chown -R nassaq:nassaq /app
USER nassaq

EXPOSE 8000
ENTRYPOINT ["/docker-entrypoint.sh"]

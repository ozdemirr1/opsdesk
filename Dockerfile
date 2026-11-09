FROM node:24-bookworm-slim AS frontend-build

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN VITE_API_BASE_URL=/ npm run build

FROM python:3.14.7-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

RUN python -m pip install --no-cache-dir uv==0.12.3

COPY pyproject.toml uv.lock .python-version ./
COPY src/ ./src/

RUN uv sync --locked --no-dev --no-editable --no-cache

COPY alembic.ini ./
COPY migrations/ ./migrations/
COPY --from=frontend-build /frontend/dist ./frontend/dist

ENV PATH="/app/.venv/bin:$PATH" \
    OPSDESK_FRONTEND_DIST_DIR="/app/frontend/dist"

RUN groupadd --gid 10001 opsdesk \
    && useradd --uid 10001 --gid opsdesk --no-create-home \
       --shell /usr/sbin/nologin opsdesk

USER 10001:10001

EXPOSE 8000

CMD ["uvicorn", "opsdesk.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

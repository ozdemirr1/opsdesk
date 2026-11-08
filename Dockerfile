FROM python:3.14.7-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

RUN python -m pip install --no-cache-dir uv==0.12.3

COPY pyproject.toml uv.lock .python-version ./
COPY src/ ./src/
COPY alembic.ini ./
COPY migrations/ ./migrations/

RUN uv sync --locked --no-dev --no-editable --no-cache

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "opsdesk.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

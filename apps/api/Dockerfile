FROM python:3.12-slim AS builder

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN python -m venv "$VIRTUAL_ENV"

WORKDIR /build
COPY pyproject.toml ./
COPY app ./app

RUN pip install --no-cache-dir .
RUN pip install "psycopg[binary]>=3.2,<4.0"  # TEMP: remove before commit, driver is not on main yet

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN addgroup --system --gid 10001 app \
    && adduser --system --uid 10001 --ingroup app app \
    && chown app:app /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder --chown=app:app /build/app ./app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8000') + '/health', timeout=4)"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

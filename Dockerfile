# Multi-stage Dockerfile for ReturnLens Demo packaging (Card B16)
FROM node:20-slim AS frontend-builder
WORKDIR /web
COPY app/web/package*.json ./
RUN npm install
COPY app/web ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    DEMO_TODAY=2026-11-11 \
    DEMO_SNAPSHOT=app/demo/snapshot/demo_cold_open.db \
    HARNESS_MODE=0

# Install minimal OS requirements
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy application code
COPY app/ ./app/
COPY --from=frontend-builder /web/dist ./app/web/dist

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

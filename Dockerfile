FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LIFEOS_STATIC_DIR=/app/frontend/dist
WORKDIR /app
COPY pyproject.toml ./
COPY backend/ ./backend/
RUN apt-get update && apt-get install --no-install-recommends -y util-linux && rm -rf /var/lib/apt/lists/* && pip install --no-cache-dir --upgrade pip==26.2.1 && pip install --no-cache-dir . && useradd --uid 10001 --create-home lifeos && mkdir /app/data && chown lifeos:lifeos /app/data
COPY --from=frontend /build/frontend/dist ./frontend/dist
COPY scripts/start-container.sh ./scripts/start-container.sh
RUN chmod 755 ./scripts/start-container.sh
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/ready', timeout=3)"
CMD ["./scripts/start-container.sh"]

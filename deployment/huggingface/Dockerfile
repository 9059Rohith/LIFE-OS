FROM node:22-bookworm-slim AS web
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
WORKDIR /app
COPY pyproject.toml ./
COPY backend/ ./backend/
RUN --mount=type=cache,target=/root/.cache/pip pip install .
COPY --from=web /build/frontend/dist ./frontend/dist
COPY deployment/huggingface/start.py ./start.py
RUN useradd --uid 1000 --create-home lifeos && mkdir -p /app/data && chown -R lifeos:lifeos /app
ENV HOME=/home/lifeos PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=7860
USER lifeos
EXPOSE 7860
CMD ["python", "start.py"]

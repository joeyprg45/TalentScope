# ── Stage 1: Build Next.js ──────────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

ENV NEXT_TELEMETRY_DISABLED=1
# 空文字にすることで /api/... への相対リクエストになり nginx が FastAPI へ転送する
ENV NEXT_PUBLIC_API_URL=""
RUN npm run build

# ── Stage 2: Runtime ────────────────────────────────────────────────────────
FROM python:3.12-slim

# nginx / supervisor / Node.js 20 をインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    supervisor \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Python 依存をインストール
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir uv \
    && uv pip install --system --no-cache-dir .

# Python アプリをコピー
COPY api/ ./api/
COPY agents/ ./agents/

# Next.js standalone をコピー
COPY --from=frontend-builder /frontend/.next/standalone/ ./frontend/
COPY --from=frontend-builder /frontend/.next/static/     ./frontend/.next/static/
COPY --from=frontend-builder /frontend/public/           ./frontend/public/

# 設定ファイルをコピー
COPY nginx.conf       /etc/nginx/nginx.conf
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost/api/health || exit 1

CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

# Django API, Celery worker and scheduler share this image (MTS v2.1 §14).

# The garment model pipeline (packages/asset-pipeline, decision 0007) runs on Node.js inside the worker.
FROM node:22-slim AS pipeline
RUN corepack enable
WORKDIR /src
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
COPY packages/asset-pipeline/package.json packages/asset-pipeline/
COPY packages/asset-pipeline/src packages/asset-pipeline/src
ENV npm_config_fetch_retries=10 \
    npm_config_fetch_retry_maxtimeout=120000 \
    npm_config_fetch_timeout=300000
RUN pnpm --filter @aurevon/asset-pipeline deploy --prod --legacy /out

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
RUN groupadd --system app && useradd --system --gid app --home /app app \
    && mkdir -p /media /media-private && chown app:app /media /media-private \
    && apt-get update && apt-get install -y --no-install-recommends libstdc++6 && rm -rf /var/lib/apt/lists/*
# /media: public product images; /media-private: 3D sources and drafts (compose volumes locally; S3 in production)

COPY backend/requirements.txt ./
# Generous retries and timeouts so slow or unstable connections finish instead of failing.
RUN pip install --retries 10 --timeout 120 -r requirements.txt

COPY --from=pipeline /usr/local/bin/node /usr/local/bin/node
COPY --from=pipeline /out /opt/asset-pipeline
ENV ASSET_PIPELINE=/opt/asset-pipeline/src/cli.mjs

COPY backend/ ./
USER app
EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]

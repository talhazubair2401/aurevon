# Django API, Celery worker and scheduler share this image (MTS v2.1 §14).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
RUN groupadd --system app && useradd --system --gid app --home /app app

COPY backend/requirements.txt ./
# Generous retries and timeouts so slow or unstable connections finish instead of failing.
RUN pip install --retries 10 --timeout 120 -r requirements.txt

COPY backend/ ./
USER app
EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]

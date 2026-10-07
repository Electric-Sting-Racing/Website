FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Build static assets into the image; migrations run as a separate release step.
RUN DJANGO_DEBUG=True \
    DJANGO_SECRET_KEY=build-only-secret \
    DB_ENGINE=sqlite \
    python manage.py collectstatic --noinput

RUN addgroup --system app \
    && adduser --system --ingroup app app \
    && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; request = urllib.request.Request('http://127.0.0.1:8000/healthz/', headers={'Host': '127.0.0.1', 'X-Forwarded-Proto': 'https'}); urllib.request.urlopen(request, timeout=3)"

CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:8000 --workers ${WEB_CONCURRENCY:-3} --access-logfile - --error-logfile - fsae_site.wsgi:application"]

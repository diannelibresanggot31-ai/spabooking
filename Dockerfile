FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y libpq5 libjpeg62-turbo-dev zlib1g-dev && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir setuptools==65.5.0

COPY requirements.txt .
# Copy and install extra requirements for deployment if present
COPY requirements-extra.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN if [ -f requirements-extra.txt ]; then pip install --no-cache-dir -r requirements-extra.txt; fi

COPY . .

RUN mkdir -p /app/static

# ✅ FORCE COPY TEMPLATES
COPY templates/ /app/templates/

# ✅ VERIFY TEMPLATES ARE THERE (this runs during Docker build)
RUN ls -la /app/templates/admin/ || true
RUN ls -la /app/static || true

RUN python manage.py collectstatic --noinput
RUN python manage.py migrate --noinput

CMD ["gunicorn", "spa_booking.wsgi:application", "--bind", "0.0.0.0:10000"]
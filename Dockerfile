FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# libpq-dev needed to build psycopg2; libjpeg/zlib for Pillow
RUN apt-get update && apt-get install -y \
    libpq-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY requirements-extra.txt .

RUN pip install --no-cache-dir -r requirements.txt
RUN if [ -f requirements-extra.txt ]; then pip install --no-cache-dir -r requirements-extra.txt; fi

COPY . .

RUN mkdir -p /app/static /app/media

RUN python manage.py collectstatic --noinput
RUN python manage.py migrate --noinput

CMD ["gunicorn", "spa_booking.wsgi:application", "--bind", "0.0.0.0:10000"]
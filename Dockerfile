FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=${DATABASE_URL}

WORKDIR /app

# Install setuptools first
RUN pip install --no-cache-dir setuptools==65.5.0

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run migrations at startup
RUN python manage.py migrate --noinput

CMD ["gunicorn", "spa_booking.wsgi:application", "--bind", "0.0.0.0:10000"]
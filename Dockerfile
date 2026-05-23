FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y libpq5 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir setuptools==65.5.0

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application code
COPY . .

# DEBUG: List template files to verify they exist in the container
RUN echo "Checking templates/admin directory:" && ls -la /app/templates/admin/

# Run migrations
RUN python manage.py migrate --noinput

CMD ["gunicorn", "spa_booking.wsgi:application", "--bind", "0.0.0.0:10000"]
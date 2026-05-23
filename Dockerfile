FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install setuptools FIRST and PIN it
RUN pip install --no-cache-dir setuptools==65.5.0

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "spa_booking.wsgi:application", "--bind", "0.0.0.0:10000"]
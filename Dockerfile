FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

RUN mkdir -p logs

# WSGI giris noktasi (Faz 7/Faz 8b: gunicorn threaded calisma modu)
# Tek process + coklu thread: SSE stream baglantilarinin worker kilitlemesini onler
# ve bellek-ici tekil NotificationBroker ile EventSource abonelerini tek havuzda bulusturur.
CMD ["gunicorn", "-w", "1", "--threads", "32", "-b", "0.0.0.0:8000", "kervansaray.wsgi:app"]


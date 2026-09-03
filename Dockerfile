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

# Uygulama giris noktasi (ingest API + panel + tool katmani) henuz yazilmadi.
# Bkz. docs/PROJECT_BRIEF.md S15.
CMD ["python", "-c", "import kervansaray; print('kervansaray', kervansaray.__version__, '- giris noktasi bekleniyor')"]

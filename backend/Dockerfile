FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl libgl1 libglib2.0-0 libzbar0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

HEALTHCHECK --interval=15s --timeout=5s --retries=4 CMD curl -fsS http://localhost:8000/health/live || exit 1

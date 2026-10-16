FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
# pgserver (embedded dev database) is not needed in containers
RUN grep -v '^pgserver' requirements.txt > req.txt && pip install --no-cache-dir -r req.txt
COPY app ./app
COPY wg_core ./wg_core
COPY worker ./worker
COPY scripts ./scripts
COPY config ./config
EXPOSE 8000
# --no-access-log: request URLs (e.g. the OAuth callback code) never reach the logs
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

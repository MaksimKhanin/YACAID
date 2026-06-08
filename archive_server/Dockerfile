# Build from the repo root: docker build -f archive_server/Dockerfile .
FROM python:3.12-slim

# opencv (used for thumbnail generation) needs these shared libs even in headless mode
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-archive-server.txt .
RUN pip install --no-cache-dir -r requirements-archive-server.txt

COPY logger_setup.py .
COPY archive_server ./archive_server

EXPOSE 8000
CMD ["uvicorn", "archive_server.main:app", "--host", "0.0.0.0", "--port", "8000"]

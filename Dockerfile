# Single image for the whole app — the API and the Streamlit dashboard share the
# same code and dependencies; docker-compose (or your cloud service) picks the
# start command per service. Honors $PORT so it drops straight into Cloud Run /
# Render / Railway / Fly.io style container services.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default command = API. Cloud services set $PORT; locally it falls back to 8000.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

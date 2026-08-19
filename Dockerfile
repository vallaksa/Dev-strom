# Dev-Strom application image.
#
# Shared by both the `api` (FastAPI/uvicorn) and `ui` (Streamlit) services in
# docker-compose.yml - they use the same image with different `command`s, so
# the full app is baked in once and each service just picks its entrypoint.
FROM python:3.12-slim

# Fail fast, keep image lean, don't buffer logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps needed to build psycopg2-binary / pgvector wheels on slim images.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first so this layer is cached across code-only changes.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Now bring in the application code.
COPY app ./app
COPY ui ./ui
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini

EXPOSE 8000

# Default: run the FastAPI server. The `ui` service in docker-compose.yml
# overrides this command to run Streamlit instead.
CMD ["uvicorn", "app.api:api", "--host", "0.0.0.0", "--port", "8000"]

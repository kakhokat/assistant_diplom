FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# системные зависимости для сборки колёс (asyncpg, bcrypt)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# зависимости
COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY requirements-dev.txt ./requirements-dev.txt
RUN pip install -r requirements-dev.txt \
    && pip install gunicorn==23.0.0

# КОПИРУЕМ КОНФИГ GUNICORN И OPENAPI
COPY gunicorn.conf.py ./gunicorn.conf.py
COPY openapi.yaml ./openapi.yaml

# копируем исходники
COPY src ./src
COPY pyproject.toml ./pyproject.toml

EXPOSE 8000

CMD ["gunicorn", "main:app", "-k", "uvicorn.workers.UvicornWorker", \
     "-c", "gunicorn.conf.py", "--chdir", "src"]

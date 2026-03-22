FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# system deps for building wheels (orjson, elastic)
RUN apt-get update && apt-get install -y \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# copy and install
COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# dev-зависимости тоже внутрь
COPY requirements-dev.txt ./requirements-dev.txt
RUN pip install -r requirements-dev.txt \
    && pip install gunicorn==23.0.0

# положим тесты и конфиги pytest в образ
COPY tests ./tests
COPY pytest.ini ./pytest.ini
COPY pyproject.toml ./pyproject.toml

# copy данные
COPY scripts ./scripts
COPY data ./data
# copy source
COPY src ./src
COPY .env.example ./.env.example
COPY gunicorn.conf.py ./gunicorn.conf.py

EXPOSE 8000
CMD ["gunicorn", "main:app", "-k", "uvicorn.workers.UvicornWorker", \
     "-c", "gunicorn.conf.py", "--chdir", "src"]

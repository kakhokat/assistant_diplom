FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1     PYTHONDONTWRITEBYTECODE=1     PIP_NO_CACHE_DIR=1     PYTHONPATH=/app/src

WORKDIR /app

RUN apt-get update && apt-get install -y     build-essential curl &&     rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY requirements-dev.txt ./requirements-dev.txt
RUN pip install -r requirements-dev.txt     && pip install gunicorn==23.0.0

COPY gunicorn.conf.py ./gunicorn.conf.py
COPY pytest.ini ./pytest.ini
COPY src ./src
COPY tests ./tests

EXPOSE 8003
CMD ["gunicorn", "main:app", "-k", "uvicorn.workers.UvicornWorker", "-c", "gunicorn.conf.py", "--chdir", "src"]

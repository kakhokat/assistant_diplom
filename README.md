# Ассистент для киносервиса

Это проект киносервиса с несколькими отдельными сервисами и веб-демо. В репозитории есть:

- авторизация пользователей;
- каталог фильмов, персон и жанров с поиском;
- пользовательские действия: закладки, лайки, отзывы;
- ассистент, который отвечает на вопросы о фильмах и умеет использовать данные пользователя после входа в систему;
- фронтенд-демо, через которое можно проверить основные сценарии.

Проект запускается через Docker Compose. Снаружи публикуется только один адрес: `http://localhost`.

## Что умеет проект

После запуска доступны такие сценарии:

- регистрация и вход пользователя;
- просмотр каталога фильмов;
- поиск фильмов, персон и жанров;
- просмотр Swagger для сервисов;
- добавление закладок, лайков и отзывов;
- запросы к ассистенту через API и через демо-интерфейс.

Ассистент умеет отвечать, например, на такие вопросы:

- какая оценка у фильма;
- кто снял фильм;
- сколько длится фильм;
- какие жанры у фильма;
- какие фильмы есть у выбранного человека;
- что у меня в закладках;
- посоветуй фильм;
- посоветуй фильмы жанра ...;
- посоветуй по моим любимым жанрам.

Примеры запросов лежат в `services/frontend_demo/site/demo-config.json`.

## Состав проекта

### 1. `auth_api`
Сервис авторизации. Отвечает за регистрацию, вход, refresh/logout, профиль пользователя и роли.

Зависимости:
- PostgreSQL
- Redis
- Jaeger

### 2. `async_api`
Сервис каталога и поиска. Отдаёт фильмы, жанры, персон, списки и результаты поиска.

Зависимости:
- Elasticsearch
- Redis
- внутренний nginx для проксирования

### 3. `ugc_api`
Сервис пользовательских действий. Работает с закладками, лайками и отзывами.

Зависимости:
- MongoDB
- внутренний nginx

### 4. `assistant_api`
Сервис ассистента. Принимает вопрос, вызывает нужные сервисы и собирает итоговый ответ.

Дополнительно использует:
- Redis для сессий и кэша
- опционально Ollama для локального LLM fallback

### 5. `frontend_demo`
Небольшой веб-интерфейс для проверки проекта в браузере.

### 6. `gateway_nginx`
Единая публичная точка входа. Через него открываются фронтенд и API остальных сервисов.

## Структура репозитория

```text
.
├── docker-compose.yml
├── gateway/
├── scripts/
└── services/
    ├── auth/
    ├── async_api/
    ├── ugc/
    ├── assistant/
    └── frontend_demo/
```

## Запуск

Из корня проекта:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

docker compose down -v --remove-orphans --rmi local
docker builder prune -af

docker compose build --no-cache
docker compose up -d
```

Проверить, что контейнеры поднялись:

```powershell
docker compose ps
```

## Подготовка демо

### 1. Подтянуть локальную модель для ассистента

```powershell
.\scripts\llm-setup-ollama.ps1
```

### 2. Сгенерировать каталог

```powershell
.\scripts\generate-catalog-dataset.ps1
```

Пример с большим объёмом данных:

```powershell
.\scripts\generate-catalog-dataset.ps1 -Films 100000 -ChunkSize 5000
```

### 3. Подготовить демо-пользователя

```powershell
.\scripts\prepare-demo-user.ps1
```

Скрипт залогинит пользователя, добавит ему закладки и лайки и выведет готовые данные для демонстрации персональных сценариев.

## Полезные адреса

После запуска проект доступен по адресу `http://localhost`.

Основные маршруты:

- фронтенд: `http://localhost/`
- gateway health: `http://localhost/_health`
- auth: `http://localhost/api/v1/auth/...`
- каталог Swagger: `http://localhost/api/openapi`
- каталог OpenAPI: `http://localhost/api/openapi.json`
- UGC Swagger: `http://localhost/ugc/docs`
- UGC OpenAPI: `http://localhost/ugc/openapi.json`
- assistant Swagger: `http://localhost/assistant/docs`
- assistant OpenAPI: `http://localhost/assistant/openapi.json`
- endpoint ассистента: `POST http://localhost/assistant/api/v1/ask`

## Проверка проекта

Полная проверка:

```powershell
.\scripts\check-all.ps1
```

Поштучно:

```powershell
.\scripts\check-01-infra.ps1
.\scripts\check-02-auth.ps1
.\scripts\check-03-async-api.ps1
.\scripts\check-04-ugc.ps1
.\scripts\check-05-assistant.ps1
.\scripts\check-06-logs.ps1
.\scripts\check-07-secrets.ps1
.\scripts\check-08-security.ps1
```

## Проверка ассистента отдельно

```powershell
cd .\services\assistant

py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
pip install black isort flake8 pytest-asyncio

pytest -q
black --check src tests
isort --check-only src tests
flake8 src tests --max-line-length=88
```

## Как устроен демо-сценарий

Обычный порядок показа такой:

1. Открыть главную страницу.
2. Показать каталог и поиск.
3. Задать ассистенту несколько общих вопросов про фильмы.
4. Войти под демо-пользователем.
5. Повторить запрос про закладки.
6. Попросить рекомендацию по любимым жанрам.

Так удобно показать и публичные, и персональные сценарии.

## Что лежит в `scripts/`

В корне есть PowerShell-скрипты для типовых действий:

- поднятие и проверка проекта;
- генерация каталога;
- подготовка демо-пользователя;
- запуск Ollama;
- проверки логов, секретов и базовых security-настроек;
- очистка временных файлов.

## Ограничения текущей версии

- история просмотров не хранится;
- рекомендации строятся на основе доступных данных каталога, закладок и лайков, нет событийной аналитики;
- локальная LLM-модель для ассистента необязательна: базовые сценарии работают и без неё.

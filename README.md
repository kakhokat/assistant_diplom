# Cinema platform (assistant-ready, prod-like core)

This repository contains the **cleaned prod-like core** of the cinema platform together with a thin `assistant_api` service for assistant scenarios.

Included services:
- Auth (`auth_api` + Postgres + Redis + Jaeger)
- Catalog/Search (`async_api` + Elasticsearch + Redis + internal nginx + `es_init`)
- UGC CRUD (`ugc_api` + MongoDB + internal nginx)
- Gateway (`gateway_nginx`) as the only public entrypoint
- Assistant (`assistant_api`) as a thin orchestration layer over Auth / Catalog / UGC
- Optional local LLM fallback for better NLU (`ollama`, profile `llm`)

Removed from the final demo contour:
- Admin panel + admin ETL
- Notifications + RabbitMQ + worker + MailHog
- UGC event analytics pipeline (Kafka / ZooKeeper / ClickHouse / ETL / producer API)

## Why this architecture

The final contour keeps only the services that are directly needed for:
- assistant-ready catalog queries;
- assistant question answering and simple personalized recommendations;
- authentication and protected endpoints;
- user context (likes, bookmarks, reviews);
- local debugging and demo through a single gateway.

The removed services are useful for the full product, but they are not required for the assistant MVP, regression, or defense demo.

## Public routes

Only one host port is published: `http://localhost` (port `80`).

Routes:
- Auth: `http://localhost/api/v1/auth/...`
- Catalog / Async API Swagger: `http://localhost/api/openapi`
- Catalog / Async API OpenAPI: `http://localhost/api/openapi.json`
- Catalog endpoints: `http://localhost/api/v1/...`
- UGC Swagger: `http://localhost/ugc/docs`
- UGC OpenAPI: `http://localhost/ugc/openapi.json`
- UGC endpoints: `http://localhost/ugc/...`
- Gateway health: `http://localhost/_health`
- UGC health via gateway: `http://localhost/health`
- Assistant Swagger: `http://localhost/assistant/docs`
- Assistant OpenAPI: `http://localhost/assistant/openapi.json`
- Assistant endpoint: `POST http://localhost/assistant/api/v1/ask`

## Local env files

Runtime values are read from:
- root `.env`
- `services/auth/.env`
- `services/ugc/.env`
- `services/async_api/.env`
- `services/assistant/.env`

Templates are stored in:
- `.env.example`
- `services/auth/.env.example`
- `services/ugc/.env.example`
- `services/async_api/.env.example`
- `services/assistant/.env.example`

## Fresh start (recommended)

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

docker compose down -v --remove-orphans
docker compose up -d --build
```

## Check containers and recent logs

```powershell
docker compose ps
docker compose logs -n 120 gateway_nginx
docker compose logs -n 120 auth_api async_api ugc_api assistant_api
```

## Run full regression

```powershell
.\scripts\check-all.ps1
```

## Run checks one by one

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

## Manual browser checks for defense

Open:
- `http://localhost/api/openapi`
- `http://localhost/ugc/docs`
- `http://localhost/_health`
- `http://localhost/assistant/docs`

Expected:
- Async API Swagger loads through the gateway
- UGC Swagger loads under `/ugc`
- Assistant Swagger loads under `/assistant`
- only gateway publishes host port `80`

## Assistant API

`assistant_api` is implemented as a thin orchestration layer. It does not store domain data itself; instead, it calls existing platform services.

Supported demo scenarios:
- film rating
- film director
- film duration
- film genres
- person filmography
- my bookmarks
- simple recommendations by favorite genres

Current limitation:
- watch history is not stored yet, so requests like “recommend films with actor X that I have not watched yet” are answered with that limitation explicitly.


## Optional local LLM fallback

The assistant now supports a hybrid NLU flow:
- deterministic parser for stable contract scenarios;
- optional local LLM fallback for free-form phrasing, transliterated titles, and softer recommendation queries.

By default, the platform runs with `ASSISTANT_LLM_ENABLED=false`, so regression stays deterministic.
To enable the local model:

```powershell
.\scripts\llm-setup-ollama.ps1
```

Then set `ASSISTANT_LLM_ENABLED=true` in `services/assistant/.env` and restart `assistant_api`.

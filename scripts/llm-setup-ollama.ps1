$ErrorActionPreference = "Stop"

Write-Host "Starting Ollama service..." -ForegroundColor Cyan
docker compose up -d ollama

Write-Host "Pulling local model qwen2.5:3b-instruct into Ollama..." -ForegroundColor Cyan
docker compose exec ollama ollama pull qwen2.5:3b-instruct

Write-Host "Restarting assistant_api with LLM enabled..." -ForegroundColor Cyan
docker compose up -d assistant_api

Write-Host "Local LLM is ready and assistant_api has been restarted." -ForegroundColor Green

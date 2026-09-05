# Docker Management Commands for SpectechPlatform
# Usage: .\scripts\docker-commands.ps1 [command]

param(
    [Parameter(Position=0)]
    [ValidateSet(
        "dev-up", "dev-down", "dev-logs", "dev-restart",
        "prod-build", "prod-up", "prod-down", "prod-logs", "prod-restart",
        "status", "clean", "help"
    )]
    [string]$Command = "help"
)

function Show-Help {
    Write-Host "SpectechPlatform Docker Commands" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "DEVELOPMENT:" -ForegroundColor Yellow
    Write-Host "  dev-up       Start development environment"
    Write-Host "  dev-down     Stop development environment"
    Write-Host "  dev-logs     View development logs"
    Write-Host "  dev-restart  Restart development environment"
    Write-Host ""
    Write-Host "PRODUCTION:" -ForegroundColor Yellow
    Write-Host "  prod-build   Build production images"
    Write-Host "  prod-up      Start production environment"
    Write-Host "  prod-down    Stop production environment"
    Write-Host "  prod-logs    View production logs"
    Write-Host "  prod-restart Restart production environment"
    Write-Host ""
    Write-Host "UTILS:" -ForegroundColor Yellow
    Write-Host "  status       Show running containers"
    Write-Host "  clean        Remove all containers and volumes"
    Write-Host "  help         Show this help"
}

switch ($Command) {
    "dev-up" {
        Write-Host "Starting development environment..." -ForegroundColor Green
        docker-compose -f docker-compose.dev.yaml up -d
    }
    "dev-down" {
        Write-Host "Stopping development environment..." -ForegroundColor Yellow
        docker-compose -f docker-compose.dev.yaml down
    }
    "dev-logs" {
        docker-compose -f docker-compose.dev.yaml logs -f
    }
    "dev-restart" {
        Write-Host "Restarting development environment..." -ForegroundColor Cyan
        docker-compose -f docker-compose.dev.yaml down
        docker-compose -f docker-compose.dev.yaml up -d
    }
    "prod-build" {
        Write-Host "Building production images..." -ForegroundColor Green
        cd backend
        docker build -t spectech-backend:latest .
        cd ..
    }
    "prod-up" {
        Write-Host "Starting production environment..." -ForegroundColor Green
        docker-compose -f docker-compose.prod.yaml --env-file .env.prod up -d
    }
    "prod-down" {
        Write-Host "Stopping production environment..." -ForegroundColor Yellow
        docker-compose -f docker-compose.prod.yaml --env-file .env.prod down
    }
    "prod-logs" {
        docker-compose -f docker-compose.prod.yaml --env-file .env.prod logs -f
    }
    "prod-restart" {
        Write-Host "Restarting production environment..." -ForegroundColor Cyan
        docker-compose -f docker-compose.prod.yaml --env-file .env.prod down
        docker-compose -f docker-compose.prod.yaml --env-file .env.prod up -d
    }
    "status" {
        Write-Host "Container Status:" -ForegroundColor Cyan
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    }
    "clean" {
        Write-Host "Cleaning all containers and volumes..." -ForegroundColor Red
        docker-compose -f docker-compose.dev.yaml down -v
        docker-compose -f docker-compose.prod.yaml --env-file .env.prod down -v
        docker system prune -f
    }
    default {
        Show-Help
    }
}

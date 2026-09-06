# Database Restore Script
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\restore-db.ps1 -File backups/spectech-db-20260906-120000.sql

param(
    [Parameter(Mandatory=$true)]
    [string]$File
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SpectechPlatform Database Restore" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $File)) {
    Write-Host "ERROR: Backup file not found: $File" -ForegroundColor Red
    exit 1
}

Write-Host "WARNING: This will OVERWRITE the current database!" -ForegroundColor Yellow
Write-Host "File to restore: $File" -ForegroundColor Yellow
$confirm = Read-Host "Are you sure you want to continue? (yes/no)"

if ($confirm -ne "yes") {
    Write-Host "Restore cancelled." -ForegroundColor Yellow
    exit 0
}

# Check if postgres container is running
$postgresRunning = docker ps --format "{{.Names}}" | Select-String "spectech-postgres"
if (-not $postgresRunning) {
    Write-Host "ERROR: spectech-postgres container is not running!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[1/3] Stopping backend service..." -ForegroundColor Yellow
docker-compose -f docker-compose.prod.yaml --env-file .env.prod stop backend

Write-Host "[2/3] Copying backup to container..." -ForegroundColor Yellow
docker cp $File spectech-postgres:/tmp/restore.sql

Write-Host "[3/3] Restoring database..." -ForegroundColor Yellow
docker exec spectech-postgres psql -U spectech -d spectech -f /tmp/restore.sql
docker exec spectech-postgres rm /tmp/restore.sql

Write-Host ""
Write-Host "Starting backend service..." -ForegroundColor Yellow
docker-compose -f docker-compose.prod.yaml --env-file .env.prod start backend

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Restore successful!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

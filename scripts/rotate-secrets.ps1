# Secret Rotation Script
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\rotate-secrets.ps1

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SpectechPlatform Secret Rotation" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env.prod exists
$envFile = ".env.prod"
if (-not (Test-Path $envFile)) {
    Write-Host "ERROR: .env.prod not found in current directory!" -ForegroundColor Red
    Write-Host "Please run this script from the project root." -ForegroundColor Yellow
    exit 1
}

# Backup current .env.prod
$backupFile = ".env.prod.backup.$(Get-Date -Format 'yyyyMMdd-HHmmss')"
Copy-Item $envFile $backupFile
Write-Host "[1/5] Backup created: $backupFile" -ForegroundColor Green

# Generate new secrets
function New-RandomSecret {
    param([int]$Length = 64)
    $chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-!@#$%^&*"
    -join (1..$Length | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })
}

$newPostgresPassword = New-RandomSecret 32
$newJwtSecret = New-RandomSecret 64
$newRedisPassword = New-RandomSecret 32
$newMinioPassword = New-RandomSecret 32
$newGrafanaPassword = New-RandomSecret 16

Write-Host "[2/5] New secrets generated" -ForegroundColor Green

# Update .env.prod
$content = Get-Content $envFile
$content = $content -replace 'POSTGRES_PASSWORD=.*', "POSTGRES_PASSWORD=$newPostgresPassword"
$content = $content -replace 'JWT_SECRET_KEY=.*', "JWT_SECRET_KEY=$newJwtSecret"
$content = $content -replace 'REDIS_PASSWORD=.*', "REDIS_PASSWORD=$newRedisPassword"
$content = $content -replace 'MINIO_ROOT_PASSWORD=.*', "MINIO_ROOT_PASSWORD=$newMinioPassword"
$content = $content -replace 'GRAFANA_PASSWORD=.*', "GRAFANA_PASSWORD=$newGrafanaPassword"
$content | Set-Content $envFile

Write-Host "[3/5] .env.prod updated" -ForegroundColor Green

# Update PostgreSQL password
Write-Host "[4/5] Updating PostgreSQL password..." -ForegroundColor Yellow
try {
    $result = docker exec spectech-postgres psql -U spectech -d spectech -c "ALTER USER spectech WITH PASSWORD '$newPostgresPassword';" 2>&1
    if ($result -match "ALTER ROLE") {
        Write-Host "  -> PostgreSQL password updated" -ForegroundColor Green
    } else {
        Write-Host "  -> WARNING: PostgreSQL might not be running" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  -> WARNING: Could not connect to PostgreSQL" -ForegroundColor Yellow
}

# Restart services
Write-Host "[5/5] Restarting services..." -ForegroundColor Yellow
docker-compose -f docker-compose.prod.yaml --env-file .env.prod up -d --force-recreate

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Secrets rotated successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "New credentials:" -ForegroundColor Cyan
Write-Host "  POSTGRES_PASSWORD: $newPostgresPassword"
Write-Host "  JWT_SECRET_KEY:    $newJwtSecret"
Write-Host "  REDIS_PASSWORD:    $newRedisPassword"
Write-Host "  MINIO_PASSWORD:    $newMinioPassword"
Write-Host "  GRAFANA_PASSWORD:  $newGrafanaPassword"
Write-Host ""
Write-Host "Backup saved to: $backupFile" -ForegroundColor Yellow
Write-Host "IMPORTANT: Save these credentials in a secure location!" -ForegroundColor Red

# Database Backup Script
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\backup-db.ps1

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SpectechPlatform Database Backup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Create backups directory if not exists
$backupDir = "backups"
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir | Out-Null
    Write-Host "[1/3] Created backups directory" -ForegroundColor Green
}

# Generate filename with timestamp
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupFile = "$backupDir/spectech-db-$timestamp.sql"

# Check if postgres container is running
$postgresRunning = docker ps --format "{{.Names}}" | Select-String "spectech-postgres"
if (-not $postgresRunning) {
    Write-Host "ERROR: spectech-postgres container is not running!" -ForegroundColor Red
    Write-Host "Start it with: docker-compose -f docker-compose.prod.yaml up -d postgres" -ForegroundColor Yellow
    exit 1
}

Write-Host "[2/3] Creating database dump..." -ForegroundColor Yellow
docker exec spectech-postgres pg_dump -U spectech -d spectech --clean --if-exists -F p -f /tmp/backup.sql

# Copy from container to host
docker cp spectech-postgres:/tmp/backup.sql $backupFile
docker exec spectech-postgres rm /tmp/backup.sql

$size = (Get-Item $backupFile).Length / 1KB
Write-Host "[3/3] Backup completed: $backupFile ($([math]::Round($size, 2)) KB)" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Backup successful!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "To restore, run:" -ForegroundColor Cyan
Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\restore-db.ps1 -File $backupFile" -ForegroundColor White
Write-Host ""

# List recent backups
Write-Host "Recent backups:" -ForegroundColor Yellow
Get-ChildItem $backupDir -Filter "*.sql" | Sort-Object LastWriteTime -Descending | Select-Object -First 5 | ForEach-Object {
    Write-Host "  $($_.Name) - $([math]::Round($_.Length / 1KB, 2)) KB" -ForegroundColor Gray
}

# Auto-cleanup: keep only last 30 backups
$keepCount = 30
$allBackups = Get-ChildItem $backupDir -Filter "*.sql" | Sort-Object LastWriteTime -Descending
if ($allBackups.Count -gt $keepCount) {
    $toDelete = $allBackups | Select-Object -Skip $keepCount
    foreach ($old in $toDelete) {
        Remove-Item $old.FullName -Force
        Write-Host "  Deleted old backup: $($old.Name)" -ForegroundColor DarkGray
    }
    Write-Host "Cleanup: removed $($toDelete.Count) old backups, kept $keepCount" -ForegroundColor Yellow
}

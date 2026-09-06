# Locust Load Test Runner
# Usage: .\scripts\run-load-test.ps1 [users] [spawn-rate] [duration]

param(
    [int]$Users = 50,
    [int]$SpawnRate = 10,
    [int]$Duration = 60,
    [string]$Host = "http://localhost:8000"
)

Write-Host "Starting Locust load test..." -ForegroundColor Cyan
Write-Host "  Users: $Users" -ForegroundColor Yellow
Write-Host "  Spawn rate: $SpawnRate users/sec" -ForegroundColor Yellow
Write-Host "  Duration: $Duration seconds" -ForegroundColor Yellow
Write-Host "  Target: $Host" -ForegroundColor Yellow
Write-Host ""

cd $PSScriptRoot\..\load_tests

# Запуск Locust в headless режиме
locust `
    --headless `
    --users $Users `
    --spawn-rate $SpawnRate `
    --run-time "${Duration}s" `
    --host $Host `
    --csv=results `
    --html=report.html

Write-Host "`nLoad test complete!" -ForegroundColor Green
Write-Host "  CSV results: load_tests/results*.csv" -ForegroundColor Yellow
Write-Host "  HTML report: load_tests/report.html" -ForegroundColor Yellow

# Открываем отчёт
Start-Process "report.html"

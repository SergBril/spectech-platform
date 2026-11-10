#!/usr/bin/env pwsh
# Run Locust load tests
# Usage: ./scripts/run-locust.ps1 [-Headless] [-Users 50] [-SpawnRate 5] [-Duration 60]

param(
    [switch]$Headless = $true,
    [int]$Users = 20,
    [int]$SpawnRate = 5,
    [int]$Duration = 60,
    [string]$Host = "http://localhost:8000"
)

$env:PYTHONIOENCODING = "utf-8"
Set-Location $PSScriptRoot/../load_tests

if ($Headless) {
    Write-Host "Running headless: $Users users, ${SpawnRate}/s spawn, ${Duration}s duration"
    python -m locust -f locustfile.py --headless --users $Users --spawn-rate $SpawnRate --run-time "${Duration}s" --host $Host
} else {
    Write-Host "Starting Locust UI at http://localhost:8089"
    python -m locust -f locustfile.py --host $Host
}

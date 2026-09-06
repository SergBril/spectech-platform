# Coverage Report Viewer
# Usage: .\scripts\view-coverage.ps1

Write-Host "Running tests with coverage..." -ForegroundColor Cyan
cd backend
pytest tests/ --cov=app --cov-report=html --cov-report=term-missing -q

if (Test-Path "htmlcov\index.html") {
    Write-Host "`nOpening coverage report in browser..." -ForegroundColor Green
    Start-Process "htmlcov\index.html"

    Write-Host "`nCoverage Summary:" -ForegroundColor Yellow
    Get-Content "htmlcov\index.html" | Select-String -Pattern "pc_cov" | ForEach-Object {
        if ($_ -match '(\d+)%') {
            $percent = [int]$matches[1]
            $color = if ($percent -ge 80) { "Green" } elseif ($percent -ge 60) { "Yellow" } else { "Red" }
            Write-Host "  Total coverage: $percent%" -ForegroundColor $color
        }
    }
} else {
    Write-Host "Error: Coverage report not generated" -ForegroundColor Red
}

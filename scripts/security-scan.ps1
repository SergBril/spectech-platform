# Security Scan Script
# Usage: .\scripts\security-scan.ps1

Write-Host "Starting security scan..." -ForegroundColor Cyan

# Scan backend image
Write-Host "`n[1/3] Scanning spectech-backend image..." -ForegroundColor Yellow
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image --severity HIGH,CRITICAL spectech-backend:latest

# Scan frontend image (if exists)
Write-Host "`n[2/3] Scanning spectech-platform-frontend image..." -ForegroundColor Yellow
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image --severity HIGH,CRITICAL spectech-platform-frontend:latest 2>$null

# Scan filesystem for secrets
Write-Host "`n[3/3] Scanning filesystem for secrets..." -ForegroundColor Yellow
cd backend
detect-secrets scan --all-files . | Out-File ..\security-scan-results.json

Write-Host "`nScan complete!" -ForegroundColor Green
Write-Host "Results saved to: security-scan-results.json" -ForegroundColor Gray

# Install cloudflared for Windows
# Usage: .\scripts\install-cloudflared.ps1

$version = "2026.8.3"
$url = "https://github.com/cloudflare/cloudflared/releases/download/$version/cloudflared-windows-amd64.msi"
$output = "$env:TEMP\cloudflared.msi"

Write-Host "Downloading cloudflared $version..." -ForegroundColor Green
Invoke-WebRequest -Uri $url -OutFile $output

Write-Host "Installing cloudflared..." -ForegroundColor Green
Start-Process msiexec.exe -ArgumentList "/i `"$output`" /quiet /norestart" -Wait

Write-Host "cloudflared installed successfully!" -ForegroundColor Green
cloudflared --version

Remove-Item $output

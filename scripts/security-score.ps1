# Security Headers Scoring Script (Mozilla Observatory style)
# Usage: .\scripts\security-score.ps1

$url = "https://localhost/api/v1/system/health"
Write-Host "🔍 Scanning security headers: $url" -ForegroundColor Cyan

$headers = curl -k -I -s $url
$score = 0
$maxScore = 100

Write-Host "`n📊 Security Headers Analysis:" -ForegroundColor Yellow
Write-Host ("=" * 60)

# HSTS (25 points)
if ($headers -match "Strict-Transport-Security") {
    Write-Host "✅ HSTS: Present" -ForegroundColor Green
    $score += 25
} else {
    Write-Host "❌ HSTS: Missing (CRITICAL)" -ForegroundColor Red
}

# Content-Security-Policy (25 points)
if ($headers -match "Content-Security-Policy") {
    Write-Host "✅ CSP: Present" -ForegroundColor Green
    $score += 25
} else {
    Write-Host "❌ CSP: Missing (CRITICAL)" -ForegroundColor Red
}

# X-Frame-Options (10 points)
if ($headers -match "X-Frame-Options") {
    Write-Host "✅ X-Frame-Options: Present" -ForegroundColor Green
    $score += 10
} else {
    Write-Host "❌ X-Frame-Options: Missing" -ForegroundColor Red
}

# X-Content-Type-Options (10 points)
if ($headers -match "X-Content-Type-Options") {
    Write-Host "✅ X-Content-Type-Options: Present" -ForegroundColor Green
    $score += 10
} else {
    Write-Host "❌ X-Content-Type-Options: Missing" -ForegroundColor Red
}

# Referrer-Policy (10 points)
if ($headers -match "Referrer-Policy") {
    Write-Host "✅ Referrer-Policy: Present" -ForegroundColor Green
    $score += 10
} else {
    Write-Host "❌ Referrer-Policy: Missing" -ForegroundColor Red
}

# Permissions-Policy (10 points)
if ($headers -match "Permissions-Policy") {
    Write-Host "✅ Permissions-Policy: Present" -ForegroundColor Green
    $score += 10
} else {
    Write-Host "❌ Permissions-Policy: Missing" -ForegroundColor Red
}

# Cross-Origin-Opener-Policy (5 points)
if ($headers -match "Cross-Origin-Opener-Policy") {
    Write-Host "✅ COOP: Present" -ForegroundColor Green
    $score += 5
} else {
    Write-Host "❌ COOP: Missing" -ForegroundColor Red
}

# Cross-Origin-Resource-Policy (5 points)
if ($headers -match "Cross-Origin-Resource-Policy") {
    Write-Host "✅ CORP: Present" -ForegroundColor Green
    $score += 5
} else {
    Write-Host "❌ CORP: Missing" -ForegroundColor Red
}

# Server tokens hidden (bonus - 0 points, but good practice)
if ($headers -match "Server: nginx$" -or $headers -notmatch "nginx/\d") {
    Write-Host "✅ Server version: Hidden" -ForegroundColor Green
} else {
    Write-Host "⚠️  Server version: Exposed" -ForegroundColor Yellow
}

Write-Host ("=" * 60)
Write-Host "`n🎯 Total Score: $score / $maxScore" -ForegroundColor Cyan

$grade = switch ($score) {
    {$_ -ge 90} { "A+"; break }
    {$_ -ge 80} { "A"; break }
    {$_ -ge 70} { "B"; break }
    {$_ -ge 60} { "C"; break }
    {$_ -ge 50} { "D"; break }
    default { "F" }
}

$color = switch ($grade) {
    {$_ -in "A+","A"} { "Green" }
    {$_ -in "B","C"} { "Yellow" }
    default { "Red" }
}

Write-Host "🏆 Grade: $grade" -ForegroundColor $color

if ($score -ge 90) {
    Write-Host "`n🎉 Excellent! Your application has top-tier security headers!" -ForegroundColor Green
} elseif ($score -ge 70) {
    Write-Host "`n👍 Good! Consider adding missing headers for A+ rating." -ForegroundColor Yellow
} else {
    Write-Host "`n⚠️  Needs improvement! Critical headers are missing." -ForegroundColor Red
}

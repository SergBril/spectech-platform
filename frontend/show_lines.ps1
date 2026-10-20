$lines = Get-Content 'app/main.py' -Encoding UTF8
for ($i = 14; $i -lt 75 -and $i -lt $lines.Count; $i++) {
    Write-Host ("{0,4}: {1}" -f ($i + 1), $lines[$i])
}

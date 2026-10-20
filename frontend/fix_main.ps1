$file = 'app/main.py'
$lines = Get-Content $file -Encoding UTF8

# Собираем строки без дубликатов addresses импорта
$newLines = @()
$addressesAdded = $false

for ($i = 0; $i -lt $lines.Count; $i++) {
    $line = $lines[$i]

    # Пропускаем дубликаты импорта addresses
    if ($line -match '^\s*from app\.api\.routes import addresses\s*$') {
        if (-not $addressesAdded) {
            # Оставляем только первый
            $addressesAdded = $true
            $newLines += $line
        }
        continue
    }

    # Если строка внутри блока импорта и содержит addresses - пропускаем
    if ($line -match '^\s*addresses,?\s*$') {
        continue
    }

    $newLines += $line
}

# Теперь проверяем есть ли импорт addresses
$hasAddressesImport = $false
for ($i = 0; $i -lt $newLines.Count; $i++) {
    if ($newLines[$i] -match 'from app\.api\.routes import addresses') {
        $hasAddressesImport = $true
        break
    }
}

# Если нет - добавляем в правильное место
if (-not $hasAddressesImport) {
    $finalLines = @()
    for ($i = 0; $i -lt $newLines.Count; $i++) {
        $finalLines += $newLines[$i]

        # Добавляем после последнего блока from app.api.routes import
        if ($newLines[$i] -match '^\)$' -and $i -gt 0) {
            # Проверяем был ли это блок импорта routes
            for ($j = $i - 1; $j -ge $i - 50 -and $j -ge 0; $j--) {
                if ($newLines[$j] -match 'from app\.api\.routes import \(') {
                    $finalLines += 'from app.api.routes import addresses'
                    break
                }
                if ($newLines[$j] -match '^from ' -and $newLines[$j] -notmatch 'app\.api\.routes') {
                    break
                }
            }
        }
    }
    $newLines = $finalLines
}

Set-Content $file $newLines -Encoding UTF8
Write-Host "✅ Fixed main.py" -ForegroundColor Green

# Показываем результат
Write-Host "
=== Imports section ===" -ForegroundColor Cyan
$content = Get-Content $file -Encoding UTF8
for ($i = 0; $i -lt $content.Count -and $i -lt 90; $i++) {
    if ($content[$i] -match 'from app\.api\.routes' -or $content[$i] -match 'addresses') {
        Write-Host ("{0,4}: {1}" -f ($i + 1), $content[$i])
    }
}

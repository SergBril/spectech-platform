$file = 'src/pages/LoginPage.tsx'
$lines = Get-Content $file -Encoding UTF8

# Ищем строку с "Зарегистрироваться" и добавляем ссылку после неё
$output = @()
$added = $false

for ($i = 0; $i -lt $lines.Count; $i++) {
    $output += $lines[$i]

    # После строки с "Зарегистрироваться" и закрывающих тегов добавляем ссылку
    if ($lines[$i] -match 'Зарегистрироваться' -and -not $added) {
        # Добавляем следующую строку (</Link>)
        $i++
        $output += $lines[$i]

        # Добавляем следующую строку (</p>)
        $i++
        $output += $lines[$i]

        # Теперь добавляем нашу ссылку
        $output += '          <p className="mt-2 text-center text-sm text-gray-600">'
        $output += '            <Link to="/forgot-password" className="font-medium text-blue-600 hover:text-blue-500">'
        $output += '              Забыли пароль?'
        $output += '            </Link>'
        $output += '          </p>'
        $added = $true
    }
}

Set-Content $file $output -Encoding UTF8
Write-Host "✅ Added forgot-password link to LoginPage.tsx" -ForegroundColor Green

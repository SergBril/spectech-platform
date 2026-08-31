# Smoke Test V3: Finance MVP
$API = "http://localhost:8000/api/v1"
$PASS = 0
$FAIL = 0

function Check($Name, $Method, $Url, $Body, $Expected) {
    try {
        $params = @{ Uri = "$API$Url"; Method = $Method; Headers = @{Authorization = "Bearer $TOKEN"}; ContentType = "application/json" }
        if ($Body) { $params.Body = $Body }
        $response = Invoke-WebRequest @params -ErrorAction Stop
        if ($response.StatusCode -eq $Expected) {
            Write-Host "OK $Name ($($response.StatusCode))" -ForegroundColor Green
            $script:PASS++
            return ($response.Content | ConvertFrom-Json)
        } else {
            Write-Host "FAIL $Name (expected $Expected, got $($response.StatusCode))" -ForegroundColor Red
            $script:FAIL++
            return $null
        }
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        if ($code -eq $Expected) { Write-Host "OK $Name ($code)" -ForegroundColor Green; $script:PASS++ }
        else { Write-Host "FAIL $Name (expected $Expected, got $code)" -ForegroundColor Red; $script:FAIL++ }
        return $null
    }
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Smoke Test V3: Finance MVP" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$login = Invoke-RestMethod -Uri "$API/auth/login" -Method POST -ContentType "application/json" -Body '{"email":"admin@spectech.dev","password":"admin123"}'
$global:TOKEN = $login.access_token
Write-Host "OK Login" -ForegroundColor Green; $PASS++

$dash = Check "Dashboard" "GET" "/payments/dashboard"
if ($dash) { Write-Host "   Revenue: $($dash.total_revenue)" -ForegroundColor Gray }

$invoiceBody = @{request_id=1; client_id=2; invoice_date="2026-09-01"; vat_rate=20; items=@(@{description="Test"; quantity=8; unit="hr"; unit_price=2500})} | ConvertTo-Json -Depth 3
$invoice = Check "Create invoice" "POST" "/invoices" $invoiceBody 201
if ($invoice) { $invoiceId = $invoice.id; Check "Send invoice" "POST" "/invoices/$invoiceId/send" $null 200 | Out-Null }

$actBody = @{request_id=1; client_id=2; act_date="2026-09-01"; total_amount=24000} | ConvertTo-Json
$act = Check "Create act" "POST" "/acts" $actBody 201
if ($act) { $actId = $act.id; Check "Sign client" "POST" "/acts/$actId/sign" '{"signed_by":"client"}' 200 | Out-Null; Check "Sign executor" "POST" "/acts/$actId/sign" '{"signed_by":"executor"}' 200 | Out-Null }

$payoutBody = @{owner_id=3; vehicle_id=1; gross_amount=20000; commission_rate=15; payout_date="2026-09-01"} | ConvertTo-Json
$payout = Check "Create payout" "POST" "/payouts" $payoutBody 201
if ($payout) { Check "Approve payout" "POST" "/payouts/$($payout.id)/approve" $null 200 | Out-Null }

if ($invoiceId) { $paymentBody = @{invoice_id=$invoiceId; amount=24000; method="bank_transfer"; payment_date="2026-09-10"} | ConvertTo-Json; Check "Register payment" "POST" "/payments" $paymentBody 201 | Out-Null }

$finalDash = Check "Final dashboard" "GET" "/payments/dashboard"

Write-Host "========================================" -ForegroundColor Cyan
if ($FAIL -eq 0) { Write-Host " ALL $PASS CHECKS PASSED" -ForegroundColor Green }
else { Write-Host " $PASS passed, $FAIL failed" -ForegroundColor Yellow }
Write-Host "========================================" -ForegroundColor Cyan

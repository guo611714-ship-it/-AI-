# SearXNG search with auto-proxy start (PowerShell)
# Usage: powershell -File searxng-search.ps1 -Query "search query"

param(
    [Parameter(Mandatory=$true)]
    [string]$Query,
    [string]$Language = "zh-CN",
    [string]$Categories = "general"
)

$ProxyPort = 8001
$SearxngUrl = "http://localhost:8889"
$HolyTechExe = "D:\holytech\HolyTech.exe"
$MaxRetries = 2

function Test-Proxy {
    $conn = Get-NetTCPConnection -LocalPort $ProxyPort -State Listen -ErrorAction SilentlyContinue
    return $null -ne $conn
}

function Start-Proxy {
    if (-not (Test-Proxy)) {
        Write-Host "[searxng] Proxy not running, starting HolyTech..." -ForegroundColor Yellow
        Start-Process -FilePath $HolyTechExe -WindowStyle Minimized
        for ($i = 1; $i -le 15; $i++) {
            Start-Sleep -Seconds 1
            if (Test-Proxy) {
                Write-Host "[searxng] Proxy ready on port $ProxyPort" -ForegroundColor Green
                return $true
            }
        }
        Write-Host "[searxng] Proxy start timeout, using direct connection" -ForegroundColor DarkYellow
        return $false
    }
    return $true
}

function Invoke-SearxngSearch {
    param([string]$q, [string]$lang, [string]$cat)
    $EncodedQuery = [System.Uri]::EscapeDataString($q)
    try {
        $Result = Invoke-RestMethod -Uri "$SearxngUrl/search?q=$EncodedQuery&format=json&categories=$cat&language=$lang" -TimeoutSec 10
        return $Result
    } catch {
        return $null
    }
}

# Ensure proxy
Start-Proxy | Out-Null

# Search with retry
$Result = $null
for ($retry = 0; $retry -lt $MaxRetries; $retry++) {
    $Result = Invoke-SearxngSearch -q $Query -lang $Language -cat $Categories
    if ($null -ne $Result -and $Result.results.Count -gt 0) { break }
    if ($retry -eq 0) {
        Write-Host "[searxng] No results, retrying..." -ForegroundColor Yellow
        Start-Sleep -Seconds 1
    }
}

# Output
if ($null -eq $Result -or $Result.results.Count -eq 0) {
    Write-Host "[searxng] No results found" -ForegroundColor Red
    exit 1
}

$Results = $Result.results
Write-Host "Found $($Results.Count) results" -ForegroundColor Cyan

if ($Result.unresponsive_engines.Count -gt 0) {
    $Names = ($Result.unresponsive_engines | ForEach-Object { $_[0] }) -join ", "
    Write-Host "Unresponsive: $Names" -ForegroundColor DarkYellow
}

$i = 0
foreach ($r in $Results | Select-Object -First 5) {
    $i++
    $title = if ($r.title.Length -gt 80) { $r.title.Substring(0,80) + "..." } else { $r.title }
    Write-Host "$i. $title" -ForegroundColor White
    Write-Host "   $($r.url)" -ForegroundColor DarkGray
    if ($r.content) {
        $snippet = if ($r.content.Length -gt 200) { $r.content.Substring(0,200) + "..." } else { $r.content }
        Write-Host "   $snippet" -ForegroundColor DarkGray
    }
    Write-Host ""
}

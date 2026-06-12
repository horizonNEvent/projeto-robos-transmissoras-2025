# start_tunnel.ps1
# Inicia o cloudflared, captura a URL automaticamente,
# atualiza o apiConfig.js e faz deploy no Vercel.

$ErrorActionPreference = "Stop"
$log = "$env:TEMP\cf_tust_tunnel.log"
Remove-Item $log -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "[3/4] Iniciando Cloudflare Tunnel..." -ForegroundColor Cyan

# Backend precisa estar no ar antes do tunnel (evita deploy com API morta)
try {
    $health = Invoke-WebRequest -Uri "http://127.0.0.1:8000/docs" -UseBasicParsing -TimeoutSec 3
    if ($health.StatusCode -ge 500) { throw "status $($health.StatusCode)" }
} catch {
    Write-Host "ERRO: Backend nao responde em http://127.0.0.1:8000/" -ForegroundColor Red
    Write-Host "      Abra a janela 'ROBO RUNNER - Backend' e corrija o erro antes de rodar o tunnel." -ForegroundColor Yellow
    exit 1
}

# 127.0.0.1 evita cloudflared usar IPv6 [::1] no Windows (uvicorn pode recusar)
Start-Process -FilePath ".\cloudflared.exe" `
    -ArgumentList "tunnel --url http://127.0.0.1:8000" `
    -RedirectStandardError $log `
    -NoNewWindow

Write-Host "      Aguardando URL (ate 30s)..." -ForegroundColor Yellow

$url = $null
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep 1
    if (Test-Path $log) {
        $content = Get-Content $log -Raw -ErrorAction SilentlyContinue
        if ($content -match 'https://[\w-]+\.trycloudflare\.com') {
            $url = $matches[0]
            break
        }
    }
}

if (-not $url) {
    Write-Host "ERRO: Nao foi possivel obter URL do tunnel" -ForegroundColor Red
    exit 1
}

Write-Host "      URL: $url" -ForegroundColor Green

# Atualiza apiConfig.js
$apiConfig = "// Arquivo de configuracao central da API`n// Tunnel cloudflare - atualizado automaticamente pelo start_dev.bat`nexport const API_URL = `"$url`";"
Set-Content -Path "app\frontend\src\apiConfig.js" -Value $apiConfig -Encoding UTF8

# Build + Deploy no Vercel (nao bloqueia o retorno ao start_dev.bat)
Write-Host "      Fazendo build do frontend..." -ForegroundColor Yellow
Push-Location app\frontend
npm run build --silent
if ($LASTEXITCODE -ne 0) {
    Pop-Location
    Write-Host "ERRO: npm run build falhou" -ForegroundColor Red
    exit 1
}
Pop-Location

Write-Host "      Deploy Vercel em segundo plano (nao trava o backend)..." -ForegroundColor Yellow
$deployLog = Join-Path $env:TEMP "tust_vercel_deploy.log"
$frontendDir = Join-Path $PSScriptRoot "app\frontend"
Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", "cd /d `"$frontendDir`" && npx --yes vercel --prod --yes > `"$deployLog`" 2>&1" `
    -WindowStyle Minimized

Write-Host "      Log do deploy: $deployLog" -ForegroundColor DarkGray

try {
    $viaTunnel = Invoke-WebRequest -Uri "$url/" -UseBasicParsing -TimeoutSec 10
    if ($viaTunnel.StatusCode -eq 200) {
        Write-Host "      Tunnel OK: $url" -ForegroundColor Green
    }
} catch {
    Write-Host "      AVISO: Tunnel criado mas ainda nao responde. Aguarde e recarregue o front." -ForegroundColor Yellow
}

Write-Host "      Aguarde o deploy Vercel terminar (log acima) e abra:" -ForegroundColor Green
Write-Host "      https://frontend-red-eight-34.vercel.app" -ForegroundColor Green
Write-Host ""

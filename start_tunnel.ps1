# start_tunnel.ps1
# Inicia o cloudflared, captura a URL automaticamente,
# atualiza o apiConfig.js e faz deploy no Vercel.

$ErrorActionPreference = "Stop"
$log = "$env:TEMP\cf_tust_tunnel.log"
Remove-Item $log -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "[2/3] Iniciando Cloudflare Tunnel..." -ForegroundColor Cyan

# Inicia cloudflared (URLs saem no stderr)
Start-Process -FilePath ".\cloudflared.exe" `
    -ArgumentList "tunnel --url http://localhost:8000" `
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

# Build + Deploy no Vercel
Write-Host "      Fazendo build e deploy no Vercel..." -ForegroundColor Yellow
Push-Location app\frontend
npm run build --silent

# Usando --token se necessário ou apenas garantindo que o output não quebre o PS
$deploy = npx vercel --prod --yes
if ($deploy -match "Aliased: (https://\S+)") {
    Write-Host "      Deploy concluido: $matches[1]" -ForegroundColor Green
} else {
    Write-Host "      Deploy enviado para o Vercel (verifique no painel se houver erro)." -ForegroundColor Cyan
}

Pop-Location

Write-Host "      Deploy concluido!" -ForegroundColor Green
Write-Host ""

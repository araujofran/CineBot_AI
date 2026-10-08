$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$tunnelPath = Join-Path $projectRoot 'tools\cloudflared.exe'
$runtimePath = Join-Path $projectRoot 'data'
$ollamaPath = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
if ((Get-Content (Join-Path $projectRoot '.env') -ErrorAction SilentlyContinue) -match '^LLM_PROVIDER=ollama$') {
    try { Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 3 | Out-Null } catch {
        if (Test-Path -LiteralPath $ollamaPath) { Start-Process -FilePath $ollamaPath -ArgumentList 'serve' -WindowStyle Hidden }
    }
}
New-Item -ItemType Directory -Path $runtimePath -Force | Out-Null
try { $health = Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 3 } catch { $health = $null }
if (-not $health) {
    $backend = Start-Process -FilePath $pythonPath -ArgumentList '-m','uvicorn','cinebot.presentation.api:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimePath 'backend.out.log') -RedirectStandardError (Join-Path $runtimePath 'backend.err.log') -PassThru
    $backend.Id | Set-Content (Join-Path $runtimePath 'backend.pid')
}
$activeTunnel = $null
$pidPath = Join-Path $runtimePath 'tunnel.pid'
if (Test-Path -LiteralPath $pidPath) {
    $storedId = [int](Get-Content -LiteralPath $pidPath)
    $candidate = Get-Process -Id $storedId -ErrorAction SilentlyContinue
    if ($candidate -and $candidate.ProcessName -eq 'cloudflared') { $activeTunnel = $candidate }
}
if (-not $activeTunnel) {
$tunnel = Start-Process -FilePath $tunnelPath -ArgumentList 'tunnel','--no-autoupdate','--protocol','http2','--url','http://127.0.0.1:8000' -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimePath 'tunnel.out.log') -RedirectStandardError (Join-Path $runtimePath 'tunnel.err.log') -PassThru
$tunnel.Id | Set-Content (Join-Path $runtimePath 'tunnel.pid')
}
Write-Output 'Servidor e conector iniciados. O link publico aparecera em data/tunnel.err.log.'

$tunnelLog = Join-Path $runtimePath 'tunnel.err.log'
for ($attempt = 0; $attempt -lt 15; $attempt++) {
    if (Test-Path -LiteralPath $tunnelLog) {
        $matchesFound = [regex]::Matches((Get-Content -LiteralPath $tunnelLog -Raw), 'https://[a-z0-9-]+\.trycloudflare\.com')
        if ($matchesFound.Count -gt 0) {
            $publicUrl = $matchesFound[$matchesFound.Count - 1].Value
            $publicUrl | Set-Content (Join-Path $runtimePath 'public-url.txt')
            Write-Output ('URL publica: ' + $publicUrl)
            Get-Content (Join-Path $runtimePath 'public-access.txt')
            break
        }
    }
    Start-Sleep -Seconds 2
}

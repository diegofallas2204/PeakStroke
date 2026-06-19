# Lanzador de desarrollo de PeakStroke.
# Arranca backend (FastAPI/uvicorn) y frontend (Vite) en esta misma consola y, al
# cerrar la ventana o presionar Ctrl+C, detiene ambos y todos sus procesos hijos.
# No se ejecuta directamente: lo invoca start-peakstroke.bat.

$ErrorActionPreference = 'Stop'
$root     = $PSScriptRoot
$backend  = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$python   = Join-Path $backend '.venv\Scripts\python.exe'

$script:procs = @()

function Stop-All {
    foreach ($p in $script:procs) {
        try {
            if ($p -and -not $p.HasExited) {
                # /T mata también node/vite/uvicorn-reloader (procesos hijos).
                taskkill /PID $p.Id /T /F 2>$null | Out-Null
            }
        } catch { }
    }
}

# Limpieza también si se cierra la ventana con la X (evento de salida del motor).
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action { Stop-All }

if (-not (Test-Path $python)) {
    Write-Host "No se encontró el entorno virtual del backend:" -ForegroundColor Red
    Write-Host "  $python"
    Write-Host "Créalo con:  cd backend; python -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
    exit 1
}

try {
    Write-Host 'Iniciando backend  -> http://localhost:8000' -ForegroundColor Cyan
    $b = Start-Process -FilePath $python `
        -ArgumentList '-m','uvicorn','app.main:app','--reload','--port','8000' `
        -WorkingDirectory $backend -PassThru -NoNewWindow
    $script:procs += $b

    Write-Host 'Iniciando frontend -> http://localhost:5173' -ForegroundColor Cyan
    $f = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c','npm run dev' `
        -WorkingDirectory $frontend -PassThru -NoNewWindow
    $script:procs += $f

    Write-Host ''
    Write-Host 'PeakStroke corriendo. Cierra esta ventana o presiona Ctrl+C para detener todo.' -ForegroundColor Green
    Write-Host ''

    # Espera hasta que cualquiera de los dos termine (o hasta Ctrl+C).
    while (-not ($b.HasExited -or $f.HasExited)) {
        Start-Sleep -Seconds 1
    }
    Write-Host ''
    Write-Host 'Uno de los servidores se detuvo; cerrando el otro...' -ForegroundColor Yellow
}
finally {
    Write-Host 'Deteniendo PeakStroke...' -ForegroundColor Yellow
    Stop-All
}

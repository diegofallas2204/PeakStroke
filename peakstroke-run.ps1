# Lanzador de desarrollo de PeakStroke.
# Arranca backend (FastAPI/uvicorn) y frontend (Vite) en esta misma consola, abre
# el navegador y, al cerrar la ventana o presionar Ctrl+C, detiene ambos y todos
# sus procesos hijos.
# No se ejecuta directamente: lo invoca start-peakstroke.bat.

$ErrorActionPreference = 'Stop'
$root     = $PSScriptRoot
$backend  = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$python   = Join-Path $backend '.venv\Scripts\python.exe'

$BACKEND_PORT  = 8000
$FRONTEND_PORT = 5173

$script:procs = @()

# -- Utilidades de proceso y puerto ------------------------------------------

# Mata un proceso y toda su descendencia. No usamos `taskkill /T`: el worker real
# de `uvicorn --reload` nace por multiprocessing y sobrevive si el árbol se rompe
# (por ejemplo al cerrar la ventana con la X). Aquí bajamos hijo por hijo.
function Stop-Tree([int]$procId) {
    foreach ($child in @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$procId" -ErrorAction SilentlyContinue)) {
        Stop-Tree ([int]$child.ProcessId)
    }
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
}

function Get-PortOwner([int]$port) {
    @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique)
}

# Si una ejecución anterior dejó el puerto tomado, el servidor nuevo no puede
# escuchar y el lanzador se cerraba de inmediato (la ventana "parpadeaba").
# Liberarlo antes de arrancar hace que el doble clic funcione siempre.
function Clear-Port([int]$port, [string]$label) {
    $owners = Get-PortOwner $port
    if (-not $owners) { return $true }
    Write-Host "Puerto $port ocupado por una ejecución anterior ($label) - liberando..." -ForegroundColor Yellow
    foreach ($owner in $owners) { Stop-Tree ([int]$owner) }
    for ($i = 0; $i -lt 20; $i++) {
        if (-not (Get-PortOwner $port)) { return $true }
        Start-Sleep -Milliseconds 250
    }
    return (-not (Get-PortOwner $port))
}

# Espera a que el servidor escuche; corta antes si el proceso murió.
# Devuelve 'ok', 'muerto' o 'timeout'.
function Wait-Server($proc, [int]$port, [int]$timeoutSec) {
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Get-PortOwner $port) { return 'ok' }
        if ($proc.HasExited)     { return 'muerto' }
        Start-Sleep -Milliseconds 300
    }
    return 'timeout'
}

function Stop-All {
    foreach ($p in $script:procs) {
        try { if ($p -and -not $p.HasExited) { Stop-Tree $p.Id } } catch { }
    }
    # Barrido final por puerto: recoge los nietos que sobrevivan al árbol.
    foreach ($port in @($BACKEND_PORT, $FRONTEND_PORT)) {
        foreach ($owner in (Get-PortOwner $port)) { Stop-Tree ([int]$owner) }
    }
}

# Mantiene la ventana abierta al fallar: si no, el error se pierde en el parpadeo.
function Stop-WithError([string]$message, [string[]]$hints = @()) {
    Write-Host ''
    Write-Host $message -ForegroundColor Red
    foreach ($h in $hints) { Write-Host "  $h" }
    Write-Host ''
    Write-Host 'Presiona Enter para cerrar esta ventana...' -ForegroundColor DarkGray
    [void](Read-Host)
    Stop-All
    exit 1
}

# Limpieza también si se cierra la ventana con la X (evento de salida del motor).
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action { Stop-All }

# -- Comprobaciones previas --------------------------------------------------

if (-not (Test-Path $python)) {
    Stop-WithError "No se encontró el entorno virtual del backend:" @(
        $python,
        '',
        'Créalo con:  cd backend; python -m venv .venv; .venv\Scripts\pip install -r requirements.txt'
    )
}

if (-not (Test-Path (Join-Path $frontend 'node_modules'))) {
    Stop-WithError 'Faltan las dependencias del frontend.' @('Instálalas con:  cd frontend; npm install')
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Stop-WithError 'No se encontró npm en el PATH.' @('Instala Node.js desde https://nodejs.org y vuelve a intentarlo.')
}

if (-not (Clear-Port $BACKEND_PORT 'backend')) {
    Stop-WithError "El puerto $BACKEND_PORT sigue ocupado y no se pudo liberar." @('Cierra la aplicación que lo usa o reinicia el equipo.')
}
if (-not (Clear-Port $FRONTEND_PORT 'frontend')) {
    Stop-WithError "El puerto $FRONTEND_PORT sigue ocupado y no se pudo liberar." @('Cierra la aplicación que lo usa o reinicia el equipo.')
}

# -- Arranque ----------------------------------------------------------------

try {
    Write-Host 'Iniciando backend  -> http://localhost:8000' -ForegroundColor Cyan
    $b = Start-Process -FilePath $python `
        -ArgumentList '-m','uvicorn','app.main:app','--reload','--port',"$BACKEND_PORT" `
        -WorkingDirectory $backend -PassThru -NoNewWindow
    $script:procs += $b

    switch (Wait-Server $b $BACKEND_PORT 60) {
        'muerto'  { Stop-WithError 'El backend se cerró al arrancar (revisa el error de arriba).' }
        'timeout' { Stop-WithError "El backend no respondió en el puerto $BACKEND_PORT." }
    }

    Write-Host 'Iniciando frontend -> http://localhost:5173' -ForegroundColor Cyan
    $f = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c','npm run dev' `
        -WorkingDirectory $frontend -PassThru -NoNewWindow
    $script:procs += $f

    switch (Wait-Server $f $FRONTEND_PORT 90) {
        'muerto'  { Stop-WithError 'El frontend se cerró al arrancar (revisa el error de arriba).' }
        'timeout' { Stop-WithError "El frontend no respondió en el puerto $FRONTEND_PORT." }
    }

    Start-Process "http://localhost:$FRONTEND_PORT"

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

# Piloto de PeakStroke en la red local: la app de verdad, con login, servida
# desde esta computadora para que varias personas entren a la vez, cada una con
# su cuenta (otros dispositivos de la misma wifi, u otras ventanas de aquí).
# Ver docs/PILOTO.md.
#
#   .\piloto.ps1 preparar     secreto, base y build (no arranca nada)
#   .\piloto.ps1 datos        BORRA la base del piloto y carga el seed: 2
#                             entrenadores y 5 atletas con datos (contraseña: peakstroke)
#   .\piloto.ps1 levantar     prepara y lo deja corriendo en segundo plano; abre el navegador
#   .\piloto.ps1 apagar       lo para (lo levantado con `levantar`)
#   .\piloto.ps1 estado       si está corriendo y dónde
#   .\piloto.ps1              prepara y arranca en esta ventana (Ctrl+C para parar)
#   (con doble clic: piloto-levantar.bat y piloto-apagar.bat)
#   .\piloto.ps1 ops crear-equipo --nombre-equipo "Club" --correo yo@club.com --nombre "Yo"
#                             comandos de operación contra la base del piloto
#
# Todo lo del piloto vive aparte del desarrollo: backend\piloto.db (la base) y
# backend\.env.piloto (el secreto y la configuración). Git ignora los dos.
# PEAKSTROKE_PILOTO_DIR cambia esa carpeta (para probar el script sin tocarlos).
#
# Va por http, no https: es la red de casa o del club, no internet. Por eso la
# cookie de sesión no lleva `Secure` (un navegador no la guardaría por http fuera
# de localhost) y el entorno no es `production`. El login sí está encendido.

param(
    [ValidateSet('arrancar', 'levantar', 'apagar', 'estado', 'preparar', 'datos', 'ops')]
    [string]$Accion = 'arrancar',
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Resto
)

$ErrorActionPreference = 'Stop'
$root     = $PSScriptRoot
$backend  = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$python   = Join-Path $backend '.venv\Scripts\python.exe'
$datos    = if ($env:PEAKSTROKE_PILOTO_DIR) { $env:PEAKSTROKE_PILOTO_DIR } else { $backend }
$base     = Join-Path $datos 'piloto.db'
$envFile  = Join-Path $datos '.env.piloto'
$API_PORT = 8000
$WEB_PORT = 4173
$pids     = Join-Path $datos 'piloto.pids'
$logs     = Join-Path $datos 'piloto-logs'

function Escribir-Config {
    if (Test-Path $envFile) { return }
    New-Item -ItemType Directory -Force $datos | Out-Null
    $secreto = (& $python -c "import secrets; print(secrets.token_urlsafe(64))").Trim()
    $url = 'sqlite+aiosqlite:///' + ($base -replace '\\', '/')
    @(
        '# Configuración del piloto en red local (piloto.ps1). NO subir a git: lleva el secreto.',
        'PEAKSTROKE_AUTH_ENABLED=true',
        '# http en la red local: la cookie no puede ser Secure (ver piloto.ps1).',
        'PEAKSTROKE_REFRESH_COOKIE_SECURE=false',
        "PEAKSTROKE_JWT_SECRET=$secreto",
        "PEAKSTROKE_DATABASE_URL=$url",
        '# La vista previa reenvía la IP de cada dispositivo desde esta máquina.',
        'PEAKSTROKE_PROXIES_DE_CONFIANZA=127.0.0.1/32,::1/128'
    ) | Set-Content -Encoding utf8 $envFile
    Write-Host "Configuración nueva en $envFile (con un secreto propio)." -ForegroundColor Green
}

function Cargar-Config {
    foreach ($linea in Get-Content $envFile) {
        if ($linea -match '^\s*#' -or $linea -notmatch '=') { continue }
        $clave, $valor = $linea -split '=', 2
        Set-Item -Path "env:$($clave.Trim())" -Value $valor.Trim()
    }
}

# Los programas externos (alembic, npm) escriben sus registros en stderr, y en
# PowerShell 5.1 eso con 'Stop' es un error. Dentro de cada función se usa
# 'Continue' y el fallo de verdad se mira en $LASTEXITCODE.
function En-Backend([string[]]$argumentos) {
    $ErrorActionPreference = 'Continue'
    Push-Location $backend
    try {
        & $python @argumentos
        if ($LASTEXITCODE -ne 0) { throw "Falló: python $($argumentos -join ' ')" }
    } finally { Pop-Location }
}

function Construir {
    $ErrorActionPreference = 'Continue'
    $rama = (git -C $root rev-parse --abbrev-ref HEAD).Trim()
    if ($rama -like 'modulo/*') {
        Write-Host "Ojo: estás en $rama; la build solo llevará ese módulo. El piloto va en Preliminar." -ForegroundColor Yellow
    }
    Push-Location $frontend
    try {
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'npm run build falló' }
    } finally { Pop-Location }
}

function Ips-De-La-Red {
    @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        # Fuera las de esta máquina y las virtuales (WSL, Hyper-V, VPN): solo la wifi o el cable.
        Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and $_.PrefixOrigin -ne 'WellKnown' -and $_.InterfaceAlias -notmatch 'vEthernet|WSL|Hyper-V|VirtualBox|VMware|Loopback|Tailscale|ZeroTier' } |
        Select-Object -ExpandProperty IPAddress)
}

function Quien-Escucha([int]$puerto) {
    @(Get-NetTCPConnection -State Listen -LocalPort $puerto -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique)
}

function Parar-Arbol([int]$procId) {
    foreach ($hijo in @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$procId" -ErrorAction SilentlyContinue)) {
        Parar-Arbol ([int]$hijo.ProcessId)
    }
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
}

function Apagar {
    $parados = 0
    if (Test-Path $pids) {
        foreach ($id in Get-Content $pids) {
            if ($id -match '^\d+$' -and (Get-Process -Id ([int]$id) -ErrorAction SilentlyContinue)) {
                Parar-Arbol ([int]$id); $parados++
            }
        }
        Remove-Item $pids -Force
    }
    # Por si quedó algo del piloto escuchando sin estar apuntado (solo python y node).
    foreach ($p in @($API_PORT, $WEB_PORT)) {
        foreach ($id in Quien-Escucha $p) {
            $proc = Get-Process -Id $id -ErrorAction SilentlyContinue
            if ($proc -and $proc.ProcessName -in @('python', 'node')) { Parar-Arbol $id; $parados++ }
        }
    }
    if ($parados) { Write-Host 'Piloto apagado.' -ForegroundColor Green }
    else { Write-Host 'El piloto no estaba corriendo.' -ForegroundColor DarkGray }
}

function Mostrar-Entradas {
    Write-Host 'Entra desde:' -ForegroundColor Cyan
    Write-Host "  http://localhost:$WEB_PORT"
    Write-Host "  http://127.0.0.1:$WEB_PORT   (otra cuenta a la vez: otro origen)"
    foreach ($ip in Ips-De-La-Red) { Write-Host "  http://${ip}:$WEB_PORT   (otra computadora de la red)" }
    Write-Host 'Cuentas y contraseñas: CUENTAS-PILOTO.txt' -ForegroundColor DarkGray
}

function Estado {
    $api = Quien-Escucha $API_PORT
    $web = Quien-Escucha $WEB_PORT
    if ($api -and $web) { Write-Host 'Piloto corriendo.' -ForegroundColor Green; Mostrar-Entradas }
    elseif ($api -or $web) { Write-Host "A medias: API $(if ($api) {'sí'} else {'no'}), web $(if ($web) {'sí'} else {'no'}). Apágalo y vuelve a levantarlo." -ForegroundColor Yellow }
    else { Write-Host 'El piloto no está corriendo.' -ForegroundColor DarkGray }
}

switch ($Accion) {
    'apagar' { Apagar; exit 0 }
    'estado' { Estado; exit 0 }
}

Escribir-Config
Cargar-Config

switch ($Accion) {
    'ops' { En-Backend (@('tools/ops.py') + $Resto); exit 0 }
    'datos' {
        if ((Quien-Escucha $API_PORT) -or (Quien-Escucha $WEB_PORT)) {
            throw 'El piloto está corriendo: apágalo antes de recargar los datos (.\piloto.ps1 apagar).'
        }
        Write-Host "Se BORRA la base del piloto ($base) y se carga el seed." -ForegroundColor Yellow
        En-Backend @('seed.py')
        exit 0
    }
}

En-Backend @('-m', 'alembic', 'upgrade', 'head')
Construir
if ($Accion -eq 'preparar') {
    Write-Host 'Piloto preparado. Arráncalo con .\piloto.ps1' -ForegroundColor Green
    exit 0
}

foreach ($p in @($API_PORT, $WEB_PORT)) {
    if (Quien-Escucha $p) {
        throw "El puerto $p está ocupado (¿el piloto ya corre, o el entorno de desarrollo sigue abierto?). Prueba .\piloto.ps1 apagar"
    }
}

$argsApi = @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$API_PORT", '--no-proxy-headers')

if ($Accion -eq 'levantar') {
    # En segundo plano, sin ventanas y por WMI: así los procesos no cuelgan de
    # esta consola ni de quien la abrió, y cerrar una ventana o una pestaña no
    # los mata. Cada uno con su log y su PID apuntado para que `apagar` sepa qué
    # parar. Un proceso creado por WMI no hereda el entorno: el API lee él mismo
    # .env.piloto (tools/piloto_api.py), y así el secreto no va en la línea de
    # comandos. La vista previa va con node directo (no npm).
    New-Item -ItemType Directory -Force $logs | Out-Null
    $node = (Get-Command node -ErrorAction Stop).Source
    $vite = Join-Path $frontend 'node_modules\vite\bin\vite.js'
    $lanzador = Join-Path $backend 'tools\piloto_api.py'
    $logApi = Join-Path $logs 'api.log'
    $logWeb = Join-Path $logs 'web.log'
    $oculto = New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{ ShowWindow = [uint16]0 }
    function Crear([string]$linea, [string]$carpeta) {
        $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
            CommandLine = $linea; CurrentDirectory = $carpeta; ProcessStartupInformation = $oculto
        }
        if ($r.ReturnValue -ne 0) { throw "Windows no pudo crear el proceso (código $($r.ReturnValue)): $linea" }
        [int]$r.ProcessId
    }
    $idApi = Crear "`"$python`" `"$lanzador`" `"$envFile`" `"$logApi`" $API_PORT" $backend
    $idWeb = Crear "cmd.exe /c `"`"$node`" `"$vite`" preview --host 0.0.0.0 --port $WEB_PORT --strictPort > `"$logWeb`" 2>&1`"" $frontend
    @($idApi, $idWeb) | Set-Content $pids
    $limite = (Get-Date).AddSeconds(60)
    while (-not ((Quien-Escucha $API_PORT) -and (Quien-Escucha $WEB_PORT))) {
        $vivos = (Get-Process -Id $idApi -ErrorAction SilentlyContinue) -and (Get-Process -Id $idWeb -ErrorAction SilentlyContinue)
        if ((Get-Date) -gt $limite -or -not $vivos) {
            Apagar
            throw "No arrancó. Mira los logs en $logs"
        }
        Start-Sleep -Milliseconds 500
    }
    Write-Host ''
    Write-Host 'Piloto levantado en segundo plano.' -ForegroundColor Green
    Mostrar-Entradas
    Write-Host 'Para apagarlo: piloto-apagar.bat (o .\piloto.ps1 apagar)' -ForegroundColor DarkGray
    Start-Process "http://localhost:$WEB_PORT"
    exit 0
}

# El API solo escucha en esta máquina: a la red sale la vista previa, que le
# reenvía /api. --no-proxy-headers deja que la IP real la decida
# PEAKSTROKE_PROXIES_DE_CONFIANZA y nadie más (docs/DESPLIEGUE.md §3).
$api = Start-Process -FilePath $python -WorkingDirectory $backend -PassThru -NoNewWindow -ArgumentList $argsApi
try {
    Write-Host ''
    Write-Host 'Piloto en marcha.' -ForegroundColor Cyan
    Mostrar-Entradas
    Write-Host 'Ctrl+C para parar.' -ForegroundColor DarkGray
    Push-Location $frontend
    $ErrorActionPreference = 'Continue'
    npm run preview -- --host 0.0.0.0 --port $WEB_PORT --strictPort
} finally {
    Pop-Location
    if ($api -and -not $api.HasExited) { Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue }
}

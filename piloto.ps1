# Piloto de PeakStroke en la red local: la app de verdad, con login, servida
# desde esta computadora para que varias personas entren a la vez, cada una con
# su cuenta (otros dispositivos de la misma wifi, u otras ventanas de aquí).
# Ver docs/PILOTO.md.
#
#   .\piloto.ps1 preparar     secreto, base y build (no arranca nada)
#   .\piloto.ps1 datos        BORRA la base del piloto y carga el seed: 2
#                             entrenadores y 5 atletas con datos (contraseña: peakstroke)
#   .\piloto.ps1              prepara y arranca (Ctrl+C para parar)
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
    [ValidateSet('arrancar', 'preparar', 'datos', 'ops')]
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

Escribir-Config
Cargar-Config

switch ($Accion) {
    'ops' { En-Backend (@('tools/ops.py') + $Resto); exit 0 }
    'datos' {
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
    if (Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue) {
        throw "El puerto $p está ocupado (¿el entorno de desarrollo sigue abierto?)."
    }
}

# El API solo escucha en esta máquina: a la red sale la vista previa, que le
# reenvía /api. --no-proxy-headers deja que la IP real la decida
# PEAKSTROKE_PROXIES_DE_CONFIANZA y nadie más (docs/DESPLIEGUE.md §3).
$api = Start-Process -FilePath $python -WorkingDirectory $backend -PassThru -NoNewWindow `
    -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$API_PORT", '--no-proxy-headers'
try {
    Write-Host ''
    Write-Host 'Piloto en marcha. Entra desde:' -ForegroundColor Cyan
    Write-Host "  esta computadora:  http://localhost:$WEB_PORT"
    Write-Host "                     http://127.0.0.1:$WEB_PORT   (otra cuenta a la vez: otro origen)"
    foreach ($ip in Ips-De-La-Red) { Write-Host "  la wifi:           http://${ip}:$WEB_PORT" }
    Write-Host 'Si un teléfono no conecta, Windows puede estar bloqueando el puerto (firewall).' -ForegroundColor DarkGray
    Write-Host 'Ctrl+C para parar.' -ForegroundColor DarkGray
    Push-Location $frontend
    $ErrorActionPreference = 'Continue'
    npm run preview -- --host 0.0.0.0 --port $WEB_PORT --strictPort
} finally {
    Pop-Location
    if ($api -and -not $api.HasExited) { Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue }
}

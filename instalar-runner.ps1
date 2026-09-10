$ErrorActionPreference = 'Stop'

# Instalador pessoal do GitHub Actions Runner para este repositório.
# Não contém token nem credenciais. O token é solicitado somente durante a execução.

$repoUrl = 'https://github.com/thenights20/viagens'
$runnerVersion = '2.337.0'
$runnerDir = 'C:\actions-runner'
$zipName = "actions-runner-win-x64-$runnerVersion.zip"
$zipPath = Join-Path $runnerDir $zipName
$downloadUrl = "https://github.com/actions/runner/releases/download/v$runnerVersion/$zipName"
$expectedHash = '1150692afa94e71f872017e254ea55b6eece1eece3fe7e3a6d4c93d0a1b85cfc'

function Test-Administrator {
    $current = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($current)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Administrator)) {
    Write-Host 'Abrindo novamente como Administrador...' -ForegroundColor Yellow
    Start-Process powershell.exe -Verb RunAs -ArgumentList @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', "`"$PSCommandPath`""
    )
    exit
}

Write-Host ''
Write-Host '=== Configuração do computador para o GitHub Actions ===' -ForegroundColor Cyan
Write-Host "Repositório: $repoUrl"
Write-Host "Pasta:       $runnerDir"
Write-Host ''

New-Item -ItemType Directory -Path $runnerDir -Force | Out-Null
Set-Location $runnerDir

if (Test-Path (Join-Path $runnerDir '.runner')) {
    Write-Host 'Este computador já possui um runner configurado nesta pasta.' -ForegroundColor Green
    Write-Host 'Abra GitHub > Settings > Actions > Runners e confira se ele aparece Online/Idle.'
    Read-Host 'Pressione Enter para fechar'
    exit 0
}

if (-not (Test-Path (Join-Path $runnerDir 'config.cmd'))) {
    if (-not (Test-Path $zipPath)) {
        Write-Host 'Baixando o GitHub Actions Runner...'
        Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath
    }

    Write-Host 'Validando o arquivo baixado...'
    $actualHash = (Get-FileHash -Path $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $expectedHash.ToLowerInvariant()) {
        Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
        throw 'A validação SHA256 falhou. O arquivo foi removido e nada foi instalado.'
    }

    Write-Host 'Extraindo arquivos...'
    Expand-Archive -Path $zipPath -DestinationPath $runnerDir -Force
}

Write-Host ''
Write-Host 'IMPORTANTE:' -ForegroundColor Yellow
Write-Host 'Use um TOKEN NOVO da tela New self-hosted runner.'
Write-Host 'O token é temporário e não será salvo neste script.'
Write-Host ''

$secureToken = Read-Host 'Cole o token NOVO do GitHub' -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
try {
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}

if ([string]::IsNullOrWhiteSpace($token)) {
    throw 'Token vazio.'
}

$runnerName = "price-monitor-$env:COMPUTERNAME"
Write-Host ''
Write-Host "Registrando como $runnerName e instalando como serviço..." -ForegroundColor Cyan

& (Join-Path $runnerDir 'config.cmd') `
    --unattended `
    --url $repoUrl `
    --token $token `
    --name $runnerName `
    --work '_work' `
    --runasservice

$token = $null
$secureToken = $null

if ($LASTEXITCODE -ne 0) {
    throw "A configuração terminou com código $LASTEXITCODE."
}

Start-Sleep -Seconds 3
$services = Get-Service | Where-Object { $_.Name -like 'actions.runner.*' }
if ($services) {
    foreach ($service in $services) {
        if ($service.Status -ne 'Running') {
            try { Start-Service $service.Name } catch {}
        }
    }
    Write-Host ''
    Write-Host 'Runner instalado. Serviço encontrado:' -ForegroundColor Green
    Get-Service | Where-Object { $_.Name -like 'actions.runner.*' } | Format-Table Status, Name, DisplayName -AutoSize
} else {
    Write-Host 'Runner registrado, mas o serviço não foi localizado. Confira a tela de Runners no GitHub.' -ForegroundColor Yellow
}

Write-Host ''
Write-Host 'Agora volte ao GitHub > Settings > Actions > Runners.' -ForegroundColor Green
Write-Host 'Ele deve aparecer como Online / Idle.'
Read-Host 'Pressione Enter para fechar'

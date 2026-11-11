# Install ilias-mcp on Windows and open account setup.
param(
    [switch]$SkipCheck,
    [switch]$Terminal,
    [switch]$NoClaude,
    [string]$User,
    [string]$DownloadRoot,
    [switch]$ChatGPT,
    [string]$TunnelClient,
    [string]$TunnelId
)

$ErrorActionPreference = "Stop"
# Some shells launch PowerShell without .EXE in PATHEXT.
if (($env:PATHEXT -split ';') -notcontains '.EXE') {
    $env:PATHEXT = ".EXE;$env:PATHEXT"
}
Set-Location -LiteralPath $PSScriptRoot
$VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$Uv = Get-Command uv.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1

function Invoke-Native([string]$Exe, [string[]]$Arguments) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Exe failed (exit code $LASTEXITCODE)." }
}

function Find-Python {
    $candidates = @(
        @{ Exe = "py.exe"; Flags = @("-3") },
        @{ Exe = "python.exe"; Flags = @() },
        @{ Exe = "python3.exe"; Flags = @() }
    )
    if ($env:LOCALAPPDATA) {
        $installRoot = Join-Path $env:LOCALAPPDATA "Programs\Python"
        $folders = Get-ChildItem -LiteralPath $installRoot -Directory -Filter "Python3*" -ErrorAction SilentlyContinue
        foreach ($folder in $folders) {
            $candidates += @{ Exe = (Join-Path $folder.FullName "python.exe"); Flags = @() }
        }
    }
    foreach ($candidate in $candidates) {
        $command = Get-Command $candidate.Exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $command) { continue }
        $flags = $candidate.Flags
        try {
            & $command.Source @flags -c "import sys; sys.exit(sys.version_info < (3, 10))" *> $null
            if ($LASTEXITCODE -eq 0) { return @{ Exe = $command.Source; Flags = $flags } }
        } catch { }
    }
    return $null
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    if (Test-Path -LiteralPath ".venv") {
        throw "The existing .venv is incompatible with Windows. Rename it and rerun setup."
    }
    if ($Uv) {
        Invoke-Native $Uv.Source @("venv", "--python", ">=3.10", ".venv")
    } else {
        $Python = Find-Python
        if (-not $Python) { throw "Install Python 3.10+ from python.org or install uv, then rerun setup." }
        Invoke-Native $Python.Exe ($Python.Flags + @("-m", "venv", ".venv"))
    }
}

if ($Uv) {
    Invoke-Native $Uv.Source @("pip", "install", "--python", $VenvPython, "-e", ".")
} else {
    & $VenvPython -m pip --version *> $null
    if ($LASTEXITCODE -ne 0) {
        Invoke-Native $VenvPython @("-m", "ensurepip", "--upgrade")
    }
    Invoke-Native $VenvPython @("-m", "pip", "install", "-e", ".")
}

if ($ChatGPT) {
    $TunnelArgs = @("-m", "ilias_mcp.chatgpt")
    if ($TunnelClient) { $TunnelArgs += @("--tunnel-client", $TunnelClient) }
    if ($TunnelId) { $TunnelArgs += @("--tunnel-id", $TunnelId) }
    & $VenvPython @TunnelArgs
    exit $LASTEXITCODE
}

$SetupArgs = @("-m", "ilias_mcp.install", "setup")
if ($SkipCheck) { $SetupArgs += "--skip-check" }
if ($Terminal) { $SetupArgs += "--terminal" }
if ($NoClaude) { $SetupArgs += "--no-claude" }
if ($User) { $SetupArgs += @("--user", $User) }
if ($DownloadRoot) { $SetupArgs += @("--download-root", $DownloadRoot) }
& $VenvPython @SetupArgs
exit $LASTEXITCODE

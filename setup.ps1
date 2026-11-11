# Set up ilias-mcp on Windows: virtualenv, password in Windows Credential Manager,
# self-test and Claude desktop configuration.
#
#   powershell -ExecutionPolicy Bypass -File setup.ps1              full setup
#   powershell -ExecutionPolicy Bypass -File setup.ps1 -SkipCheck   skip the live self-test
#
# (-ExecutionPolicy Bypass applies to this one run only; nothing is changed permanently.)
param([switch]$SkipCheck)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$Dir = (Get-Location).Path
$Service = "ilias-mcp"
$VenvPython = Join-Path $Dir ".venv\Scripts\python.exe"
$VenvConfig = Join-Path $Dir ".venv\Scripts\ilias-mcp-config.exe"
$VenvCheck = Join-Path $Dir ".venv\Scripts\ilias-mcp-check.exe"

function Invoke-Native([string]$Exe, [string[]]$Arguments) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "'$Exe $($Arguments -join ' ')' failed (exit code $LASTEXITCODE)" }
}

function Find-Python {
    # The py launcher comes with the python.org installer; 'python' may be the
    # Microsoft Store alias, which fails the version test below unless Python is installed.
    foreach ($candidate in @("py -3.13", "py -3.12", "py -3.11", "py -3.10", "py -3", "python", "python3")) {
        $parts = $candidate -split " "
        $exe = $parts[0]
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        $rest = @($parts | Select-Object -Skip 1)
        try {
            & $exe @rest -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" *> $null
            if ($LASTEXITCODE -eq 0) { return $candidate }
        } catch { }
    }
    return $null
}

Write-Host "== 1/4 Python environment (.venv)"
if (Test-Path -LiteralPath ".venv") {
    Write-Host "   Updating the existing .venv. If Claude is running with ilias-mcp, quit it first:"
    Write-Host "   Windows does not let the update replace files of a running program."
}
$Python = Find-Python
if ($Python) {
    $parts = $Python -split " "
    $exe = $parts[0]
    $rest = @($parts | Select-Object -Skip 1)
    Invoke-Native $exe ($rest + @("-m", "venv", ".venv"))
    Write-Host "   $(& $VenvPython --version) - $Python"
    Invoke-Native $VenvPython @("-m", "pip", "install", "-q", "--upgrade", "pip")
    Invoke-Native $VenvPython @("-m", "pip", "install", "-q", "-e", ".")
} elseif (Get-Command uv -ErrorAction SilentlyContinue) {
    Invoke-Native "uv" @("venv", "-q", "-p", "3.12", ".venv")
    Invoke-Native "uv" @("pip", "install", "-q", "-p", $VenvPython, "-e", ".")
} else {
    Write-Host "   Python 3.10+ not found. Install it from https://www.python.org/downloads/"
    Write-Host "   (or: winget install Python.Python.3.12) and run this script again."
    exit 1
}

Write-Host ""
Write-Host "== 2/4 ILIAS username and password (Windows Credential Manager)"
$IliasUser = (Read-Host "   ILIAS username (firstname.lastname)").Trim()
if (-not $IliasUser) { Write-Host "   The username cannot be empty."; exit 1 }
& $VenvConfig has-password --user $IliasUser | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "   A saved password already exists."
    Write-Host "   (To replace it: .venv\Scripts\python -m keyring del $Service $IliasUser, then run this script again.)"
} else {
    Write-Host "   Type your ILIAS password and press Enter. Nothing is shown while you type;"
    Write-Host "   the password goes straight into Windows Credential Manager and is never written to a file."
    Invoke-Native $VenvPython @("-m", "keyring", "set", $Service, $IliasUser)
}
# A cache from version 0.2 or older records no account: asks whether it is this one's.
& $VenvConfig cache --user $IliasUser --ask

Write-Host ""
if ($SkipCheck) {
    Write-Host "== 3/4 Self-test skipped"
} else {
    Write-Host "== 3/4 Self-test (log in + 2 courses; roughly 20-45 requests, at most one per second)"
    $env:ILIAS_USER = $IliasUser
    & $VenvCheck --report selftest-report.json --dump .debug\pages
    $ok = ($LASTEXITCODE -eq 0)
    Remove-Item Env:ILIAS_USER
    if ($ok) {
        Write-Host "   Self-test passed."
    } else {
        Write-Host "   Part of the self-test failed; see selftest-report.json."
        Write-Host "   (A rejected password is not retried: replace the saved password and run this script again.)"
    }
}

Write-Host ""
Write-Host "== 4/4 Claude desktop app"
$Documents = [Environment]::GetFolderPath("MyDocuments")  # follows OneDrive folder redirection
if (-not $Documents) { $Documents = Join-Path $HOME "Documents" }
$DefaultRoot = Join-Path $Documents "ILIAS"
$DownloadRoot = (Read-Host "   Folder that ilias_download_file may write to [$DefaultRoot]").Trim()
if (-not $DownloadRoot) { $DownloadRoot = $DefaultRoot }
$Answer = Read-Host "   Add the 'ilias' server to the Claude configuration? (a backup is made first) [y/N]"
if ($Answer -match '^[yYeE]') {
    Invoke-Native $VenvConfig @("add", "--user", $IliasUser, "--download-root", $DownloadRoot)
    Write-Host "   Quit Claude completely and open it again. Closing the window is not enough:"
    Write-Host "   quit it from the tray icon next to the clock (or end it in Task Manager)."
} else {
    Invoke-Native $VenvConfig @("add", "--user", $IliasUser, "--download-root", $DownloadRoot, "--dry-run")
}

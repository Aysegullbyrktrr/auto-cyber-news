<#
.SYNOPSIS
    Windows PowerShell task runner mirroring the Unix Makefile targets.

.DESCRIPTION
    The project ships a Unix Makefile that assumes `make`, `python3`, and
    `.venv/bin/python` — none of which exist on a default Windows install.
    This script provides the same targets using Windows-native paths
    (`.venv\Scripts\`) and `$env:PYTHONPATH`.

.EXAMPLE
    .\make.ps1 setup
    .\make.ps1 test
    .\make.ps1 run-once
    .\make.ps1 -Python py setup    # use the `py` launcher as the base interpreter
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Task = 'help',

    # Base interpreter used to CREATE the virtualenv (setup only).
    # Defaults to `python`; pass `py` to use the Windows launcher.
    [string]$Python = 'python',

    # Extra arguments forwarded to the underlying command (e.g. pytest args).
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$VenvDir = Join-Path $Root '.venv'
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'

function Get-VenvPython {
    if (-not (Test-Path $VenvPython)) {
        throw "Virtualenv not found at $VenvDir. Run: .\make.ps1 setup"
    }
    return $VenvPython
}

# Run a module/command through the venv interpreter with PYTHONPATH=src,
# mirroring the Makefile's `PYTHONPATH=src $(PYTHON) ...` invocations.
function Invoke-App {
    param([string[]]$AppArgs)
    $py = Get-VenvPython
    $previous = $env:PYTHONPATH
    $env:PYTHONPATH = (Join-Path $Root 'src')
    try {
        & $py @AppArgs
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    finally {
        $env:PYTHONPATH = $previous
    }
}

function Invoke-Cli {
    param([string]$Command)
    $argv = @('-m', 'auto_cyber_news', $Command) + $Rest
    Invoke-App $argv
}

# Run every task from the project root so relative paths (src, tests) resolve
# regardless of the caller's current directory.
Push-Location $Root
try {
switch ($Task.ToLowerInvariant()) {
    'setup' {
        & $Python -m venv $VenvDir
        & $VenvPython -m pip install --upgrade pip
        & $VenvPython -m pip install -r (Join-Path $Root 'requirements-dev.txt')
        & $VenvPython -m pip install -e $Root
    }
    'install' {
        $py = Get-VenvPython
        & $py -m pip install -r (Join-Path $Root 'requirements-dev.txt')
        & $py -m pip install -e $Root
    }
    'validate' {
        & (Join-Path $Root 'make.ps1') lint
        & (Join-Path $Root 'make.ps1') typecheck
        & (Join-Path $Root 'make.ps1') test
    }
    'format' {
        $py = Get-VenvPython
        & $py -m ruff format src tests
    }
    'lint' {
        $py = Get-VenvPython
        & $py -m ruff check src tests
        & $py -m ruff format --check src tests
    }
    'typecheck' {
        $py = Get-VenvPython
        & $py -m mypy src
    }
    'test' {
        $py = Get-VenvPython
        & $py -m pytest @Rest
    }
    'init-db'          { Invoke-Cli 'init-db' }
    'migrate'          { Invoke-Cli 'migrate' }
    'db-status'        { Invoke-Cli 'db-status' }
    'run-once'         { Invoke-Cli 'run-once' }
    'run-ingestion'    { Invoke-Cli 'run-ingestion' }
    'run-analysis'     { Invoke-Cli 'run-analysis' }
    'run-scheduler'    { Invoke-Cli 'run-scheduler' }
    'send-test-telegram' { Invoke-Cli 'send-test-telegram' }
    'send-test-email'  { Invoke-Cli 'send-test-email' }
    'digest'           { Invoke-Cli 'digest' }
    'validate-config'  { Invoke-Cli 'validate-config' }
    'health-check'     { Invoke-Cli 'health-check' }
    'docker-build'     { docker build -t auto-cyber-news:local $Root }
    'docker-up'        { docker compose up --build }
    'docker-down'      { docker compose down }
    'clean' {
        foreach ($p in '.pytest_cache', '.mypy_cache', '.ruff_cache', 'htmlcov', '.coverage', 'build', 'dist') {
            $full = Join-Path $Root $p
            if (Test-Path $full) { Remove-Item -Recurse -Force $full }
        }
        Get-ChildItem -Path $Root -Filter '*.egg-info' -Directory -ErrorAction SilentlyContinue |
            Remove-Item -Recurse -Force
    }
    default {
        Write-Host @'
auto-cyber-news task runner (Windows)

Usage: .\make.ps1 <task> [-Python <python|py>] [extra args...]

Setup:
  setup              Create .venv and install dev deps + the package (editable)
  install            Reinstall deps into the existing .venv
  clean              Remove caches and build artifacts

Quality:
  validate           lint + typecheck + test
  format             ruff format
  lint               ruff check + format --check
  typecheck          mypy
  test [args]        pytest (extra args forwarded, e.g. .\make.ps1 test -k rss)

Database:
  init-db | migrate | db-status

Run:
  run-once | run-ingestion | run-analysis | run-scheduler
  digest | send-test-telegram | send-test-email
  validate-config | health-check

Docker:
  docker-build | docker-up | docker-down
'@
    }
}
}
finally {
    Pop-Location
}

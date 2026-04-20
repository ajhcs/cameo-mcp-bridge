$ErrorActionPreference = "Stop"

$pluginRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$repoRoot = (Resolve-Path (Join-Path $pluginRoot "..\..")).Path
$serverRoot = (Resolve-Path (Join-Path $repoRoot "mcp-server")).Path
$venvPython = Join-Path $serverRoot ".venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    $pythonCommand = $venvPython
    $pythonArgs = @()
} else {
    $pyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        $pythonCommand = $pyLauncher.Source
        $pythonArgs = @("-3")
    } else {
        $pythonFallback = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pythonFallback) {
            Write-Error "Unable to start cameo_mcp.server. Expected $venvPython, py.exe, or a Python interpreter on PATH."
        }
        $pythonCommand = $pythonFallback.Source
        $pythonArgs = @()
    }
}

Push-Location $serverRoot
try {
    & $pythonCommand @pythonArgs -c "import cameo_mcp.server" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Python interpreter '$pythonCommand' cannot import cameo_mcp.server from $serverRoot."
    }

    & $pythonCommand @pythonArgs -m cameo_mcp.server
    exit $LASTEXITCODE
} finally {
    Pop-Location
}

$ErrorActionPreference = "Stop"

$backendDirectory = $PSScriptRoot
$repositoryRoot = (Resolve-Path (Join-Path $backendDirectory "..\..")).Path
$virtualEnvironmentPython = Join-Path $repositoryRoot ".venv\Scripts\python.exe"

if (-not $env:COMPONENT3_SERIAL_PORT) {
    $env:COMPONENT3_SERIAL_PORT = "COM7"
}

if (-not (Test-Path -LiteralPath $virtualEnvironmentPython)) {
    throw "Repository virtual environment not found at $virtualEnvironmentPython"
}

Write-Host "Starting Component 4 with:" -ForegroundColor Cyan
Write-Host $virtualEnvironmentPython
Write-Host "ESP32 serial port: $env:COMPONENT3_SERIAL_PORT" -ForegroundColor Cyan

Set-Location -LiteralPath $backendDirectory
& $virtualEnvironmentPython -c "import torch, cv2; print(f'Torch {torch.__version__} | OpenCV {cv2.__version__}')"
& $virtualEnvironmentPython -m flask --app run.py run --debug

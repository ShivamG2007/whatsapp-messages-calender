# Starts the brain and the WhatsApp listener in two windows.
# Run from anywhere:  powershell -ExecutionPolicy Bypass -File scripts\start.ps1

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "No .venv found. Follow docs/SETUP.md first." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path (Join-Path $root "config\selected_chats.json"))) {
    Write-Host "No chats selected yet. Run:  cd listener; npm run pick" -ForegroundColor Yellow
    exit 1
}

Start-Process powershell -WorkingDirectory $root -ArgumentList "-NoExit", "-Command", "& '$python' -m brain serve"
Start-Sleep -Seconds 3
Start-Process powershell -WorkingDirectory (Join-Path $root "listener") -ArgumentList "-NoExit", "-Command", "npm start"
Write-Host "Brain and listener started in two new windows. Close them (or press Ctrl+C in each) to stop." -ForegroundColor Green

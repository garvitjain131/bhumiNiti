# Start the Land Policy Intelligence Platform locally: API on :8000, web app on :3000.
#   powershell -ExecutionPolicy Bypass -File .\start.ps1
# First time only: see README.md ("Set up once").
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path (Join-Path $root "db\lpip.duckdb"))) { Write-Host "Database not built. Run: $py etl\build_db.py" -ForegroundColor Red; exit 1 }
if (-not (Test-Path (Join-Path $root "web\.next"))) { Write-Host "Web app not built. Run: cd web; npm install; npx next build" -ForegroundColor Red; exit 1 }

Start-Process -FilePath $py -ArgumentList "-m", "uvicorn", "backend.app.main:app", "--port", "8000" -WorkingDirectory $root -WindowStyle Minimized
Start-Process -FilePath "npx.cmd" -ArgumentList "next", "start", "-p", "3000" -WorkingDirectory (Join-Path $root "web") -WindowStyle Minimized
Start-Sleep -Seconds 6
Write-Host "Platform: http://localhost:3000   API docs: http://localhost:3000/docs" -ForegroundColor Green
Write-Host "Demo accounts: db\demo_accounts.txt. Stop everything: powershell -ExecutionPolicy Bypass -File .\stop.ps1"
Start-Process "http://localhost:3000"

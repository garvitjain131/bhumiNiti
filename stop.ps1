# Stop the Land Policy Intelligence Platform completely: the API (:8000) and the web app (:3000), whether they were
# started by start.ps1 or in dev mode (python -m backend / npm run dev).
#   powershell -ExecutionPolicy Bypass -File .\stop.ps1
$ports = 8000, 3000
$pattern = 'uvicorn\s+backend\.app\.main|-m\s+backend\b|next(\.cmd)?"?\s+(start|dev)|next\\dist\\bin\\next|npm-cli\.js"?\s+run\s+dev'

# 1. every process whose command line is one of the platform's servers (and the cmd/npx wrappers around them)
$targets = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match $pattern })
# 2. whatever is still listening on the platform's ports, plus its parent (e.g. the Python launcher)
foreach ($c in Get-NetTCPConnection -State Listen -LocalPort $ports -ErrorAction SilentlyContinue) {
    $p = Get-CimInstance Win32_Process -Filter "ProcessId=$($c.OwningProcess)"
    if ($p) {
        $targets += $p
        $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($p.ParentProcessId)"
        # the venv's python.exe launcher, or npm's "cmd /c next ..." wrapper; never an interactive terminal shell
        if ($parent -and ($parent.Name -eq 'python.exe' -or ($parent.Name -in 'cmd.exe', 'node.exe' -and $parent.CommandLine -match 'next'))) {
            $targets += $parent
        }
    }
}

# 3. their child processes too (uvicorn's --reload worker inherits the port from the reloader)
$all = @(Get-CimInstance Win32_Process)
$ids = [System.Collections.Generic.HashSet[int]]::new()
foreach ($t in $targets) { [void]$ids.Add([int]$t.ProcessId) }
do {
    $added = 0
    foreach ($p in $all) {
        if ($ids.Contains([int]$p.ParentProcessId) -and $ids.Add([int]$p.ProcessId)) { $targets += $p; $added++ }
    }
} while ($added)

$stopped = 0
foreach ($p in $targets | Sort-Object ProcessId -Unique) {
    try {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
        Write-Host ("stopped {0,-6} {1}" -f $p.ProcessId, $p.Name)
        $stopped++
    } catch { }  # already exited with its parent
}

Start-Sleep -Seconds 1
$left = @(Get-NetTCPConnection -State Listen -LocalPort $ports -ErrorAction SilentlyContinue)
if ($left.Count) {
    Write-Host "Still listening on port(s) $(($left.LocalPort | Sort-Object -Unique) -join ', '); run this script as administrator." -ForegroundColor Red
    exit 1
}
if ($stopped) { Write-Host "Platform stopped: ports 8000 and 3000 are free." -ForegroundColor Green }
else { Write-Host "Nothing was running." -ForegroundColor Green }

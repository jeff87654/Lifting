Write-Host "=== GAP Processes ==="
$procs = Get-Process -Name "gap" -ErrorAction SilentlyContinue
if ($procs) {
    foreach ($p in $procs) {
        Write-Host ("PID: {0}, Memory: {1:N0} MB, CPU: {2:N1}s, StartTime: {3}" -f $p.Id, ($p.WorkingSet64/1MB), $p.CPU, $p.StartTime)
        try {
            $wmi = Get-CimInstance Win32_Process -Filter "ProcessId=$($p.Id)" -ErrorAction SilentlyContinue
            if ($wmi) {
                Write-Host ("  CommandLine: {0}" -f $wmi.CommandLine)
                $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($wmi.ParentProcessId)" -ErrorAction SilentlyContinue
                if ($parent) {
                    Write-Host ("  Parent PID: {0}, Parent Name: {1}" -f $parent.ProcessId, $parent.Name)
                }
            }
        } catch {
            Write-Host "  (Could not get details)"
        }
    }
} else {
    Write-Host "No gap.exe processes found."
}
Write-Host ""
Write-Host "=== Python Processes (possible GAP launchers) ==="
$pyprocs = Get-Process -Name "python","python3" -ErrorAction SilentlyContinue
if ($pyprocs) {
    foreach ($p in $pyprocs) {
        Write-Host ("PID: {0}, Memory: {1:N0} MB, CPU: {2:N1}s, StartTime: {3}" -f $p.Id, ($p.WorkingSet64/1MB), $p.CPU, $p.StartTime)
        try {
            $wmi = Get-CimInstance Win32_Process -Filter "ProcessId=$($p.Id)" -ErrorAction SilentlyContinue
            if ($wmi) { Write-Host ("  CommandLine: {0}" -f $wmi.CommandLine) }
        } catch {}
    }
} else {
    Write-Host "No python processes found."
}

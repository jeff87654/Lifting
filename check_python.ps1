Get-Process python*,bash* -ErrorAction SilentlyContinue | ForEach-Object {
    $wmi = Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue
    Write-Host "PID=$($_.Id) Name=$($_.Name) Start=$($_.StartTime) Cmd=$($wmi.CommandLine)"
}

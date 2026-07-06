$connections = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($connections) {
    foreach ($conn in $connections) {
        try {
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction Stop
            Write-Host "Stopped PID=$($conn.OwningProcess)"
        } catch {
            Write-Host "Failed to stop PID=$($conn.OwningProcess): $_"
        }
    }
} else {
    Write-Host 'No listener on port 8000'
}

$ErrorActionPreference = "Stop"
$host.UI.RawUI.WindowTitle = "HR Ops Platform"
$rootDir = (Get-Item ".").FullName

$cCyan   = "Cyan"
$cGreen  = "Green"
$cYellow = "Yellow"
$cGray   = "DarkGray"
$cGold   = "DarkYellow"
$cRed    = "Red"
$cWhite  = "White"

Write-Host "========================================" -ForegroundColor $cCyan
Write-Host "  Self-Healing HR Ops Platform"          -ForegroundColor $cCyan
Write-Host "========================================" -ForegroundColor $cCyan
Write-Host ""

# –– Kill any leftover processes on our ports ––
foreach ($port in @(8000, 5173)) {
    netstat -ano | Select-String ":$port" | Select-String "LISTENING" | ForEach-Object {
        if ($_ -match "(\d+)\s*$") { $procId = $Matches[1]; try { Stop-Process -Id $procId -Force -ErrorAction Stop; Write-Host "[CLEANUP] Killed PID $procId on port $port" -ForegroundColor $cYellow } catch {} }
    }
}
Start-Sleep 1

$python = if (Test-Path ".venv\Scripts\python.exe") { (Resolve-Path ".venv\Scripts\python.exe").Path }
          elseif (Test-Path "venv\Scripts\python.exe") { (Resolve-Path "venv\Scripts\python.exe").Path }
          else { "python" }

if (-not (Test-Path "frontend\node_modules")) {
    Write-Host "[PRE] Installing frontend dependencies..." -ForegroundColor $cYellow
    Push-Location frontend
    npm install; if (-not $?) { throw "npm install failed" }
    Pop-Location
}

function Start-RedirectedProcess($filePath, $arguments, $workingDir) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $filePath
    $psi.Arguments = $arguments
    $psi.WorkingDirectory = $workingDir
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $p = New-Object System.Diagnostics.Process
    $p.StartInfo = $psi
    $null = $p.Start()
    return $p
}

Write-Host "[1/4] Starting backend on http://localhost:8000 ..." -ForegroundColor $cGreen
$backend = Start-RedirectedProcess "cmd.exe" "/c $python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload" $rootDir
Write-Host "       BACKEND PID: $($backend.Id)" -ForegroundColor $cGray

Write-Host "[2/4] Starting frontend on http://localhost:5173 ..." -ForegroundColor $cGreen
$frontend = Start-RedirectedProcess "cmd.exe" "/c cd /d `"$rootDir\frontend`" && npm run dev" $rootDir
Write-Host "       FRONTEND PID: $($frontend.Id)" -ForegroundColor $cGray

Write-Host "[3/4] Waiting for backend to be ready..." -ForegroundColor $cGreen
$retries = 0; $healthy = $false
do {
    Start-Sleep -Seconds 2
    try {
        $req = [System.Net.WebRequest]::Create("http://localhost:8000/health")
        $req.Timeout = 3000
        $resp = $req.GetResponse()
        $healthy = $resp.StatusCode -eq 200
        $resp.Close()
    } catch {}
    $retries++
} while (-not $healthy -and $retries -le 90)

if (-not $healthy) {
    Write-Host "[WARN] Backend health check timed out after 3 minutes." -ForegroundColor $cYellow
} else {
    Start-Sleep -Seconds 3
    Write-Host "[4/4] Opening browser tabs..." -ForegroundColor $cGreen
    Start-Process "http://localhost:5173"
    Start-Sleep 1; Start-Process "http://localhost:8000/docs"
    Start-Sleep 1; Start-Process "http://localhost:8000/redoc"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor $cCyan
Write-Host "  HR Ops Platform is running!"            -ForegroundColor $cCyan
Write-Host "========================================" -ForegroundColor $cCyan
Write-Host "  Frontend:     http://localhost:5173"    -ForegroundColor $cWhite
Write-Host "  Backend API:  http://localhost:8000"    -ForegroundColor $cWhite
Write-Host "  Swagger Docs: http://localhost:8000/docs" -ForegroundColor $cWhite
Write-Host "  ReDoc Docs:   http://localhost:8000/redoc" -ForegroundColor $cWhite
Write-Host "========================================" -ForegroundColor $cCyan
Write-Host "  Close this window to stop all services"  -ForegroundColor $cYellow
Write-Host "========================================" -ForegroundColor $cCyan
Write-Host ""

try {
    do {
        $beLine = $backend.StandardOutput.ReadLine()
        if ($beLine) { Write-Host "[BACKEND] $beLine" -ForegroundColor $cGray }
        $beErr = $backend.StandardError.ReadLine()
        if ($beErr) { Write-Host "[BACKEND] $beErr" -ForegroundColor $cRed }

        $feLine = $frontend.StandardOutput.ReadLine()
        if ($feLine) { Write-Host "[FRONTEND] $feLine" -ForegroundColor $cGold }
        $feErr = $frontend.StandardError.ReadLine()
        if ($feErr) { Write-Host "[FRONTEND] $feErr" -ForegroundColor $cRed }

        $backendAlive  = -not $backend.HasExited
        $frontendAlive = -not $frontend.HasExited

        if (-not $backendAlive -and -not $frontendAlive) { break }
        if (-not $backendAlive) { Write-Host "[WARN] Backend exited" -ForegroundColor $cRed; break }
        if (-not $frontendAlive) { Write-Host "[WARN] Frontend exited" -ForegroundColor $cRed }

        Start-Sleep -Milliseconds 200
    } while ($backendAlive -or $frontendAlive)

} finally {
    if (-not $backend.HasExited) { $backend.Kill() }
    if (-not $frontend.HasExited) { $frontend.Kill() }
}

Write-Host "`nAll services stopped." -ForegroundColor $cYellow

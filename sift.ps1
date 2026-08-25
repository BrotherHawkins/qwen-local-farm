param(
    [Parameter(Position = 0)]
    [ValidateSet("setup", "start", "stop", "status", "ask", "pull", "logs")]
    [string]$Command = "status",

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$RunDir = Join-Path $Root ".run"
$GatewayPidFile = Join-Path $RunDir "gateway.pid"
$OllamaPidFile = Join-Path $RunDir "ollama.pid"
$GatewayOutLog = Join-Path $RunDir "gateway.out.log"
$GatewayErrLog = Join-Path $RunDir "gateway.err.log"
$OllamaOutLog = Join-Path $RunDir "ollama.out.log"
$OllamaErrLog = Join-Path $RunDir "ollama.err.log"

$Model = if ($env:SIFT_MODEL) { $env:SIFT_MODEL } else { "qwen3.5:4b" }
$OllamaBase = if ($env:OLLAMA_BASE_URL) { $env:OLLAMA_BASE_URL.TrimEnd("/") } else { "http://127.0.0.1:11434" }
$GatewayHost = if ($env:SIFT_GATEWAY_HOST) { $env:SIFT_GATEWAY_HOST } else { "127.0.0.1" }
$GatewayPort = if ($env:SIFT_GATEWAY_PORT) { [int]$env:SIFT_GATEWAY_PORT } else { 8765 }
$GatewayBase = "http://127.0.0.1:$GatewayPort"

function Ensure-RunDir {
    if (-not (Test-Path $RunDir)) {
        New-Item -ItemType Directory -Path $RunDir | Out-Null
    }
}

function Get-OllamaExe {
    $cmd = Get-Command ollama -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe",
        "$env:ProgramFiles\Ollama\ollama.exe",
        "${env:ProgramFiles(x86)}\Ollama\ollama.exe"
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) { return $candidate }
    }

    return $null
}

function Get-PythonExe {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $cmd = Get-Command py -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    throw "Python was not found on PATH. Install Python 3.10+ and retry."
}

function Test-Url {
    param([string]$Url)
    try {
        Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 2 | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Wait-Url {
    param(
        [string]$Url,
        [string]$Name,
        [int]$Seconds = 60
    )

    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Url $Url) { return }
        Start-Sleep -Seconds 1
    }

    throw "$Name did not become ready at $Url within $Seconds seconds."
}

function Test-OllamaReady {
    return Test-Url "$OllamaBase/api/tags"
}

function Start-Ollama {
    Ensure-RunDir

    if (Test-OllamaReady) {
        Write-Host "Ollama is already running at $OllamaBase"
        return
    }

    $ollama = Get-OllamaExe
    if (-not $ollama) {
        throw "Ollama is not installed. Run .\sift.ps1 setup first."
    }

    $env:OLLAMA_HOST = "127.0.0.1:11434"
    $proc = Start-Process -FilePath $ollama -ArgumentList @("serve") -WorkingDirectory $Root -WindowStyle Hidden -PassThru -RedirectStandardOutput $OllamaOutLog -RedirectStandardError $OllamaErrLog
    Set-Content -Path $OllamaPidFile -Value $proc.Id
    Wait-Url "$OllamaBase/api/tags" "Ollama" 90
    Write-Host "Ollama started at $OllamaBase"
}

function Ensure-Model {
    $ollama = Get-OllamaExe
    if (-not $ollama) {
        throw "Ollama is not installed. Run .\sift.ps1 setup first."
    }

    Start-Ollama

    $list = & $ollama list
    if ($list -match [regex]::Escape($Model)) {
        Write-Host "Model is available: $Model"
        return
    }

    Write-Host "Pulling $Model. This can take a while the first time."
    & $ollama pull $Model
}

function Start-Gateway {
    Ensure-RunDir

    if (Test-Url "$GatewayBase/health") {
        Write-Host "Agent gateway is already running at $GatewayBase"
        return
    }

    $python = Get-PythonExe
    $server = Join-Path $Root "src\sift_gateway.py"
    $env:SIFT_MODEL = $Model
    $env:OLLAMA_BASE_URL = $OllamaBase
    $env:SIFT_GATEWAY_HOST = $GatewayHost
    $env:SIFT_GATEWAY_PORT = "$GatewayPort"

    $proc = Start-Process -FilePath $python -ArgumentList @($server) -WorkingDirectory $Root -WindowStyle Hidden -PassThru -RedirectStandardOutput $GatewayOutLog -RedirectStandardError $GatewayErrLog
    Set-Content -Path $GatewayPidFile -Value $proc.Id
    Wait-Url "$GatewayBase/health" "Agent gateway" 30
    Write-Host "Agent gateway started at $GatewayBase"
}

function Stop-ProcessFromPidFile {
    param(
        [string]$PidFile,
        [string]$Name
    )

    if (-not (Test-Path $PidFile)) {
        Write-Host "$Name was not started by this script."
        return
    }

    $pidValue = Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pidValue) {
        $proc = Get-Process -Id ([int]$pidValue) -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-Process -Id $proc.Id -Force
            Write-Host "Stopped $Name."
        }
        else {
            Write-Host "$Name process was already stopped."
        }
    }

    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

function Install-Ollama {
    if (Get-OllamaExe) {
        Write-Host "Ollama is already installed."
        return
    }

    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "winget was not found. Install Ollama from https://ollama.com/download/windows, then rerun .\sift.ps1 setup."
    }

    Write-Host "Installing Ollama with winget..."
    winget install --id Ollama.Ollama --source winget --accept-package-agreements --accept-source-agreements
}

function Show-Status {
    Write-Host "Model: $Model"
    Write-Host "Ollama: $OllamaBase"
    Write-Host "Gateway: $GatewayBase"

    $gpu = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if ($gpu) {
        Write-Host ""
        Write-Host "GPU:"
        nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
    }

    Write-Host ""
    if (Test-OllamaReady) {
        Write-Host "Ollama status: running"
        try {
            $tags = Invoke-RestMethod -Uri "$OllamaBase/api/tags" -TimeoutSec 3
            if ($tags.models) {
                Write-Host "Installed models:"
                $tags.models | ForEach-Object { Write-Host "  $($_.name)" }
            }
        }
        catch {
            Write-Host "Could not list Ollama models: $($_.Exception.Message)"
        }
    }
    else {
        Write-Host "Ollama status: stopped or not installed"
    }

    if (Test-Url "$GatewayBase/health") {
        Write-Host "Gateway status: running"
    }
    else {
        Write-Host "Gateway status: stopped"
    }
}

function Invoke-AgentPrompt {
    $message = if ($Rest.Count -ge 1) { $Rest[0] } else { "" }
    $agent = if ($Rest.Count -ge 2) { $Rest[1] } else { "default" }

    if (-not $message) {
        throw 'Usage: .\sift.ps1 ask "your prompt here" [agent-id]'
    }

    if (-not (Test-Url "$GatewayBase/health")) {
        Write-Host "Gateway is not running; starting local service first."
        Ensure-Model
        Start-Gateway
    }

    $body = @{ message = $message } | ConvertTo-Json -Depth 5
    $response = Invoke-RestMethod -Uri "$GatewayBase/agents/$agent/chat" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 600
    $response.message.content
}

switch ($Command) {
    "setup" {
        Install-Ollama
        Ensure-Model
        Write-Host ""
        Write-Host "Setup complete. Run .\sift.ps1 start when you want the local service."
    }
    "start" {
        Ensure-Model
        Start-Gateway
        Write-Host ""
        Write-Host "Ready."
        Write-Host "OpenAI-compatible base URL: $OllamaBase/v1"
        Write-Host "Agent gateway: $GatewayBase"
    }
    "stop" {
        Stop-ProcessFromPidFile $GatewayPidFile "agent gateway"
        $ollama = Get-OllamaExe
        if ($ollama -and (Test-OllamaReady)) {
            try {
                $stopOutput = & $ollama stop $Model 2>&1
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "Unloaded model: $Model"
                }
                else {
                    Write-Host "Model was not loaded: $Model"
                    if ($stopOutput) { Write-Host ($stopOutput -join "`n") }
                }
            }
            catch {
                Write-Host "Model was not loaded: $Model"
            }
        }
        Stop-ProcessFromPidFile $OllamaPidFile "Ollama server"
    }
    "status" {
        Show-Status
    }
    "ask" {
        Invoke-AgentPrompt
    }
    "pull" {
        Ensure-Model
    }
    "logs" {
        Ensure-RunDir
        Write-Host "Gateway stdout: $GatewayOutLog"
        Get-Content $GatewayOutLog -Tail 40 -ErrorAction SilentlyContinue
        Write-Host ""
        Write-Host "Gateway stderr: $GatewayErrLog"
        Get-Content $GatewayErrLog -Tail 40 -ErrorAction SilentlyContinue
        Write-Host ""
        Write-Host "Ollama stderr: $OllamaErrLog"
        Get-Content $OllamaErrLog -Tail 40 -ErrorAction SilentlyContinue
    }
}

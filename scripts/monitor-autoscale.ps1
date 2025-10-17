#!/usr/bin/env powershell
# Monitor autoscale status
param(
    [string]$PoolId,
    [int]$Intervals = 10
)

# Load configuration
$ConfigFile = Join-Path $PSScriptRoot "..\config\config.json"

if (-not (Test-Path $ConfigFile)) {
    Write-Host "Error: Configuration file not found at $ConfigFile" -ForegroundColor Red
    Write-Host "Please create config\config.json from config\config.sample.json" -ForegroundColor Yellow
    exit 1
}

try {
    $Config = Get-Content $ConfigFile | ConvertFrom-Json
    if (-not $PoolId) {
        $PoolId = $Config.azure.batch.pool_id
    }
    $BatchAccountName = $Config.azure.batch.account_name
    $BatchAccountUrl = $Config.azure.batch.account_url
}
catch {
    Write-Host "Error: Could not read configuration" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

Write-Host "🔍 Monitoring autoscale for pool: $PoolId" -ForegroundColor Green
Write-Host "⏱️  Checking every 30 seconds for $Intervals intervals" -ForegroundColor Yellow
Write-Host ""

for ($i = 1; $i -le $Intervals; $i++) {
    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-Host "[$timestamp] Check $i/$Intervals" -ForegroundColor Cyan
    
    try {
        # Use Azure CLI with current authentication context (managed identity or user login)
        $result = az batch pool show --pool-id $PoolId --account-name $BatchAccountName --account-endpoint $BatchAccountUrl --query "{currentNodes:currentDedicatedNodes,targetNodes:targetDedicatedNodes,lastEval:autoScaleRun.timestamp,hasError:autoScaleRun.error,errorMessage:autoScaleRun.error.message,results:autoScaleRun.results}" --output json | ConvertFrom-Json
        
        Write-Host "  Current Nodes: $($result.currentNodes)" -ForegroundColor White
        Write-Host "  Target Nodes:  $($result.targetNodes)" -ForegroundColor White
        Write-Host "  Last Eval:     $($result.lastEval)" -ForegroundColor Gray
        
        if ($result.hasError) {
            Write-Host "  Status:        Error in autoscale evaluation" -ForegroundColor Red
            if ($result.errorMessage) {
                Write-Host "  Error:         $($result.errorMessage)" -ForegroundColor Red
            } else {
                Write-Host "  Error:         Insufficient sample data or evaluation pending" -ForegroundColor Yellow
            }
        } else {
            Write-Host "  Status:        Autoscale active!" -ForegroundColor Green
        }
        
        if ($result.targetNodes -gt 0) {
            Write-Host "🎉 Autoscale activated! Target nodes: $($result.targetNodes)" -ForegroundColor Green
            break
        }
    }
    catch {
        Write-Host "  Error checking pool status" -ForegroundColor Red
    }
    
    Write-Host ""
    if ($i -lt $Intervals) {
        Start-Sleep -Seconds 30
    }
}

Write-Host "✅ Monitoring complete!" -ForegroundColor Green
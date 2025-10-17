# Azure Container Registry Login Script (PowerShell)
# Authenticates to ACR using Azure CLI

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Azure Container Registry Login" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Load configuration
$ConfigFile = Join-Path $PSScriptRoot "..\config\config.json"

if (-not (Test-Path $ConfigFile)) {
    Write-Host "Error: Configuration file not found at $ConfigFile" -ForegroundColor Red
    Write-Host "Please create config\config.json from config\config.sample.json" -ForegroundColor Yellow
    exit 1
}

try {
    $Config = Get-Content $ConfigFile | ConvertFrom-Json
    $AcrName = $Config.azure.acr.name
}
catch {
    Write-Host "Error: Could not read ACR name from configuration" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

Write-Host "ACR Name: $AcrName" -ForegroundColor Green
Write-Host ""

# Check if Azure CLI is installed
$AzInstalled = Get-Command az -ErrorAction SilentlyContinue
if (-not $AzInstalled) {
    Write-Host "Error: Azure CLI (az) is not installed" -ForegroundColor Red
    Write-Host "Please install from: https://docs.microsoft.com/cli/azure/install-azure-cli" -ForegroundColor Yellow
    exit 1
}

# Check if logged in to Azure
Write-Host "Checking Azure CLI login status..." -ForegroundColor Yellow
try {
    az account show 2>&1 | Out-Null
}
catch {
    Write-Host "Not logged in to Azure. Running 'az login'..." -ForegroundColor Yellow
    az login
}

Write-Host ""
Write-Host "Logging in to Azure Container Registry: $AcrName" -ForegroundColor Yellow

try {
    az acr login --name $AcrName

    Write-Host ""
    Write-Host "✓ Successfully logged in to ACR: $AcrName" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can now build and push images to:" -ForegroundColor Cyan
    Write-Host "  ${AcrName}.azurecr.io" -ForegroundColor White
    Write-Host ""
}
catch {
    Write-Host ""
    Write-Host "✗ Failed to login to ACR" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

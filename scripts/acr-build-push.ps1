# Azure Container Registry Build and Push Script (PowerShell)
# Builds Docker image and pushes to ACR

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Docker Image Build and Push to ACR" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Load configuration
$ConfigFile = Join-Path $PSScriptRoot "..\config\config.json"

if (-not (Test-Path $ConfigFile)) {
    Write-Host "Error: Configuration file not found at $ConfigFile" -ForegroundColor Red
    exit 1
}

try {
    $Config = Get-Content $ConfigFile | ConvertFrom-Json
    $AcrName = $Config.azure.acr.name
    $AcrLoginServer = $Config.azure.acr.login_server
    $ImageName = $Config.azure.acr.image_name
    $ImageTag = $Config.azure.acr.image_tag
}
catch {
    Write-Host "Error: Could not read configuration" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

$FullImageName = "${AcrLoginServer}/${ImageName}:${ImageTag}"
$VersionTag = "${AcrLoginServer}/${ImageName}:v1.0.0"

Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  ACR Name: $AcrName"
Write-Host "  ACR Server: $AcrLoginServer"
Write-Host "  Image Name: $ImageName"
Write-Host "  Image Tag: $ImageTag"
Write-Host "  Full Image: $FullImageName"
Write-Host ""

# Check if Docker is running
try {
    docker info 2>&1 | Out-Null
}
catch {
    Write-Host "Error: Docker is not running" -ForegroundColor Red
    Write-Host "Please start Docker Desktop" -ForegroundColor Yellow
    exit 1
}

# Navigate to src directory
$SrcDir = Join-Path $PSScriptRoot "..\src"
Push-Location $SrcDir

Write-Host "Building Docker image..." -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Gray

try {
    docker build `
        -t $FullImageName `
        -t $VersionTag `
        --platform linux/amd64 `
        .

    Write-Host ""
    Write-Host "✓ Docker image built successfully" -ForegroundColor Green
}
catch {
    Write-Host ""
    Write-Host "✗ Docker build failed" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Pop-Location
    exit 1
}

Write-Host ""
Write-Host "Pushing image to ACR..." -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Gray

# Push both tags
try {
    docker push $FullImageName
    Write-Host "✓ Pushed: $FullImageName" -ForegroundColor Green
}
catch {
    Write-Host "✗ Failed to push $FullImageName" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Pop-Location
    exit 1
}

try {
    docker push $VersionTag
    Write-Host "✓ Pushed: $VersionTag" -ForegroundColor Green
}
catch {
    Write-Host "✗ Failed to push $VersionTag" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Pop-Location
    exit 1
}

Pop-Location

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "✓ Build and Push Complete" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Image available at:" -ForegroundColor Yellow
Write-Host "  - $FullImageName" -ForegroundColor White
Write-Host "  - $VersionTag" -ForegroundColor White
Write-Host ""
Write-Host "Verify with:" -ForegroundColor Yellow
Write-Host "  az acr repository show-tags --name $AcrName --repository $ImageName" -ForegroundColor White
Write-Host ""

#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Rebuild Docker image and resubmit batch job for testing

.DESCRIPTION
    This script:
    1. Builds and pushes the updated Docker image
    2. Recreates the batch pool (if needed)
    3. Submits a new test job
    4. Shows monitoring commands

.EXAMPLE
    .\scripts\rebuild-and-test.ps1
#>

param(
    [Parameter(Mandatory = $false)]
    [string]$ConfigPath = "config\config.json",
    
    [Parameter(Mandatory = $false)]
    [switch]$SkipBuild = $false,
    
    [Parameter(Mandatory = $false)]
    [switch]$RecreatePool = $false
)

# Set error action preference
$ErrorActionPreference = "Stop"

function Write-Status {
    param([string]$Message, [string]$Color = "Green")
    Write-Host $Message -ForegroundColor $Color
}

function Write-Error-Status {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Red
}

Write-Status "🔄 Azure Batch - Rebuild and Test" "Cyan"
Write-Status "=================================" "Cyan"

# Load configuration
if (-not (Test-Path $ConfigPath)) {
    Write-Error-Status "❌ Configuration file not found: $ConfigPath"
    Write-Error-Status "Please create config/config.json from config/config.sample.json"
    exit 1
}

$config = Get-Content $ConfigPath | ConvertFrom-Json
$azure = $config.azure

$acrName = $azure.acr.name
$acrLoginServer = $azure.acr.login_server
$imageName = $azure.acr.image_name
$imageTag = $azure.acr.image_tag
$poolId = $azure.batch.pool_id

Write-Status "📋 Configuration:"
Write-Status "  ACR: $acrLoginServer"
Write-Status "  Image: $imageName`:$imageTag"
Write-Status "  Pool: $poolId"
Write-Status ""

# Step 1: Build and push Docker image (unless skipped)
if (-not $SkipBuild) {
    Write-Status "🐳 Step 1: Building and pushing Docker image..."
    Write-Status "-------------------------------------------"
    
    try {
        # Login to ACR
        Write-Status "Logging in to ACR..."
        az acr login --name $acrName
        
        # Build image
        Write-Status "Building Docker image..."
        docker build -t "$acrLoginServer/$imageName`:$imageTag" src/
        
        if ($LASTEXITCODE -ne 0) {
            throw "Docker build failed"
        }
        
        # Push image
        Write-Status "Pushing image to ACR..."
        docker push "$acrLoginServer/$imageName`:$imageTag"
        
        if ($LASTEXITCODE -ne 0) {
            throw "Docker push failed"
        }
        
        Write-Status "✅ Docker image updated successfully"
        
    } catch {
        Write-Error-Status "❌ Failed to build/push Docker image: $_"
        exit 1
    }
} else {
    Write-Status "⏭️  Skipping Docker build (--SkipBuild specified)"
}

# Step 2: Recreate pool if requested
if ($RecreatePool) {
    Write-Status ""
    Write-Status "🏊 Step 2: Recreating Batch pool..."
    Write-Status "--------------------------------"
    
    try {
        python scripts\create-batch-pool-managed-identity.py
        Write-Status "✅ Pool recreated successfully"
    } catch {
        Write-Error-Status "❌ Failed to recreate pool: $_"
        Write-Status "⚠️  Continuing with existing pool..."
    }
} else {
    Write-Status ""
    Write-Status "⏭️  Skipping pool recreation (use --RecreatePool to recreate)"
}

# Step 3: Submit test job
Write-Status ""
Write-Status "📋 Step 3: Submitting test job..."
Write-Status "-------------------------------"

try {
    # Check if there are input files
    $sampleCount = (Get-ChildItem "samples\*.json" -ErrorAction SilentlyContinue).Count
    
    if ($sampleCount -eq 0) {
        Write-Status "No sample files found. Generating synthetic data..."
        python scripts\generate-synthetic-data.py --output samples\ --count 3
    }
    
    # Upload files to storage
    Write-Status "Uploading test files to storage..."
    python scripts\upload-to-storage.py --container batch-input --path samples\
    
    # Submit batch job
    Write-Status "Submitting batch job..."
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $jobId = "test-$timestamp"
    
    python scripts\submit-batch-job.py --pool-id $poolId --job-id $jobId
    
    Write-Status "✅ Job submitted successfully: $jobId"
    
} catch {
    Write-Error-Status "❌ Failed to submit job: $_"
    exit 1
}

# Step 4: Show monitoring commands
Write-Status ""
Write-Status "📊 Step 4: Monitoring Commands" "Cyan"
Write-Status "=============================" "Cyan"

$batchAccountName = $azure.batch.account_name
$batchAccountUrl = $azure.batch.account_url

Write-Status ""
Write-Status "Monitor job status:"
Write-Status "  az batch job show --job-id $jobId --account-name $batchAccountName --account-endpoint $batchAccountUrl" "Yellow"
Write-Status ""
Write-Status "List all tasks:"
Write-Status "  az batch task list --job-id $jobId --account-name $batchAccountName --account-endpoint $batchAccountUrl --output table" "Yellow"
Write-Status ""
Write-Status "Get task output (replace task-0 with actual task ID):"
Write-Status "  az batch task file download --job-id $jobId --task-id task-0 --file-path stdout.txt --destination logs\stdout.txt --account-name $batchAccountName --account-endpoint $batchAccountUrl" "Yellow"
Write-Status ""
Write-Status "Get task errors:"
Write-Status "  az batch task file download --job-id $jobId --task-id task-0 --file-path stderr.txt --destination logs\stderr.txt --account-name $batchAccountName --account-endpoint $batchAccountUrl" "Yellow"
Write-Status ""
Write-Status "Download results when complete:"
Write-Status "  python scripts\download-results.py --output results\" "Yellow"
Write-Status ""
Write-Status "🎯 Next Steps:"
Write-Status "1. Wait 2-3 minutes for tasks to start"
Write-Status "2. Use the monitoring commands above to check status"
Write-Status "3. Check Azure Portal → Batch Account → Jobs → $jobId for detailed status"
Write-Status "4. Look for task output files to verify container execution"
Write-Status ""
Write-Status "✨ Rebuild and test completed! Monitor the job progress using the commands above."
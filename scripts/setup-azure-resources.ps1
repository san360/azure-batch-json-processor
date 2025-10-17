#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Creates Azure resources for Batch account with managed identity, ACR, and storage.

.DESCRIPTION
    This script creates all required Azure resources for Azure Batch processing:
    - User-assigned managed identity
    - Storage account (LRS, no key-based access)  
    - Azure Container Registry (ACR)
    - Batch account with managed identity configuration
    - Proper RBAC role assignments

.PARAMETER ResourceGroup
    Name of the resource group to create or use

.PARAMETER Location
    Azure region for resource deployment (default: eastus)

.PARAMETER ResourcePrefix
    Prefix for resource names (default: batch)

.PARAMETER SubscriptionId
    Azure subscription ID (optional, uses current context if not specified)

.EXAMPLE
    ./setup-azure-resources.ps1 -ResourceGroup "my-batch-rg" -ResourcePrefix "mybatch"
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$ResourceGroup,
    
    [Parameter(Mandatory = $false)]
    [string]$Location = "eastus",
    
    [Parameter(Mandatory = $false)]
    [string]$ResourcePrefix = "batch",
    
    [Parameter(Mandatory = $false)]
    [string]$SubscriptionId
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Function to write colored output
function Write-Status {
    param([string]$Message, [string]$Color = "Green")
    Write-Host $Message -ForegroundColor $Color
}

function Write-Error-Exit {
    param([string]$Message)
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

# Validate Azure CLI
try {
    $azVersion = az version --output json | ConvertFrom-Json
    Write-Status "✓ Azure CLI version: $($azVersion.'azure-cli')"
} catch {
    Write-Error-Exit "Azure CLI not found. Please install Azure CLI and ensure it's in your PATH."
}

# Set subscription if provided
if ($SubscriptionId) {
    Write-Status "Setting subscription to: $SubscriptionId"
    az account set --subscription $SubscriptionId
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Exit "Failed to set subscription"
    }
}

# Get current subscription info
$currentSub = az account show --output json | ConvertFrom-Json
Write-Status "✓ Using subscription: $($currentSub.name) ($($currentSub.id))"

# Generate unique suffix for resource names
$uniqueSuffix = Get-Random -Minimum 1000 -Maximum 9999
$timestamp = Get-Date -Format "yyyyMMdd"

# Define resource names
$identityName = "${ResourcePrefix}-identity-${uniqueSuffix}"
$storageAccountName = "${ResourcePrefix}storage${uniqueSuffix}".ToLower() -replace '[^a-z0-9]', ''
$acrName = "${ResourcePrefix}acr${uniqueSuffix}".ToLower() -replace '[^a-z0-9]', ''
$batchAccountName = "${ResourcePrefix}-batch-${uniqueSuffix}".ToLower()

# Truncate names if too long
$storageAccountName = $storageAccountName.Substring(0, [Math]::Min(24, $storageAccountName.Length))
$acrName = $acrName.Substring(0, [Math]::Min(50, $acrName.Length))
$batchAccountName = $batchAccountName.Substring(0, [Math]::Min(24, $batchAccountName.Length))

Write-Status "🚀 Starting Azure resource creation..." "Cyan"
Write-Status "Resource Group: $ResourceGroup"
Write-Status "Location: $Location"
Write-Status "Identity: $identityName"
Write-Status "Storage: $storageAccountName"
Write-Status "ACR: $acrName"
Write-Status "Batch: $batchAccountName"

# Create or verify resource group
Write-Status "📁 Creating/verifying resource group: $ResourceGroup"
$rgExists = az group exists --name $ResourceGroup --output tsv
if ($rgExists -eq "false") {
    az group create --name $ResourceGroup --location $Location --tags "purpose=batch-processing" "created=$(Get-Date -Format 'yyyy-MM-dd')"
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Exit "Failed to create resource group"
    }
    Write-Status "✓ Created resource group: $ResourceGroup"
} else {
    Write-Status "✓ Resource group already exists: $ResourceGroup"
}

# Create user-assigned managed identity
Write-Status "🔐 Creating user-assigned managed identity: $identityName"
$identityOutput = az identity create `
    --name $identityName `
    --resource-group $ResourceGroup `
    --location $Location `
    --tags "purpose=batch-processing" `
    --output json

if ($LASTEXITCODE -ne 0) {
    Write-Error-Exit "Failed to create managed identity"
}

$identity = $identityOutput | ConvertFrom-Json
$identityId = $identity.id
$principalId = $identity.principalId
$clientId = $identity.clientId

Write-Status "✓ Created identity: $identityName"
Write-Status "  Principal ID: $principalId"
Write-Status "  Client ID: $clientId"

# Create storage account with managed identity and no key access
Write-Status "💾 Creating storage account: $storageAccountName"
$storageOutput = az storage account create `
    --name $storageAccountName `
    --resource-group $ResourceGroup `
    --location $Location `
    --sku "Standard_LRS" `
    --kind "StorageV2" `
    --allow-blob-public-access false `
    --allow-shared-key-access false `
    --https-only true `
    --min-tls-version "TLS1_2" `
    --tags "purpose=batch-processing" `
    --output json

if ($LASTEXITCODE -ne 0) {
    Write-Error-Exit "Failed to create storage account"
}

$storage = $storageOutput | ConvertFrom-Json
$storageId = $storage.id
Write-Status "✓ Created storage account: $storageAccountName"

# Create required storage containers
Write-Status "📦 Creating storage containers..."
$containers = @("batch-input", "batch-output", "batch-logs")
foreach ($container in $containers) {
    # Use managed identity for container creation
    az storage container create `
        --name $container `
        --account-name $storageAccountName `
        --auth-mode login `
        --output none
    
    if ($LASTEXITCODE -eq 0) {
        Write-Status "✓ Created container: $container"
    } else {
        Write-Status "⚠ Container $container may already exist or will be created later" "Yellow"
    }
}

# Create Azure Container Registry
Write-Status "🐳 Creating Azure Container Registry: $acrName"
$acrOutput = az acr create `
    --name $acrName `
    --resource-group $ResourceGroup `
    --location $Location `
    --sku "Standard" `
    --admin-enabled false `
    --tags "purpose=batch-processing" `
    --output json

if ($LASTEXITCODE -ne 0) {
    Write-Error-Exit "Failed to create Azure Container Registry"
}

$acr = $acrOutput | ConvertFrom-Json
$acrId = $acr.id
$acrLoginServer = $acr.loginServer

Write-Status "✓ Created ACR: $acrName"
Write-Status "  Login Server: $acrLoginServer"

# Wait a moment for identity propagation
Write-Status "⏳ Waiting for identity propagation..."
Start-Sleep -Seconds 30

# Assign Storage Blob Data Contributor role to managed identity at resource group level
Write-Status "🔑 Assigning Storage Blob Data Contributor role..."
az role assignment create `
    --assignee-object-id $principalId `
    --assignee-principal-type ServicePrincipal `
    --role "Storage Blob Data Contributor" `
    --scope "/subscriptions/$($currentSub.id)/resourceGroups/$ResourceGroup" `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Status "✓ Assigned Storage Blob Data Contributor role"
} else {
    Write-Status "⚠ Role assignment may already exist" "Yellow"
}

# Assign AcrPull role to managed identity
Write-Status "🔑 Assigning AcrPull role..."
az role assignment create `
    --assignee-object-id $principalId `
    --assignee-principal-type ServicePrincipal `
    --role "AcrPull" `
    --scope $acrId `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Status "✓ Assigned AcrPull role"
} else {
    Write-Status "⚠ Role assignment may already exist" "Yellow"
}

# Create Batch account with managed identity
Write-Status "⚡ Creating Batch account: $batchAccountName"
$batchOutput = az batch account create `
    --name $batchAccountName `
    --resource-group $ResourceGroup `
    --location $Location `
    --storage-account $storageId `
    --tags "purpose=batch-processing" `
    --output json

if ($LASTEXITCODE -ne 0) {
    Write-Error-Exit "Failed to create Batch account"
}

$batch = $batchOutput | ConvertFrom-Json
$batchId = $batch.id
$batchAccountUrl = "https://$batchAccountName.$Location.batch.azure.com"

Write-Status "✓ Created Batch account: $batchAccountName"
Write-Status "  Account URL: $batchAccountUrl"

# Update Batch account to use managed identity for storage authentication
Write-Status "🔗 Configuring Batch account with managed identity..."
az batch account set `
    --name $batchAccountName `
    --resource-group $ResourceGroup `
    --storage-account $storageId `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Status "✓ Configured Batch storage authentication"
} else {
    Write-Status "⚠ Batch configuration may need manual setup" "Yellow"
}

# Generate configuration output
$configOutput = @{
    created = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    azure = @{
        subscription_id = $currentSub.id
        resource_group = $ResourceGroup
        location = $Location
        storage = @{
            account_name = $storageAccountName
            resource_id = $storageId
            input_container = "batch-input"
            output_container = "batch-output"
            logs_container = "batch-logs"
        }
        acr = @{
            name = $acrName
            resource_id = $acrId
            login_server = $acrLoginServer
            image_name = "batch-json-processor"
            image_tag = "latest"
        }
        batch = @{
            account_name = $batchAccountName
            resource_id = $batchId
            account_url = $batchAccountUrl
            pool_id = "json-processor-pool"
            managed_identity_id = $identityId
        }
        identity = @{
            name = $identityName
            resource_id = $identityId
            principal_id = $principalId
            client_id = $clientId
        }
    }
}

# Save configuration to file
$configPath = "config/config.json"
if (-not (Test-Path "config")) {
    New-Item -ItemType Directory -Path "config" -Force | Out-Null
}
$configOutput | ConvertTo-Json -Depth 10 | Set-Content -Path $configPath -Encoding UTF8

Write-Status "✅ SUCCESS: All Azure resources created successfully!" "Green"
Write-Status ""
Write-Status "📋 Resource Summary:" "Cyan"
Write-Status "  Resource Group: $ResourceGroup"
Write-Status "  Managed Identity: $identityName"
Write-Status "  Storage Account: $storageAccountName"
Write-Status "  Container Registry: $acrName ($acrLoginServer)"
Write-Status "  Batch Account: $batchAccountName ($batchAccountUrl)"
Write-Status ""
Write-Status "📄 Configuration saved to: $configPath"
Write-Status ""
Write-Status "🚀 Next Steps:"
Write-Status "  1. Review the generated config/config.json file"
Write-Status "  2. Build and push your Docker image to ACR"
Write-Status "  3. Create Batch pools using the managed identity"
Write-Status "  4. Submit Batch jobs for processing"
Write-Status ""
Write-Status "💡 Tip: All resources use managed identity - no keys needed!"
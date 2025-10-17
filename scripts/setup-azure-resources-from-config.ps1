#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Creates Azure resources for Batch account using config.json settings.

.DESCRIPTION
    This script reads from config/config.json and creates all required Azure resources:
    - Resource group
    - User-assigned managed identity
    - Storage account (Standard_LRS, no key-based access)  
    - Azure Container Registry (Basic SKU)
    - Batch account with managed identity configuration
    - Storage Blob Data Contributor role assignments

.PARAMETER ConfigPath
    Path to config.json file (default: config/config.json)

.EXAMPLE
    ./setup-azure-resources-from-config.ps1
    ./setup-azure-resources-from-config.ps1 -ConfigPath "config/config.json"
#>

param(
    [Parameter(Mandatory = $false)]
    [string]$ConfigPath = "config/config.json"
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

# Read configuration file
if (-not (Test-Path $ConfigPath)) {
    Write-Error-Exit "Configuration file not found: $ConfigPath"
}

try {
    $config = Get-Content $ConfigPath | ConvertFrom-Json
    Write-Status "✓ Loaded configuration from: $ConfigPath"
} catch {
    Write-Error-Exit "Failed to parse configuration file: $ConfigPath"
}

# Extract configuration values
$subscriptionId = $config.azure.subscription_id
$resourceGroup = $config.azure.resource_group
$location = $config.azure.location
$storageAccountName = $config.azure.storage.account_name
$acrName = $config.azure.acr.name
$batchAccountName = $config.azure.batch.account_name

# Generate managed identity name from existing pattern or create new one
$identityName = if ($config.azure.batch.managed_identity_id) {
    ($config.azure.batch.managed_identity_id -split '/')[-1]
} else {
    "$resourceGroup-identity"
}

Write-Status "🚀 Starting Azure resource creation from config..." "Cyan"
Write-Status "Subscription: $subscriptionId"
Write-Status "Resource Group: $resourceGroup"
Write-Status "Location: $location"
Write-Status "Identity: $identityName"
Write-Status "Storage: $storageAccountName"
Write-Status "ACR: $acrName"
Write-Status "Batch: $batchAccountName"

# Set subscription
Write-Status "Setting subscription to: $subscriptionId"
az account set --subscription $subscriptionId
if ($LASTEXITCODE -ne 0) {
    Write-Error-Exit "Failed to set subscription"
}

# Get current subscription info
$currentSub = az account show --output json | ConvertFrom-Json
Write-Status "✓ Using subscription: $($currentSub.name) ($($currentSub.id))"

# Create resource group
Write-Status "📁 Creating resource group: $resourceGroup"
$rgExists = az group exists --name $resourceGroup --output tsv
if ($rgExists -eq "false") {
    az group create --name $resourceGroup --location $location --tags "purpose=batch-processing" "created=$(Get-Date -Format 'yyyy-MM-dd')"
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Exit "Failed to create resource group"
    }
    Write-Status "✓ Created resource group: $resourceGroup"
} else {
    Write-Status "✓ Resource group already exists: $resourceGroup"
}

# Create user-assigned managed identity
Write-Status "🔐 Creating user-assigned managed identity: $identityName"
$identityExists = az identity show --name $identityName --resource-group $resourceGroup --output json 2>$null
if (-not $identityExists) {
    $identityOutput = az identity create `
        --name $identityName `
        --resource-group $resourceGroup `
        --location $location `
        --tags "purpose=batch-processing" `
        --output json

    if ($LASTEXITCODE -ne 0) {
        Write-Error-Exit "Failed to create managed identity"
    }
    Write-Status "✓ Created identity: $identityName"
} else {
    $identityOutput = $identityExists
    Write-Status "✓ Identity already exists: $identityName"
}

$identity = $identityOutput | ConvertFrom-Json
$identityId = $identity.id
$principalId = $identity.principalId
$clientId = $identity.clientId

Write-Status "  Principal ID: $principalId"
Write-Status "  Client ID: $clientId"
Write-Status "  Resource ID: $identityId"

# Create storage account
Write-Status "💾 Creating storage account: $storageAccountName"
$storageExists = az storage account show --name $storageAccountName --resource-group $resourceGroup --output json 2>$null
if (-not $storageExists) {
    $storageOutput = az storage account create `
        --name $storageAccountName `
        --resource-group $resourceGroup `
        --location $location `
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
    Write-Status "✓ Created storage account: $storageAccountName"
} else {
    $storageOutput = $storageExists
    Write-Status "✓ Storage account already exists: $storageAccountName"
}

$storage = $storageOutput | ConvertFrom-Json
$storageId = $storage.id

# Create required storage containers
Write-Status "📦 Creating storage containers..."
$containers = @($config.azure.storage.input_container, $config.azure.storage.output_container, $config.azure.storage.logs_container)
foreach ($container in $containers) {
    az storage container create `
        --name $container `
        --account-name $storageAccountName `
        --auth-mode login `
        --output none 2>$null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Status "✓ Created container: $container"
    } else {
        Write-Status "⚠ Container $container may already exist" "Yellow"
    }
}

# Create Azure Container Registry with Basic SKU
Write-Status "🐳 Creating Azure Container Registry: $acrName"
$acrExists = az acr show --name $acrName --resource-group $resourceGroup --output json 2>$null
if (-not $acrExists) {
    $acrOutput = az acr create `
        --name $acrName `
        --resource-group $resourceGroup `
        --location $location `
        --sku "Basic" `
        --admin-enabled false `
        --tags "purpose=batch-processing" `
        --output json

    if ($LASTEXITCODE -ne 0) {
        Write-Error-Exit "Failed to create Azure Container Registry"
    }
    Write-Status "✓ Created ACR: $acrName"
} else {
    $acrOutput = $acrExists
    Write-Status "✓ ACR already exists: $acrName"
}

$acr = $acrOutput | ConvertFrom-Json
$acrId = $acr.id
$acrLoginServer = $acr.loginServer

Write-Status "  Login Server: $acrLoginServer"

# Wait for identity propagation
Write-Status "⏳ Waiting for identity propagation..."
Start-Sleep -Seconds 30

# Assign Storage Blob Data Contributor role to managed identity at resource group level
Write-Status "🔑 Assigning Storage Blob Data Contributor role..."
$roleAssignment = az role assignment list `
    --assignee $principalId `
    --role "Storage Blob Data Contributor" `
    --scope "/subscriptions/$($currentSub.id)/resourceGroups/$resourceGroup" `
    --output json | ConvertFrom-Json

if (-not $roleAssignment) {
    az role assignment create `
        --assignee-object-id $principalId `
        --assignee-principal-type ServicePrincipal `
        --role "Storage Blob Data Contributor" `
        --scope "/subscriptions/$($currentSub.id)/resourceGroups/$resourceGroup" `
        --output none

    if ($LASTEXITCODE -eq 0) {
        Write-Status "✓ Assigned Storage Blob Data Contributor role"
    } else {
        Write-Status "⚠ Failed to assign Storage Blob Data Contributor role" "Yellow"
    }
} else {
    Write-Status "✓ Storage Blob Data Contributor role already assigned"
}

# Assign AcrPull role to managed identity
Write-Status "🔑 Assigning AcrPull role..."
$acrRoleAssignment = az role assignment list `
    --assignee $principalId `
    --role "AcrPull" `
    --scope $acrId `
    --output json | ConvertFrom-Json

if (-not $acrRoleAssignment) {
    az role assignment create `
        --assignee-object-id $principalId `
        --assignee-principal-type ServicePrincipal `
        --role "AcrPull" `
        --scope $acrId `
        --output none

    if ($LASTEXITCODE -eq 0) {
        Write-Status "✓ Assigned AcrPull role"
    } else {
        Write-Status "⚠ Failed to assign AcrPull role" "Yellow"
    }
} else {
    Write-Status "✓ AcrPull role already assigned"
}

# Create Batch account
Write-Status "⚡ Creating Batch account: $batchAccountName"
$batchExists = az batch account show --name $batchAccountName --resource-group $resourceGroup --output json 2>$null
if (-not $batchExists) {
    $batchOutput = az batch account create `
        --name $batchAccountName `
        --resource-group $resourceGroup `
        --location $location `
        --storage-account $storageId `
        --tags "purpose=batch-processing" `
        --output json

    if ($LASTEXITCODE -ne 0) {
        Write-Error-Exit "Failed to create Batch account"
    }
    Write-Status "✓ Created Batch account: $batchAccountName"
} else {
    $batchOutput = $batchExists
    Write-Status "✓ Batch account already exists: $batchAccountName"
}

$batch = $batchOutput | ConvertFrom-Json
$batchId = $batch.id
$batchAccountUrl = "https://$batchAccountName.$location.batch.azure.com"

Write-Status "  Account URL: $batchAccountUrl"

# Update configuration file with actual values
Write-Status "📝 Updating configuration file..."
$config.azure.acr.login_server = $acrLoginServer
$config.azure.batch.account_url = $batchAccountUrl
$config.azure.batch.managed_identity_id = $identityId

# Add identity section if not exists
if (-not $config.azure.identity) {
    $config.azure | Add-Member -Type NoteProperty -Name "identity" -Value @{}
}
$config.azure.identity = @{
    name = $identityName
    resource_id = $identityId
    principal_id = $principalId
    client_id = $clientId
}

# Add resource IDs
if (-not $config.azure.storage.resource_id) {
    $config.azure.storage | Add-Member -Type NoteProperty -Name "resource_id" -Value $storageId
}
if (-not $config.azure.acr.resource_id) {
    $config.azure.acr | Add-Member -Type NoteProperty -Name "resource_id" -Value $acrId
}
if (-not $config.azure.batch.resource_id) {
    $config.azure.batch | Add-Member -Type NoteProperty -Name "resource_id" -Value $batchId
}

$config.azure.storage.resource_id = $storageId
$config.azure.acr.resource_id = $acrId
$config.azure.batch.resource_id = $batchId

# Save updated configuration
$config | ConvertTo-Json -Depth 10 | Set-Content -Path $ConfigPath -Encoding UTF8

Write-Status "✅ SUCCESS: All Azure resources created successfully!" "Green"
Write-Status ""
Write-Status "📋 Resource Summary:" "Cyan"
Write-Status "  Resource Group: $resourceGroup"
Write-Status "  Managed Identity: $identityName"
Write-Status "  Storage Account: $storageAccountName (Standard_LRS)"
Write-Status "  Container Registry: $acrName ($acrLoginServer) - Basic SKU"
Write-Status "  Batch Account: $batchAccountName ($batchAccountUrl)"
Write-Status ""
Write-Status "📄 Configuration updated in: $ConfigPath"
Write-Status ""
Write-Status "🚀 Next Steps:"
Write-Status "  1. Build and push your Docker image to ACR:"
Write-Status "     az acr login --name $acrName"
Write-Status "     docker build -t $acrLoginServer/$($config.azure.acr.image_name):$($config.azure.acr.image_tag) src/"
Write-Status "     docker push $acrLoginServer/$($config.azure.acr.image_name):$($config.azure.acr.image_tag)"
Write-Status "  2. Create Batch pools using the managed identity"
Write-Status "  3. Submit Batch jobs for processing"
Write-Status ""
Write-Status "💡 Tip: All resources use managed identity with Storage Blob Data Contributor - no keys needed!"
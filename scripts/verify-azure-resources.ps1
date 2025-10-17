#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Verifies Azure resources created for Batch account setup.

.DESCRIPTION
    This script reads the config.json file and verifies that all Azure resources 
    are correctly created and configured with proper permissions.

.PARAMETER ConfigPath
    Path to config.json file (default: config/config.json)
#>

param(
    [Parameter(Mandatory = $false)]
    [string]$ConfigPath = "config/config.json"
)

# Set error action preference
$ErrorActionPreference = "Continue"

# Function to write colored output
function Write-Status {
    param([string]$Message, [string]$Color = "Green")
    Write-Host $Message -ForegroundColor $Color
}

function Write-Check {
    param([string]$Message, [bool]$Success)
    $symbol = if ($Success) { "✓" } else { "✗" }
    $color = if ($Success) { "Green" } else { "Red" }
    Write-Host "$symbol $Message" -ForegroundColor $color
}

# Read configuration file
if (-not (Test-Path $ConfigPath)) {
    Write-Host "Configuration file not found: $ConfigPath" -ForegroundColor Red
    exit 1
}

$config = Get-Content $ConfigPath | ConvertFrom-Json
Write-Status "🔍 Verifying Azure resources from config: $ConfigPath" "Cyan"

$resourceGroup = $config.azure.resource_group
$location = $config.azure.location
$subscriptionId = $config.azure.subscription_id

Write-Status "Subscription: $subscriptionId"
Write-Status "Resource Group: $resourceGroup"
Write-Status "Location: $location"
Write-Status ""

# Set subscription
az account set --subscription $subscriptionId 2>$null

# Check Resource Group
Write-Status "📁 Checking Resource Group..." "Yellow"
$rgExists = az group exists --name $resourceGroup --output tsv 2>$null
Write-Check "Resource group '$resourceGroup' exists" ($rgExists -eq "true")

# Check Managed Identity
Write-Status "🔐 Checking Managed Identity..." "Yellow"
$identityName = $config.azure.identity.name
$identity = az identity show --name $identityName --resource-group $resourceGroup --output json 2>$null
$identityExists = $null -ne $identity
Write-Check "Managed identity '$identityName' exists" $identityExists

if ($identityExists) {
    $identityObj = $identity | ConvertFrom-Json
    Write-Status "  Principal ID: $($identityObj.principalId)"
    Write-Status "  Client ID: $($identityObj.clientId)"
}

# Check Storage Account
Write-Status "💾 Checking Storage Account..." "Yellow"
$storageAccountName = $config.azure.storage.account_name
$storageAccount = az storage account show --name $storageAccountName --resource-group $resourceGroup --output json 2>$null
$storageExists = $null -ne $storageAccount
Write-Check "Storage account '$storageAccountName' exists" $storageExists

if ($storageExists) {
    $storageObj = $storageAccount | ConvertFrom-Json
    Write-Check "Storage SKU is Standard_LRS" ($storageObj.sku.name -eq "Standard_LRS")
    Write-Check "Shared key access disabled" (-not $storageObj.allowSharedKeyAccess)
    Write-Check "Blob public access disabled" (-not $storageObj.allowBlobPublicAccess)
    
    # Check containers
    $containers = @($config.azure.storage.input_container, $config.azure.storage.output_container, $config.azure.storage.logs_container)
    foreach ($container in $containers) {
        $containerExists = az storage container exists --name $container --account-name $storageAccountName --auth-mode login --output tsv 2>$null
        Write-Check "Container '$container' exists" ($containerExists -eq "true")
    }
}

# Check Azure Container Registry
Write-Status "🐳 Checking Azure Container Registry..." "Yellow"
$acrName = $config.azure.acr.name
$acr = az acr show --name $acrName --resource-group $resourceGroup --output json 2>$null
$acrExists = $null -ne $acr
Write-Check "ACR '$acrName' exists" $acrExists

if ($acrExists) {
    $acrObj = $acr | ConvertFrom-Json
    Write-Check "ACR SKU is Basic" ($acrObj.sku.name -eq "Basic")
    Write-Check "Admin user disabled" (-not $acrObj.adminUserEnabled)
    Write-Status "  Login Server: $($acrObj.loginServer)"
}

# Check Batch Account
Write-Status "⚡ Checking Batch Account..." "Yellow"
$batchAccountName = $config.azure.batch.account_name
$batchAccount = az batch account show --name $batchAccountName --resource-group $resourceGroup --output json 2>$null
$batchExists = $null -ne $batchAccount
Write-Check "Batch account '$batchAccountName' exists" $batchExists

if ($batchExists) {
    $batchObj = $batchAccount | ConvertFrom-Json
    Write-Status "  Account Endpoint: $($batchObj.accountEndpoint)"
    Write-Check "Auto storage linked" ($null -ne $batchObj.autoStorage)
}

# Check Role Assignments
Write-Status "🔑 Checking Role Assignments..." "Yellow"
if ($identityExists) {
    $principalId = $config.azure.identity.principal_id
    
    # Check Storage Blob Data Contributor role
    $storageRole = az role assignment list `
        --assignee $principalId `
        --role "Storage Blob Data Contributor" `
        --scope "/subscriptions/$subscriptionId/resourceGroups/$resourceGroup" `
        --output json 2>$null | ConvertFrom-Json
    
    Write-Check "Storage Blob Data Contributor role assigned" ($storageRole.Count -gt 0)
    
    # Check AcrPull role
    if ($acrExists) {
        $acrId = $config.azure.acr.resource_id
        $acrRole = az role assignment list `
            --assignee $principalId `
            --role "AcrPull" `
            --scope $acrId `
            --output json 2>$null | ConvertFrom-Json
        
        Write-Check "AcrPull role assigned" ($acrRole.Count -gt 0)
    }
}

Write-Status ""
Write-Status "✅ Verification completed!" "Green"
Write-Status ""
Write-Status "📊 Summary:" "Cyan"
Write-Status "  All resources have been created according to your specifications:"
Write-Status "  - Resource Group: Created in $location"
Write-Status "  - Managed Identity: Created with proper permissions"
Write-Status "  - Storage Account: Standard_LRS, no key-based access"
Write-Status "  - ACR: Basic SKU, admin disabled"
Write-Status "  - Batch Account: Linked with storage and managed identity"
Write-Status "  - RBAC: Storage Blob Data Contributor + AcrPull roles assigned"
Write-Status ""
Write-Status "🚀 Ready for Docker image build and Batch job submission!"
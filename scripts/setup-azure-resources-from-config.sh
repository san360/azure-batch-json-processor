#!/bin/bash
#
# setup-azure-resources-from-config.sh
# Creates Azure resources for Batch account using config.json settings.
#
# This script reads from config/config.json and creates all required Azure resources:
# - Resource group
# - User-assigned managed identity
# - Storage account (Standard_LRS, no key-based access)  
# - Azure Container Registry (Basic SKU)
# - Batch account with managed identity configuration
# - Storage Blob Data Contributor role assignments
#
# Usage:
#   ./setup-azure-resources-from-config.sh [config-path]
#
# Example:
#   ./setup-azure-resources-from-config.sh
#   ./setup-azure-resources-from-config.sh config/config.json
#

set -euo pipefail

# Default values
CONFIG_PATH="${1:-config/config.json}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Functions
print_status() {
    echo -e "${GREEN}$1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}ERROR: $1${NC}"
    exit 1
}

print_header() {
    echo -e "${CYAN}$1${NC}"
}

# Validate dependencies
if ! command -v az &> /dev/null; then
    print_error "Azure CLI not found. Please install Azure CLI and ensure it's in your PATH."
fi

if ! command -v jq &> /dev/null; then
    print_error "jq not found. Please install jq for JSON parsing."
fi

AZ_VERSION=$(az version --output json | jq -r '."azure-cli"')
print_status "✓ Azure CLI version: $AZ_VERSION"

# Read configuration file
if [ ! -f "$CONFIG_PATH" ]; then
    print_error "Configuration file not found: $CONFIG_PATH"
fi

print_status "✓ Loaded configuration from: $CONFIG_PATH"

# Extract configuration values
SUBSCRIPTION_ID=$(jq -r '.azure.subscription_id' "$CONFIG_PATH")
RESOURCE_GROUP=$(jq -r '.azure.resource_group' "$CONFIG_PATH")
LOCATION=$(jq -r '.azure.location' "$CONFIG_PATH")
STORAGE_ACCOUNT_NAME=$(jq -r '.azure.storage.account_name' "$CONFIG_PATH")
ACR_NAME=$(jq -r '.azure.acr.name' "$CONFIG_PATH")
BATCH_ACCOUNT_NAME=$(jq -r '.azure.batch.account_name' "$CONFIG_PATH")

# Extract managed identity name from existing config or generate one
EXISTING_IDENTITY_ID=$(jq -r '.azure.batch.managed_identity_id // empty' "$CONFIG_PATH")
if [ -n "$EXISTING_IDENTITY_ID" ] && [ "$EXISTING_IDENTITY_ID" != "null" ]; then
    IDENTITY_NAME=$(basename "$EXISTING_IDENTITY_ID")
else
    IDENTITY_NAME="${RESOURCE_GROUP}-identity"
fi

print_header "🚀 Starting Azure resource creation from config..."
echo "Subscription: $SUBSCRIPTION_ID"
echo "Resource Group: $RESOURCE_GROUP"
echo "Location: $LOCATION"
echo "Identity: $IDENTITY_NAME"
echo "Storage: $STORAGE_ACCOUNT_NAME"
echo "ACR: $ACR_NAME"
echo "Batch: $BATCH_ACCOUNT_NAME"

# Set subscription
print_status "Setting subscription to: $SUBSCRIPTION_ID"
az account set --subscription "$SUBSCRIPTION_ID" || print_error "Failed to set subscription"

# Get current subscription info
CURRENT_SUB=$(az account show --output json)
SUB_NAME=$(echo "$CURRENT_SUB" | jq -r '.name')
SUB_ID=$(echo "$CURRENT_SUB" | jq -r '.id')
print_status "✓ Using subscription: $SUB_NAME ($SUB_ID)"

# Create resource group
print_status "📁 Creating resource group: $RESOURCE_GROUP"
if ! az group exists --name "$RESOURCE_GROUP" --output tsv | grep -q "true"; then
    az group create \
        --name "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --tags "purpose=batch-processing" "created=$(date '+%Y-%m-%d')" \
        || print_error "Failed to create resource group"
    print_status "✓ Created resource group: $RESOURCE_GROUP"
else
    print_status "✓ Resource group already exists: $RESOURCE_GROUP"
fi

# Create user-assigned managed identity
print_status "🔐 Creating user-assigned managed identity: $IDENTITY_NAME"
if IDENTITY_OUTPUT=$(az identity show --name "$IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" --output json 2>/dev/null); then
    print_status "✓ Identity already exists: $IDENTITY_NAME"
else
    IDENTITY_OUTPUT=$(az identity create \
        --name "$IDENTITY_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --tags "purpose=batch-processing" \
        --output json) || print_error "Failed to create managed identity"
    print_status "✓ Created identity: $IDENTITY_NAME"
fi

IDENTITY_ID=$(echo "$IDENTITY_OUTPUT" | jq -r '.id')
PRINCIPAL_ID=$(echo "$IDENTITY_OUTPUT" | jq -r '.principalId')
CLIENT_ID=$(echo "$IDENTITY_OUTPUT" | jq -r '.clientId')

print_status "  Principal ID: $PRINCIPAL_ID"
print_status "  Client ID: $CLIENT_ID"
print_status "  Resource ID: $IDENTITY_ID"

# Create storage account
print_status "💾 Creating storage account: $STORAGE_ACCOUNT_NAME"
if STORAGE_OUTPUT=$(az storage account show --name "$STORAGE_ACCOUNT_NAME" --resource-group "$RESOURCE_GROUP" --output json 2>/dev/null); then
    print_status "✓ Storage account already exists: $STORAGE_ACCOUNT_NAME"
else
    STORAGE_OUTPUT=$(az storage account create \
        --name "$STORAGE_ACCOUNT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --sku "Standard_LRS" \
        --kind "StorageV2" \
        --allow-blob-public-access false \
        --allow-shared-key-access false \
        --https-only true \
        --min-tls-version "TLS1_2" \
        --tags "purpose=batch-processing" \
        --output json) || print_error "Failed to create storage account"
    print_status "✓ Created storage account: $STORAGE_ACCOUNT_NAME"
fi

STORAGE_ID=$(echo "$STORAGE_OUTPUT" | jq -r '.id')

# Create required storage containers
print_status "📦 Creating storage containers..."
INPUT_CONTAINER=$(jq -r '.azure.storage.input_container' "$CONFIG_PATH")
OUTPUT_CONTAINER=$(jq -r '.azure.storage.output_container' "$CONFIG_PATH")
LOGS_CONTAINER=$(jq -r '.azure.storage.logs_container' "$CONFIG_PATH")

for CONTAINER in "$INPUT_CONTAINER" "$OUTPUT_CONTAINER" "$LOGS_CONTAINER"; do
    if az storage container create \
        --name "$CONTAINER" \
        --account-name "$STORAGE_ACCOUNT_NAME" \
        --auth-mode login \
        --output none 2>/dev/null; then
        print_status "✓ Created container: $CONTAINER"
    else
        print_warning "Container $CONTAINER may already exist"
    fi
done

# Create Azure Container Registry with Basic SKU
print_status "🐳 Creating Azure Container Registry: $ACR_NAME"
if ACR_OUTPUT=$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --output json 2>/dev/null); then
    print_status "✓ ACR already exists: $ACR_NAME"
else
    ACR_OUTPUT=$(az acr create \
        --name "$ACR_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --sku "Basic" \
        --admin-enabled false \
        --tags "purpose=batch-processing" \
        --output json) || print_error "Failed to create Azure Container Registry"
    print_status "✓ Created ACR: $ACR_NAME"
fi

ACR_ID=$(echo "$ACR_OUTPUT" | jq -r '.id')
ACR_LOGIN_SERVER=$(echo "$ACR_OUTPUT" | jq -r '.loginServer')
print_status "  Login Server: $ACR_LOGIN_SERVER"

# Wait for identity propagation
print_status "⏳ Waiting for identity propagation..."
sleep 30

# Assign Storage Blob Data Contributor role to managed identity at resource group level
print_status "🔑 Assigning Storage Blob Data Contributor role..."
RG_SCOPE="/subscriptions/$SUB_ID/resourceGroups/$RESOURCE_GROUP"
EXISTING_ROLE=$(az role assignment list \
    --assignee "$PRINCIPAL_ID" \
    --role "Storage Blob Data Contributor" \
    --scope "$RG_SCOPE" \
    --output json)

if [ "$(echo "$EXISTING_ROLE" | jq length)" -eq 0 ]; then
    if az role assignment create \
        --assignee-object-id "$PRINCIPAL_ID" \
        --assignee-principal-type ServicePrincipal \
        --role "Storage Blob Data Contributor" \
        --scope "$RG_SCOPE" \
        --output none 2>/dev/null; then
        print_status "✓ Assigned Storage Blob Data Contributor role"
    else
        print_warning "Failed to assign Storage Blob Data Contributor role"
    fi
else
    print_status "✓ Storage Blob Data Contributor role already assigned"
fi

# Assign AcrPull role to managed identity
print_status "🔑 Assigning AcrPull role..."
EXISTING_ACR_ROLE=$(az role assignment list \
    --assignee "$PRINCIPAL_ID" \
    --role "AcrPull" \
    --scope "$ACR_ID" \
    --output json)

if [ "$(echo "$EXISTING_ACR_ROLE" | jq length)" -eq 0 ]; then
    if az role assignment create \
        --assignee-object-id "$PRINCIPAL_ID" \
        --assignee-principal-type ServicePrincipal \
        --role "AcrPull" \
        --scope "$ACR_ID" \
        --output none 2>/dev/null; then
        print_status "✓ Assigned AcrPull role"
    else
        print_warning "Failed to assign AcrPull role"
    fi
else
    print_status "✓ AcrPull role already assigned"
fi

# Create Batch account
print_status "⚡ Creating Batch account: $BATCH_ACCOUNT_NAME"
if BATCH_OUTPUT=$(az batch account show --name "$BATCH_ACCOUNT_NAME" --resource-group "$RESOURCE_GROUP" --output json 2>/dev/null); then
    print_status "✓ Batch account already exists: $BATCH_ACCOUNT_NAME"
else
    BATCH_OUTPUT=$(az batch account create \
        --name "$BATCH_ACCOUNT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --storage-account "$STORAGE_ID" \
        --tags "purpose=batch-processing" \
        --output json) || print_error "Failed to create Batch account"
    print_status "✓ Created Batch account: $BATCH_ACCOUNT_NAME"
fi

BATCH_ID=$(echo "$BATCH_OUTPUT" | jq -r '.id')
BATCH_ACCOUNT_URL="https://$BATCH_ACCOUNT_NAME.$LOCATION.batch.azure.com"
print_status "  Account URL: $BATCH_ACCOUNT_URL"

# Update configuration file with actual values
print_status "📝 Updating configuration file..."

# Create temporary config with updated values
jq --arg login_server "$ACR_LOGIN_SERVER" \
   --arg batch_url "$BATCH_ACCOUNT_URL" \
   --arg identity_id "$IDENTITY_ID" \
   --arg storage_id "$STORAGE_ID" \
   --arg acr_id "$ACR_ID" \
   --arg batch_id "$BATCH_ID" \
   --arg identity_name "$IDENTITY_NAME" \
   --arg principal_id "$PRINCIPAL_ID" \
   --arg client_id "$CLIENT_ID" \
   '.azure.acr.login_server = $login_server |
    .azure.acr.resource_id = $acr_id |
    .azure.batch.account_url = $batch_url |
    .azure.batch.managed_identity_id = $identity_id |
    .azure.batch.resource_id = $batch_id |
    .azure.storage.resource_id = $storage_id |
    .azure.identity = {
        "name": $identity_name,
        "resource_id": $identity_id,
        "principal_id": $principal_id,
        "client_id": $client_id
    }' "$CONFIG_PATH" > "${CONFIG_PATH}.tmp" && mv "${CONFIG_PATH}.tmp" "$CONFIG_PATH"

IMAGE_NAME=$(jq -r '.azure.acr.image_name' "$CONFIG_PATH")
IMAGE_TAG=$(jq -r '.azure.acr.image_tag' "$CONFIG_PATH")

print_header "✅ SUCCESS: All Azure resources created successfully!"
echo ""
print_header "📋 Resource Summary:"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Managed Identity: $IDENTITY_NAME"
echo "  Storage Account: $STORAGE_ACCOUNT_NAME (Standard_LRS)"
echo "  Container Registry: $ACR_NAME ($ACR_LOGIN_SERVER) - Basic SKU"
echo "  Batch Account: $BATCH_ACCOUNT_NAME ($BATCH_ACCOUNT_URL)"
echo ""
print_status "📄 Configuration updated in: $CONFIG_PATH"
echo ""
print_header "🚀 Next Steps:"
echo "  1. Build and push your Docker image to ACR:"
echo "     az acr login --name $ACR_NAME"
echo "     docker build -t $ACR_LOGIN_SERVER/$IMAGE_NAME:$IMAGE_TAG src/"
echo "     docker push $ACR_LOGIN_SERVER/$IMAGE_NAME:$IMAGE_TAG"
echo "  2. Create Batch pools using the managed identity"
echo "  3. Submit Batch jobs for processing"
echo ""
print_status "💡 Tip: All resources use managed identity with Storage Blob Data Contributor - no keys needed!"
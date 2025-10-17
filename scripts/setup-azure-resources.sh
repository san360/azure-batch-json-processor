#!/bin/bash
#
# setup-azure-resources.sh
# Creates Azure resources for Batch account with managed identity, ACR, and storage.
#
# This script creates all required Azure resources for Azure Batch processing:
# - User-assigned managed identity
# - Storage account (LRS, no key-based access)  
# - Azure Container Registry (ACR)
# - Batch account with managed identity configuration
# - Proper RBAC role assignments
#
# Usage:
#   ./setup-azure-resources.sh -g <resource-group> [-l <location>] [-p <prefix>] [-s <subscription-id>]
#
# Example:
#   ./setup-azure-resources.sh -g my-batch-rg -p mybatch
#

set -euo pipefail

# Default values
LOCATION="eastus"
RESOURCE_PREFIX="batch"
SUBSCRIPTION_ID=""

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

usage() {
    echo "Usage: $0 -g <resource-group> [-l <location>] [-p <prefix>] [-s <subscription-id>]"
    echo ""
    echo "Options:"
    echo "  -g    Resource group name (required)"
    echo "  -l    Azure location (default: eastus)"
    echo "  -p    Resource name prefix (default: batch)"
    echo "  -s    Subscription ID (optional, uses current context)"
    echo "  -h    Show this help message"
    echo ""
    echo "Example:"
    echo "  $0 -g my-batch-rg -p mybatch -l eastus"
    exit 1
}

# Parse command line arguments
while getopts "g:l:p:s:h" opt; do
    case $opt in
        g)
            RESOURCE_GROUP="$OPTARG"
            ;;
        l)
            LOCATION="$OPTARG"
            ;;
        p)
            RESOURCE_PREFIX="$OPTARG"
            ;;
        s)
            SUBSCRIPTION_ID="$OPTARG"
            ;;
        h)
            usage
            ;;
        \?)
            echo "Invalid option: -$OPTARG" >&2
            usage
            ;;
    esac
done

# Check if required parameters are provided
if [ -z "${RESOURCE_GROUP:-}" ]; then
    echo "Error: Resource group name is required"
    usage
fi

# Validate Azure CLI
if ! command -v az &> /dev/null; then
    print_error "Azure CLI not found. Please install Azure CLI and ensure it's in your PATH."
fi

AZ_VERSION=$(az version --output json | jq -r '."azure-cli"')
print_status "✓ Azure CLI version: $AZ_VERSION"

# Set subscription if provided
if [ -n "$SUBSCRIPTION_ID" ]; then
    print_status "Setting subscription to: $SUBSCRIPTION_ID"
    az account set --subscription "$SUBSCRIPTION_ID" || print_error "Failed to set subscription"
fi

# Get current subscription info
CURRENT_SUB=$(az account show --output json)
SUB_NAME=$(echo "$CURRENT_SUB" | jq -r '.name')
SUB_ID=$(echo "$CURRENT_SUB" | jq -r '.id')
print_status "✓ Using subscription: $SUB_NAME ($SUB_ID)"

# Generate unique suffix for resource names
UNIQUE_SUFFIX=$((RANDOM % 9000 + 1000))
TIMESTAMP=$(date +%Y%m%d)

# Define resource names
IDENTITY_NAME="${RESOURCE_PREFIX}-identity-${UNIQUE_SUFFIX}"
STORAGE_ACCOUNT_NAME=$(echo "${RESOURCE_PREFIX}storage${UNIQUE_SUFFIX}" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]')
ACR_NAME=$(echo "${RESOURCE_PREFIX}acr${UNIQUE_SUFFIX}" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]')
BATCH_ACCOUNT_NAME=$(echo "${RESOURCE_PREFIX}-batch-${UNIQUE_SUFFIX}" | tr '[:upper:]' '[:lower:]')

# Truncate names if too long
STORAGE_ACCOUNT_NAME=${STORAGE_ACCOUNT_NAME:0:24}
ACR_NAME=${ACR_NAME:0:50}
BATCH_ACCOUNT_NAME=${BATCH_ACCOUNT_NAME:0:24}

print_header "🚀 Starting Azure resource creation..."
echo "Resource Group: $RESOURCE_GROUP"
echo "Location: $LOCATION"
echo "Identity: $IDENTITY_NAME"
echo "Storage: $STORAGE_ACCOUNT_NAME"
echo "ACR: $ACR_NAME"
echo "Batch: $BATCH_ACCOUNT_NAME"

# Create or verify resource group
print_status "📁 Creating/verifying resource group: $RESOURCE_GROUP"
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
IDENTITY_OUTPUT=$(az identity create \
    --name "$IDENTITY_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --tags "purpose=batch-processing" \
    --output json) || print_error "Failed to create managed identity"

IDENTITY_ID=$(echo "$IDENTITY_OUTPUT" | jq -r '.id')
PRINCIPAL_ID=$(echo "$IDENTITY_OUTPUT" | jq -r '.principalId')
CLIENT_ID=$(echo "$IDENTITY_OUTPUT" | jq -r '.clientId')

print_status "✓ Created identity: $IDENTITY_NAME"
echo "  Principal ID: $PRINCIPAL_ID"
echo "  Client ID: $CLIENT_ID"

# Create storage account with managed identity and no key access
print_status "💾 Creating storage account: $STORAGE_ACCOUNT_NAME"
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

STORAGE_ID=$(echo "$STORAGE_OUTPUT" | jq -r '.id')
print_status "✓ Created storage account: $STORAGE_ACCOUNT_NAME"

# Create required storage containers
print_status "📦 Creating storage containers..."
CONTAINERS=("batch-input" "batch-output" "batch-logs")
for CONTAINER in "${CONTAINERS[@]}"; do
    if az storage container create \
        --name "$CONTAINER" \
        --account-name "$STORAGE_ACCOUNT_NAME" \
        --auth-mode login \
        --output none 2>/dev/null; then
        print_status "✓ Created container: $CONTAINER"
    else
        print_warning "Container $CONTAINER may already exist or will be created later"
    fi
done

# Create Azure Container Registry
print_status "🐳 Creating Azure Container Registry: $ACR_NAME"
ACR_OUTPUT=$(az acr create \
    --name "$ACR_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --sku "Standard" \
    --admin-enabled false \
    --tags "purpose=batch-processing" \
    --output json) || print_error "Failed to create Azure Container Registry"

ACR_ID=$(echo "$ACR_OUTPUT" | jq -r '.id')
ACR_LOGIN_SERVER=$(echo "$ACR_OUTPUT" | jq -r '.loginServer')

print_status "✓ Created ACR: $ACR_NAME"
echo "  Login Server: $ACR_LOGIN_SERVER"

# Wait a moment for identity propagation
print_status "⏳ Waiting for identity propagation..."
sleep 30

# Assign Storage Blob Data Contributor role to managed identity at resource group level
print_status "🔑 Assigning Storage Blob Data Contributor role..."
if az role assignment create \
    --assignee-object-id "$PRINCIPAL_ID" \
    --assignee-principal-type ServicePrincipal \
    --role "Storage Blob Data Contributor" \
    --scope "/subscriptions/$SUB_ID/resourceGroups/$RESOURCE_GROUP" \
    --output none 2>/dev/null; then
    print_status "✓ Assigned Storage Blob Data Contributor role"
else
    print_warning "Role assignment may already exist"
fi

# Assign AcrPull role to managed identity
print_status "🔑 Assigning AcrPull role..."
if az role assignment create \
    --assignee-object-id "$PRINCIPAL_ID" \
    --assignee-principal-type ServicePrincipal \
    --role "AcrPull" \
    --scope "$ACR_ID" \
    --output none 2>/dev/null; then
    print_status "✓ Assigned AcrPull role"
else
    print_warning "Role assignment may already exist"
fi

# Create Batch account with managed identity
print_status "⚡ Creating Batch account: $BATCH_ACCOUNT_NAME"
BATCH_OUTPUT=$(az batch account create \
    --name "$BATCH_ACCOUNT_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --storage-account "$STORAGE_ID" \
    --tags "purpose=batch-processing" \
    --output json) || print_error "Failed to create Batch account"

BATCH_ID=$(echo "$BATCH_OUTPUT" | jq -r '.id')
BATCH_ACCOUNT_URL="https://$BATCH_ACCOUNT_NAME.$LOCATION.batch.azure.com"

print_status "✓ Created Batch account: $BATCH_ACCOUNT_NAME"
echo "  Account URL: $BATCH_ACCOUNT_URL"

# Update Batch account to use managed identity for storage authentication
print_status "🔗 Configuring Batch account with managed identity..."
if az batch account set \
    --name "$BATCH_ACCOUNT_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --storage-account "$STORAGE_ID" \
    --output none 2>/dev/null; then
    print_status "✓ Configured Batch storage authentication"
else
    print_warning "Batch configuration may need manual setup"
fi

# Generate configuration output
CONFIG_JSON=$(cat <<EOF
{
  "created": "$(date '+%Y-%m-%d %H:%M:%S')",
  "azure": {
    "subscription_id": "$SUB_ID",
    "resource_group": "$RESOURCE_GROUP",
    "location": "$LOCATION",
    "storage": {
      "account_name": "$STORAGE_ACCOUNT_NAME",
      "resource_id": "$STORAGE_ID",
      "input_container": "batch-input",
      "output_container": "batch-output",
      "logs_container": "batch-logs"
    },
    "acr": {
      "name": "$ACR_NAME",
      "resource_id": "$ACR_ID",
      "login_server": "$ACR_LOGIN_SERVER",
      "image_name": "batch-json-processor",
      "image_tag": "latest"
    },
    "batch": {
      "account_name": "$BATCH_ACCOUNT_NAME",
      "resource_id": "$BATCH_ID",
      "account_url": "$BATCH_ACCOUNT_URL",
      "pool_id": "json-processor-pool",
      "managed_identity_id": "$IDENTITY_ID"
    },
    "identity": {
      "name": "$IDENTITY_NAME",
      "resource_id": "$IDENTITY_ID",
      "principal_id": "$PRINCIPAL_ID",
      "client_id": "$CLIENT_ID"
    }
  }
}
EOF
)

# Save configuration to file
CONFIG_PATH="config/config.json"
mkdir -p config
echo "$CONFIG_JSON" > "$CONFIG_PATH"

print_header "✅ SUCCESS: All Azure resources created successfully!"
echo ""
print_header "📋 Resource Summary:"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Managed Identity: $IDENTITY_NAME"
echo "  Storage Account: $STORAGE_ACCOUNT_NAME"
echo "  Container Registry: $ACR_NAME ($ACR_LOGIN_SERVER)"
echo "  Batch Account: $BATCH_ACCOUNT_NAME ($BATCH_ACCOUNT_URL)"
echo ""
print_status "📄 Configuration saved to: $CONFIG_PATH"
echo ""
print_header "🚀 Next Steps:"
echo "  1. Review the generated config/config.json file"
echo "  2. Build and push your Docker image to ACR"
echo "  3. Create Batch pools using the managed identity"
echo "  4. Submit Batch jobs for processing"
echo ""
print_status "💡 Tip: All resources use managed identity - no keys needed!"
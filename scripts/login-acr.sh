#!/bin/bash

# Azure Container Registry Login Script
# Authenticates to ACR using Azure CLI

set -e  # Exit on error

echo "========================================"
echo "Azure Container Registry Login"
echo "========================================"

# Load configuration
CONFIG_FILE="../config/config.json"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Configuration file not found at $CONFIG_FILE"
    echo "Please create config/config.json from config/config.sample.json"
    exit 1
fi

# Extract ACR name from config
ACR_NAME=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['azure']['acr']['name'])" 2>/dev/null)

if [ -z "$ACR_NAME" ]; then
    echo "Error: Could not read ACR name from configuration"
    exit 1
fi

echo "ACR Name: $ACR_NAME"
echo ""

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "Error: Azure CLI (az) is not installed"
    echo "Please install from: https://docs.microsoft.com/cli/azure/install-azure-cli"
    exit 1
fi

# Check if logged in to Azure
echo "Checking Azure CLI login status..."
az account show &> /dev/null || {
    echo "Not logged in to Azure. Running 'az login'..."
    az login
}

echo ""
echo "Logging in to Azure Container Registry: $ACR_NAME"
az acr login --name "$ACR_NAME"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Successfully logged in to ACR: $ACR_NAME"
    echo ""
else
    echo ""
    echo "✗ Failed to login to ACR"
    exit 1
fi

echo "You can now build and push images to:"
echo "  ${ACR_NAME}.azurecr.io"
echo ""

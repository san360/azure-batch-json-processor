#!/bin/bash

# Azure Container Registry Build and Push Script
# Builds Docker image and pushes to ACR

set -e  # Exit on error

echo "========================================"
echo "Docker Image Build and Push to ACR"
echo "========================================"

# Load configuration
CONFIG_FILE="../config/config.json"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Configuration file not found at $CONFIG_FILE"
    exit 1
fi

# Extract ACR details from config
ACR_NAME=$(python3 -c "import json; config=json.load(open('$CONFIG_FILE')); print(config['azure']['acr']['name'])")
ACR_LOGIN_SERVER=$(python3 -c "import json; config=json.load(open('$CONFIG_FILE')); print(config['azure']['acr']['login_server'])")
IMAGE_NAME=$(python3 -c "import json; config=json.load(open('$CONFIG_FILE')); print(config['azure']['acr']['image_name'])")
IMAGE_TAG=$(python3 -c "import json; config=json.load(open('$CONFIG_FILE')); print(config['azure']['acr']['image_tag'])")

FULL_IMAGE_NAME="${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}"
VERSION_TAG="${ACR_LOGIN_SERVER}/${IMAGE_NAME}:v1.0.0"

echo "Configuration:"
echo "  ACR Name: $ACR_NAME"
echo "  ACR Server: $ACR_LOGIN_SERVER"
echo "  Image Name: $IMAGE_NAME"
echo "  Image Tag: $IMAGE_TAG"
echo "  Full Image: $FULL_IMAGE_NAME"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running"
    echo "Please start Docker Desktop"
    exit 1
fi

# Navigate to src directory
cd "$(dirname "$0")/../src"

echo "Building Docker image..."
echo "----------------------------------------"

docker build \
    -t "$FULL_IMAGE_NAME" \
    -t "$VERSION_TAG" \
    --platform linux/amd64 \
    .

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Docker image built successfully"
else
    echo ""
    echo "✗ Docker build failed"
    exit 1
fi

echo ""
echo "Pushing image to ACR..."
echo "----------------------------------------"

# Push both tags
docker push "$FULL_IMAGE_NAME"

if [ $? -eq 0 ]; then
    echo "✓ Pushed: $FULL_IMAGE_NAME"
else
    echo "✗ Failed to push $FULL_IMAGE_NAME"
    exit 1
fi

docker push "$VERSION_TAG"

if [ $? -eq 0 ]; then
    echo "✓ Pushed: $VERSION_TAG"
else
    echo "✗ Failed to push $VERSION_TAG"
    exit 1
fi

echo ""
echo "========================================"
echo "✓ Build and Push Complete"
echo "========================================"
echo ""
echo "Image available at:"
echo "  - $FULL_IMAGE_NAME"
echo "  - $VERSION_TAG"
echo ""
echo "Verify with:"
echo "  az acr repository show-tags --name $ACR_NAME --repository $IMAGE_NAME"
echo ""

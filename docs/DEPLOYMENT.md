# Deployment Guide - Azure Batch JSON Processor

This guide walks you through deploying the Azure Batch JSON processor from scratch.

## Prerequisites

### Required Azure Resources
You mentioned you already have:
- Azure Container Registry (ACR)
- Azure Batch Account with Managed Identity
- Azure Storage Account

### Required Tools
- Python 3.11 or higher
- Docker Desktop
- Azure CLI (`az`)
- Git
- Text editor (VS Code recommended)

### Required Permissions
- Contributor access to Azure Batch Account
- Contributor access to Storage Account
- AcrPush access to Container Registry
- Ability to assign RBAC roles

## Step 1: Clone/Setup Project

```bash
# Navigate to your project directory
cd c:\dev\azure-batch

# Verify project structure
dir
```

You should see:
```
docs/
scripts/
src/
samples/
config/
README.md
```

## Step 2: Configure Environment

### 2.1 Create Configuration File

```bash
# Copy sample configuration
copy config\config.sample.json config\config.json
```

### 2.2 Edit Configuration

Edit `config\config.json` with your Azure resource details:

```json
{
  "azure": {
    "subscription_id": "YOUR_SUBSCRIPTION_ID",
    "resource_group": "YOUR_RESOURCE_GROUP",
    "location": "eastus",

    "storage": {
      "account_name": "yourstorageaccount",
      "input_container": "batch-input",
      "output_container": "batch-output",
      "logs_container": "batch-logs"
    },

    "acr": {
      "name": "yourregistryname",
      "login_server": "yourregistryname.azurecr.io",
      "image_name": "batch-json-processor",
      "image_tag": "latest"
    },

    "batch": {
      "account_name": "yourbatchaccount",
      "account_url": "https://yourbatchaccount.eastus.batch.azure.com",
      "pool_id": "json-processor-pool",
      "managed_identity_id": "/subscriptions/YOUR_SUB_ID/resourceGroups/YOUR_RG/providers/Microsoft.ManagedIdentity/userAssignedIdentities/YOUR_IDENTITY"
    }
  }
}
```

### 2.3 Install Python Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

## Step 3: Setup Azure Storage

### 3.1 Create Storage Containers

```bash
# Login to Azure
az login

# Set subscription
az account set --subscription "YOUR_SUBSCRIPTION_ID"

# Create containers
az storage container create --name batch-input --account-name yourstorageaccount --auth-mode login
az storage container create --name batch-output --account-name yourstorageaccount --auth-mode login
az storage container create --name batch-logs --account-name yourstorageaccount --auth-mode login
```

### 3.2 Assign Managed Identity Permissions to Storage

```bash
# Get Managed Identity Principal ID
$IDENTITY_PRINCIPAL_ID = az identity show --ids /subscriptions/YOUR_SUB_ID/resourceGroups/YOUR_RG/providers/Microsoft.ManagedIdentity/userAssignedIdentities/YOUR_IDENTITY --query principalId -o tsv

# Get Storage Account Resource ID
$STORAGE_ID = az storage account show --name yourstorageaccount --resource-group YOUR_RG --query id -o tsv

# Assign "Storage Blob Data Contributor" role
az role assignment create --assignee $IDENTITY_PRINCIPAL_ID --role "Storage Blob Data Contributor" --scope $STORAGE_ID

# Verify role assignment
az role assignment list --assignee $IDENTITY_PRINCIPAL_ID --scope $STORAGE_ID
```

## Step 4: Setup Azure Container Registry

### 4.1 Verify ACR Access

```bash
# Login to ACR
az acr login --name yourregistryname

# Verify login
az acr repository list --name yourregistryname
```

### 4.2 Assign Managed Identity Permissions to ACR

```bash
# Get ACR Resource ID
$ACR_ID = az acr show --name yourregistryname --resource-group YOUR_RG --query id -o tsv

# Assign "AcrPull" role to Managed Identity
az role assignment create --assignee $IDENTITY_PRINCIPAL_ID --role "AcrPull" --scope $ACR_ID

# Verify role assignment
az role assignment list --assignee $IDENTITY_PRINCIPAL_ID --scope $ACR_ID
```

## Step 5: Build and Push Docker Image

### 5.1 Login to ACR (using script)

```bash
# Make script executable (if on Linux/Mac)
chmod +x scripts/login-acr.sh

# Run login script
.\scripts\login-acr.sh
```

### 5.2 Build and Push Image

```bash
# Run build and push script
.\scripts\acr-build-push.sh

# This will:
# 1. Build the Docker image locally
# 2. Tag it with ACR registry name
# 3. Push to ACR
# 4. Verify the push succeeded
```

### 5.3 Verify Image in ACR

```bash
# List images in ACR
az acr repository show-tags --name yourregistryname --repository batch-json-processor

# You should see:
# [
#   "latest",
#   "v1.0.0"
# ]
```

## Step 6: Configure Azure Batch Pool

### 6.1 Create Batch Pool with Container Configuration

You can create the pool via Azure Portal or using Azure CLI:

#### Option A: Azure Portal

1. Navigate to Azure Batch Account
2. Click "Pools" → "Add"
3. Configure:
   - **Pool ID**: `json-processor-pool`
   - **VM Size**: `Standard_D2s_v3`
   - **Scale**: Fixed (2 nodes) or Auto-scale
   - **Container Configuration**:
     - Type: Docker
     - Container Registry: Your ACR
     - Authentication: Managed Identity
   - **Identity**: Add your User-Assigned Managed Identity
4. Click "Create"

#### Option B: Azure CLI

Create a pool configuration JSON file `config/pool-config.json`:

```json
{
  "id": "json-processor-pool",
  "vmSize": "Standard_D2s_v3",
  "virtualMachineConfiguration": {
    "imageReference": {
      "publisher": "microsoft-azure-batch",
      "offer": "ubuntu-server-container",
      "sku": "20-04-lts",
      "version": "latest"
    },
    "nodeAgentSkuId": "batch.node.ubuntu 20.04",
    "containerConfiguration": {
      "type": "dockerCompatible",
      "containerImageNames": [
        "yourregistryname.azurecr.io/batch-json-processor:latest"
      ],
      "containerRegistries": [
        {
          "registryServer": "yourregistryname.azurecr.io",
          "identityReference": {
            "resourceId": "/subscriptions/YOUR_SUB_ID/resourceGroups/YOUR_RG/providers/Microsoft.ManagedIdentity/userAssignedIdentities/YOUR_IDENTITY"
          }
        }
      ]
    }
  },
  "targetDedicatedNodes": 2,
  "targetLowPriorityNodes": 0,
  "identity": {
    "type": "UserAssigned",
    "userAssignedIdentities": {
      "/subscriptions/YOUR_SUB_ID/resourceGroups/YOUR_RG/providers/Microsoft.ManagedIdentity/userAssignedIdentities/YOUR_IDENTITY": {}
    }
  }
}
```

Then create the pool:

```bash
az batch pool create --json-file config/pool-config.json --account-name yourbatchaccount
```

### 6.2 Verify Pool Status

```bash
# Check pool status
az batch pool show --pool-id json-processor-pool --account-name yourbatchaccount

# Wait for nodes to be ready (state: idle)
az batch node list --pool-id json-processor-pool --account-name yourbatchaccount
```

## Step 7: Generate and Upload Test Data

### 7.1 Generate Synthetic JSON Data

```bash
# Generate 5 files with 1000 transactions each
python scripts/generate-synthetic-data.py --count 1000 --files 5 --output ./samples/

# You should see files created:
# samples/sales_batch_20250117_143022_001.json
# samples/sales_batch_20250117_143022_002.json
# ...
```

### 7.2 Upload to Storage

```bash
# Upload all generated files to batch-input container
python scripts/upload-to-storage.py --container batch-input --path ./samples/

# Verify upload
az storage blob list --container-name batch-input --account-name yourstorageaccount --auth-mode login
```

## Step 8: Submit Batch Job

### 8.1 Run the Job Submission Script

```bash
# Submit batch job
python scripts/submit-batch-job.py --pool-id json-processor-pool --job-id sales-processing-001

# This will:
# 1. List all files in batch-input container
# 2. Create a Batch job
# 3. Create one task per file
# 4. Each task runs the Docker container with appropriate environment variables
```

### 8.2 Monitor Job Progress

```bash
# Check job status
az batch job show --job-id sales-processing-001 --account-name yourbatchaccount

# List tasks
az batch task list --job-id sales-processing-001 --account-name yourbatchaccount

# Get task details
az batch task show --job-id sales-processing-001 --task-id task-0 --account-name yourbatchaccount

# View task logs (stdout)
az batch task file download --job-id sales-processing-001 --task-id task-0 --file-path stdout.txt --destination ./logs/task-0-stdout.txt --account-name yourbatchaccount

# View task logs (stderr)
az batch task file download --job-id sales-processing-001 --task-id task-0 --file-path stderr.txt --destination ./logs/task-0-stderr.txt --account-name yourbatchaccount
```

## Step 9: Retrieve Results

### 9.1 Download Processed Files

```bash
# Download all results
python scripts/download-results.py --container batch-output --output ./results/

# Check results
dir ./results/
```

### 9.2 Review Results

Each output file will contain:
- Original data validation results
- Aggregated statistics
- Top customers and products
- Anomaly flags
- Processing metadata

Example output structure:
```json
{
  "input_file": "sales_batch_20250117_143022_001.json",
  "processed_at": "2025-01-17T14:35:10Z",
  "processing_time_seconds": 12.5,
  "validation": {
    "total_transactions": 1000,
    "valid_transactions": 998,
    "invalid_transactions": 2,
    "validation_errors": [...]
  },
  "analytics": {
    "total_revenue": 125450.75,
    "average_order_value": 125.45,
    "top_customers": [...],
    "top_products": [...],
    "revenue_by_category": {...}
  },
  "anomalies": {
    "high_value_transactions": 5,
    "suspicious_patterns": []
  }
}
```

## Step 10: Cleanup (Optional)

### 10.1 Delete Batch Job

```bash
az batch job delete --job-id sales-processing-001 --account-name yourbatchaccount --yes
```

### 10.2 Delete or Scale Down Pool

```bash
# Scale down to 0 nodes (keeps pool configuration)
az batch pool resize --pool-id json-processor-pool --target-dedicated-nodes 0 --target-low-priority-nodes 0 --account-name yourbatchaccount

# Or delete pool entirely
az batch pool delete --pool-id json-processor-pool --account-name yourbatchaccount --yes
```

### 10.3 Clean Up Storage (Optional)

```bash
# Delete containers
az storage container delete --name batch-input --account-name yourstorageaccount
az storage container delete --name batch-output --account-name yourstorageaccount
az storage container delete --name batch-logs --account-name yourstorageaccount
```

## Troubleshooting

### Issue: Container fails to authenticate to Storage

**Solution**:
- Verify Managed Identity is assigned to Batch Pool
- Verify RBAC role "Storage Blob Data Contributor" is assigned
- Check identity resource ID is correct in pool configuration

```bash
# Verify role assignment
az role assignment list --assignee $IDENTITY_PRINCIPAL_ID --all
```

### Issue: Container fails to pull from ACR

**Solution**:
- Verify Managed Identity has "AcrPull" role on ACR
- Verify ACR name and image name are correct
- Check ACR authentication is configured correctly in pool

```bash
# Test ACR access manually
az acr repository show --name yourregistryname --repository batch-json-processor
```

### Issue: Tasks fail with "command not found"

**Solution**:
- Verify Docker image was built correctly
- Check Dockerfile has correct CMD/ENTRYPOINT
- Review task command in job submission script

```bash
# Test container locally
docker run -it yourregistryname.azurecr.io/batch-json-processor:latest python --version
```

### Issue: Files not found in storage

**Solution**:
- Verify container names match configuration
- Check files were uploaded successfully
- Verify Managed Identity has read permissions

```bash
# List blobs
az storage blob list --container-name batch-input --account-name yourstorageaccount --auth-mode login
```

### Issue: Python dependencies missing in container

**Solution**:
- Verify requirements.txt is complete
- Rebuild Docker image
- Check Docker build logs for errors

```bash
# Rebuild with verbose output
docker build --no-cache -t yourregistryname.azurecr.io/batch-json-processor:latest ./src/
```

## Next Steps

### Automation with Azure Functions

To convert the manual trigger to Azure Function (future):

1. Create Azure Function App (Python 3.11)
2. Add Blob Trigger function
3. Copy logic from `submit-batch-job.py` into function
4. Deploy function
5. Test by uploading file to storage

See `docs/AZURE_FUNCTION_GUIDE.md` (to be created) for detailed steps.

### Monitoring Setup

1. Enable Application Insights for Batch Account
2. Create Azure Dashboard with key metrics
3. Set up alerts for task failures
4. Configure Log Analytics workspace

### CI/CD Pipeline

1. Create Azure DevOps or GitHub Actions pipeline
2. Automate Docker image build and push
3. Automate pool updates with new image
4. Run integration tests

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review Azure Batch documentation: https://docs.microsoft.com/azure/batch/
3. Review container logs in Batch task output
4. Check Azure Portal for error messages

## Summary Checklist

- [ ] Configuration file created and populated
- [ ] Python virtual environment setup
- [ ] Storage containers created
- [ ] Managed Identity permissions assigned (Storage + ACR)
- [ ] Docker image built and pushed to ACR
- [ ] Batch pool created with container configuration
- [ ] Pool nodes in "idle" state
- [ ] Test data generated and uploaded
- [ ] Batch job submitted successfully
- [ ] Tasks completed successfully
- [ ] Results downloaded and reviewed

Congratulations! Your Azure Batch JSON processor is now deployed and operational.

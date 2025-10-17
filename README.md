# Azure Batch JSON Processing

A complete Azure Batch solution for processing JSON files at scale using managed identity authentication and autoscaling. This project implements secure, scalable, and cost-effective batch processing with Docker containers.

## Project Overview

This project demonstrates Azure Batch for high-volume JSON data processing with these key features:

- **Managed Identity Only**: No storage keys or secrets required
- **Autoscaling**: Automatically scales 0-10 nodes based on workload
- **Container-based**: Docker containers with private ACR registry
- **Secure**: Role-based access control (RBAC) for all resources
- **Monitoring**: Built-in autoscaling and job monitoring

## Architecture

The solution uses these Azure services:

- **Azure Batch**: Pool management and job orchestration with autoscaling
- **Azure Container Registry (ACR)**: Private Docker image storage
- **Azure Storage**: Input/output blob storage with managed identity
- **Azure Resource Manager**: Infrastructure as Code templates

## Prerequisites

1. Azure CLI installed and authenticated
2. Docker Desktop (for local testing)
3. Python 3.8+ with required packages
4. PowerShell (for Windows scripts)

## Project Structure

```
azure-batch/
├── docs/
│   ├── ARCHITECTURE.md              # Detailed architecture documentation
│   ├── DEPLOYMENT.md               # Step-by-step deployment guide
│   └── FUTURE_AZURE_FUNCTION.md    # Future Azure Functions integration
├── scripts/
│   ├── generate-synthetic-data.py   # Generate sample JSON data
│   ├── upload-to-storage.py         # Upload files to Azure Storage
│   ├── login-acr.sh/ps1            # Login to Azure Container Registry
│   ├── acr-build-push.sh/ps1       # Build and push Docker image
│   ├── create-batch-pool-managed-identity.py  # Advanced pool with autoscaling
│   ├── monitor-autoscale.ps1        # Monitor autoscaling status
│   ├── submit-batch-job.py          # Submit processing jobs
│   └── download-results.py          # Download processed results
├── src/
│   ├── Dockerfile                   # Container definition
│   ├── requirements.txt             # Python dependencies
│   └── processor/
│       ├── __init__.py
│       ├── main.py                  # Main processing logic
│       ├── json_processor.py        # JSON processing functions
│       └── storage_helper.py        # Azure Storage utilities
├── samples/                         # Sample JSON files for testing
├── config/
│   ├── config.json                  # Your actual configuration
│   └── config.sample.json           # Sample configuration template
├── pool_config_debug.json           # Generated pool configuration
├── requirements.txt                 # Root Python dependencies
└── README.md                        # This file
```

## Setup Instructions

### 1. Clone and Configure

```bash
git clone https://github.com/san360/azure-batch-json-processor.git
cd azure-batch-json-processor
```

### 2. Configure Azure Resources

```bash
# Copy sample configuration
cp config/config.sample.json config/config.json

# Edit config.json with your Azure resource details:
# - Subscription ID
# - Resource Group
# - Batch Account
# - Storage Account
# - Container Registry
# - Managed Identity
```

### 3. Create Managed Identity and Assign Roles

```bash
# Create managed identity
az identity create --name batch-managed-identity --resource-group your-rg

# Get identity details
az identity show --name batch-managed-identity --resource-group your-rg

# Assign Storage Blob Data Contributor role
az role assignment create \
  --assignee PRINCIPAL_ID \
  --role "Storage Blob Data Contributor" \
  --scope /subscriptions/SUB_ID/resourceGroups/RG_NAME/providers/Microsoft.Storage/storageAccounts/STORAGE_NAME

# Assign AcrPull role for container registry
az role assignment create \
  --assignee PRINCIPAL_ID \
  --role "AcrPull" \
  --scope /subscriptions/SUB_ID/resourceGroups/RG_NAME/providers/Microsoft.ContainerRegistry/registries/ACR_NAME
```

### 4. Configure Batch Account for Managed Identity

```bash
# Configure autostorage with managed identity
az batch account set \
  --name your-batch-account \
  --resource-group your-rg \
  --storage-account your-storage-account \
  --storage-account-authentication-mode BatchAccountManagedIdentity

# Configure node identity reference
az batch account identity assign \
  --name your-batch-account \
  --resource-group your-rg \
  --user-assigned /subscriptions/SUB_ID/resourceGroups/RG_NAME/providers/Microsoft.ManagedIdentity/userAssignedIdentities/batch-managed-identity
```

### 5. Build and Push Docker Image

```bash
# Login to ACR
az acr login --name your-acr

# Build and push (using provided scripts)
.\scripts\acr-build-push.ps1
# or
./scripts/acr-build-push.sh
```

### 6. Generate Test Data

```bash
# Generate synthetic JSON files for testing
python scripts\generate-synthetic-data.py --count 10 --output .\samples\
```

### 7. Upload Files to Storage

```bash
# Upload test files
python scripts\upload-to-storage.py --container batch-input --path .\samples\
```

### 8. Create Autoscaling Batch Pool

```bash
# Create pool with autoscaling (0-10 nodes, scales based on active tasks)
python scripts\create-batch-pool-managed-identity.py
```

### 9. Submit Batch Job

```bash
# Submit job to process all files (uses managed identity)
python scripts\submit-batch-job.py --pool-id json-processor-pool
```

### 10. Monitor Autoscaling and Jobs

```bash
# Monitor autoscaling status
.\scripts\monitor-autoscale.ps1

# Check pool status
az batch pool show --pool-id json-processor-pool

# List running jobs
az batch job list

# Check task status
az batch task list --job-id JOB_ID
```

### 11. Download Results

```bash
# Download all processed files
python scripts\download-results.py --output .\results\
```

## Configuration

### config.json Structure

```json
{
  "azure": {
    "subscription_id": "your-subscription-id",
    "resource_group": "your-resource-group",
    "batch": {
      "account_name": "your-batch-account",
      "account_url": "https://your-batch-account.region.batch.azure.com",
      "pool_id": "json-processor-pool",
      "managed_identity_id": "/subscriptions/SUB_ID/resourceGroups/RG_NAME/providers/Microsoft.ManagedIdentity/userAssignedIdentities/batch-managed-identity"
    },
    "storage": {
      "account_name": "your-storage-account",
      "input_container": "batch-input",
      "output_container": "batch-output"
    },
    "acr": {
      "name": "your-acr",
      "login_server": "your-acr.azurecr.io",
      "image_name": "batch-json-processor",
      "image_tag": "latest"
    }
  }
}
```

## Autoscaling Configuration

The pool uses this autoscaling formula:

```javascript
// Scale 0-10 nodes based on active tasks (1 node per 3 tasks)
$TargetDedicatedNodes = min(10, max(0, ceil(avg($ActiveTasks.GetSample(TimeInterval_Minute * 5)) / 3)));
$NodeDeallocationOption = taskcompletion;
```

**Key Features:**

- **Minimum nodes**: 0 (cost-effective when idle)
- **Maximum nodes**: 10 (prevents runaway scaling)
- **Scaling ratio**: 1 node per 3 active tasks
- **Evaluation period**: 5-minute average of active tasks
- **Deallocation**: Waits for task completion before removing nodes

## Security

- **No secrets**: All authentication uses managed identity
- **Private registry**: Container images stored in private ACR
- **RBAC**: Principle of least privilege for all role assignments
- **Network isolation**: Optional VNet integration for enhanced security

### Managed Identity Setup

This project implements a **keyless authentication** architecture:

1. **Batch Account Configuration**:
   - User-assigned managed identity attached to Batch Account
   - Node identity reference configured for autostorage
   
2. **Pool Configuration**:
   - Pools created with user-assigned managed identity
   - Container registry authentication via identity reference
   
3. **Storage Access**:
   - Autostorage configured in `BatchAccountManagedIdentity` mode
   - No storage keys required for blob operations
   
4. **RBAC Assignments**:
   - Managed identity has `Storage Blob Data Contributor` role
   - `AcrPull` role for container registry access

## Cost Optimization

- **Autoscaling**: Scales to 0 nodes when idle
- **Spot instances**: Optional spot VM pricing for cost savings (70-90% savings)
- **Container reuse**: Efficient container image layering
- **Storage optimization**: Lifecycle policies for blob storage

## Performance

Expected processing times (approximate):

| File Size | Records | Processing Time | VM Size |
|-----------|---------|----------------|----------|
| 1 MB | 1,000 | 30 seconds | STANDARD_A1_V2 |
| 10 MB | 10,000 | 2 minutes | STANDARD_A1_V2 |
| 100 MB | 100,000 | 15 minutes | STANDARD_D2S_V3 |

## Future Enhancements

### Phase 2: Azure Function Automation

- Blob trigger to automatically start processing
- Event-driven architecture
- No manual script execution needed

### Phase 3: Advanced Analytics

- Machine learning model integration
- Real-time streaming with Event Hubs
- Power BI dashboard integration

### Phase 4: CI/CD Pipeline

- GitHub Actions / Azure DevOps
- Automated testing
- Continuous deployment

## Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Update documentation
5. Submit pull request

## License

MIT License - see LICENSE file for details

## Resources

- [Azure Batch Documentation](https://docs.microsoft.com/azure/batch/)
- [Azure Managed Identity](https://docs.microsoft.com/azure/active-directory/managed-identities-azure-resources/)
- [Azure Container Registry](https://docs.microsoft.com/azure/container-registry/)
- [Docker Documentation](https://docs.docker.com/)

---

**Built for scalable, secure, and efficient batch processing on Azure.**
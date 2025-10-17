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
│   ├── create-batch-pool.sh/ps1    # Create basic batch pool
│   ├── create-batch-pool-managed-identity.py  # Advanced pool with autoscaling
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
git clone [your-repo]
cd azure-batch
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
│   ├── create-batch-pool-managed-identity.py  # Create autoscaling pool with managed identity
│   ├── monitor-autoscale.ps1           # Monitor autoscaling status
│   ├── submit-batch-job.py             # Submit Batch job
│   └── download-results.py             # Download processed results
├── src/
│   ├── processor/
│   │   ├── main.py              # Main entry point
│   │   ├── json_processor.py    # Processing logic
│   │   ├── storage_helper.py    # Azure Storage operations
│   │   └── __init__.py
│   ├── Dockerfile               # Container definition
│   └── requirements.txt         # Python dependencies
├── config/
│   ├── config.sample.json       # Sample configuration
│   └── config.json              # Your configuration (create from sample)
├── samples/                     # Generated sample data (created by script)
├── results/                     # Downloaded results (created by script)
└── README.md                    # This file
```

## Prerequisites

### Azure Resources (You already have)
- Azure Container Registry (ACR)
- Azure Batch Account with Managed Identity enabled
- Azure Storage Account

### Local Tools
- Python 3.11 or higher
- Docker Desktop
- Azure CLI
- Git

## Quick Start

### 1. Clone and Setup

```bash
cd c:\dev\azure-batch
```

### 2. Configure

```bash
# Copy sample configuration
copy config\config.sample.json config\config.json

# Edit config\config.json with your Azure resource details
notepad config\config.json
```

### 3. Install Python Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Install dependencies
pip install -r src\requirements.txt
```

### 4. Generate Sample Data

```bash
# Generate 5 files with 1000 transactions each
python scripts\generate-synthetic-data.py --count 1000 --files 5 --output .\samples\
```

### 5. Upload to Storage

```bash
# Upload generated files
python scripts\upload-to-storage.py --container batch-input --path .\samples\
```

### 6. Create Autoscaling Batch Pool with Managed Identity

```bash
# Create autoscaling pool with managed identity (recommended)
python scripts\create-batch-pool-managed-identity.py

# Or create basic pool (PowerShell/Bash) - no autoscaling
.\scripts\create-batch-pool.ps1
# or
.\scripts\create-batch-pool.sh
```

**Autoscaling Features:**
- Scales from 0-10 nodes based on workload
- 1 node per 3 pending tasks
- 5-minute evaluation intervals
- Automatic scale-down when idle
- Cost-optimized (pay only when processing)

### 7. Build and Push Docker Image

```bash
# Login to ACR (PowerShell)
.\scripts\login-acr.ps1

# Build and push image (PowerShell)
.\scripts\acr-build-push.ps1
```

### 8. Submit Batch Job

```bash
# Submit job to process all files (uses managed identity)
python scripts\submit-batch-job.py --pool-id json-processor-pool
```

### 9. Monitor Autoscaling and Jobs

```bash
# Monitor autoscaling status
.\scripts\monitor-autoscale.ps1

# Check pool status
az batch pool show --pool-id json-processor-pool --account-name batchsan360 --account-endpoint https://batchsan360.swedencentral.batch.azure.com

# List running jobs
az batch job list --account-name batchsan360

# Check task status
az batch task list --job-id JOB_ID --account-name batchsan360
```

### 10. Download Results

```bash
# Monitor job status
az batch job list --query "[].{JobId:id, State:state}"

# Download results when complete
python scripts\download-results.py --output .\results\
```

## Configuration

The configuration is automatically managed by the setup scripts. Initial setup:

```powershell
# Copy sample configuration
copy config\config.sample.json config\config.json

# Edit with your basic settings (subscription, resource group, location, names)
notepad config\config.json

# Run setup script to create all resources and update config automatically
.\scripts\setup-azure-resources-from-config.ps1
```

After running the setup script, your `config\config.json` will contain:

```json
{
  "azure": {
    "subscription_id": "your-subscription-id",
    "resource_group": "your-resource-group", 
    "location": "eastus",
    "storage": {
      "account_name": "yourstorageaccount",
      "input_container": "batch-input",
      "output_container": "batch-output",
      "logs_container": "batch-logs",
      "resource_id": "/subscriptions/.../storageAccounts/yourstorageaccount"
    },
    "acr": {
      "name": "yourregistry",
      "login_server": "yourregistry.azurecr.io",
      "image_name": "batch-json-processor",
      "image_tag": "latest",
      "resource_id": "/subscriptions/.../registries/yourregistry"
    },
    "batch": {
      "account_name": "yourbatchaccount",
      "account_url": "https://yourbatchaccount.eastus.batch.azure.com",
      "pool_id": "json-processor-pool", 
      "managed_identity_id": "/subscriptions/.../userAssignedIdentities/your-identity",
      "resource_id": "/subscriptions/.../batchAccounts/yourbatchaccount"
    },
    "identity": {
      "name": "your-identity",
      "resource_id": "/subscriptions/.../userAssignedIdentities/your-identity",
      "principal_id": "principal-id-guid",
      "client_id": "client-id-guid"
    }
  }
}
```

## Detailed Documentation

- **[Architecture Documentation](docs/ARCHITECTURE.md)**: Detailed architecture, data flow, and design decisions
- **[Deployment Guide](docs/DEPLOYMENT.md)**: Step-by-step deployment instructions with troubleshooting

## Processing Logic

The processor performs the following operations on each JSON file:

1. **Validation**: Checks for required fields, data types, valid ranges
2. **Aggregation**: Calculates totals, averages, counts
3. **Customer Analytics**: Top customers, order counts, spending patterns
4. **Product Analytics**: Best-selling products, revenue by category
5. **Anomaly Detection**: High-value transactions, suspicious patterns
6. **Report Generation**: Comprehensive JSON output with all insights

### Input Format

```json
{
  "batch_id": "batch_20250117_143022",
  "transaction_count": 1000,
  "transactions": [
    {
      "transaction_id": "uuid",
      "timestamp": "2025-01-17T14:30:22Z",
      "customer": {...},
      "line_items": [...],
      "total": 125.45
    }
  ]
}
```

### Output Format

```json
{
  "batch_id": "batch_20250117_143022",
  "processed_at": "2025-01-17T14:35:22Z",
  "processing_time_seconds": 12.5,
  "validation": {
    "total_transactions": 1000,
    "valid_transactions": 998,
    "invalid_transactions": 2
  },
  "analytics": {
    "summary": {...},
    "top_customers": [...],
    "top_products": [...],
    "revenue_by_category": {...}
  },
  "anomalies": {
    "high_value_transactions": [...],
    "suspicious_patterns": [...]
  }
}
```

## Common Commands

## Advanced Usage

### Generate Data

```bash

### Upload Files
```bash
# Upload all JSON files from samples directory
python scripts\upload-to-storage.py --container batch-input --path .\samples\

# Upload single file
python scripts\upload-to-storage.py --container batch-input --path .\samples\file.json
```

### Build Docker Image
```bash
# Build locally (for testing)
cd src
docker build -t batch-json-processor:latest .

# Test locally
docker run -it batch-json-processor:latest python processor/main.py --help
```

### Monitor Batch Jobs
```bash
# List all jobs
az batch job list --output table

# Show job details
az batch job show --job-id YOUR_JOB_ID

# List tasks in a job
az batch task list --job-id YOUR_JOB_ID --output table

# View task logs
az batch task file download --job-id YOUR_JOB_ID --task-id task-0 --file-path stdout.txt --destination stdout.txt
```

### Download Results
```bash
# Download all results
python scripts\download-results.py --output .\results\

# Download specific prefix
python scripts\download-results.py --output .\results\ --prefix processed_batch_
```

## Troubleshooting

### Authentication Issues
```bash
# Re-login to Azure
az login

# Verify subscription
az account show

# Test ACR access
az acr login --name yourregistry
```

### Container Issues
```bash
# Test container locally
docker run -it yourregistry.azurecr.io/batch-json-processor:latest python --version

# Check container logs in Batch
az batch task file list --job-id YOUR_JOB_ID --task-id task-0
```

### Storage Issues
```bash
# List blobs
az storage blob list --container-name batch-input --account-name yourstorage --auth-mode login

# Check Managed Identity permissions
az role assignment list --assignee IDENTITY_PRINCIPAL_ID
```

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

## Performance

Expected processing times (approximate):

| File Size | Records | Processing Time | VM Size |
|-----------|---------|-----------------|---------|
| 1 MB      | 1,000   | 10-15 sec      | D2s_v3  |
| 10 MB     | 10,000  | 45-60 sec      | D2s_v3  |
| 100 MB    | 100,000 | 5-8 min        | D4s_v3  |

## Cost Optimization

- Use Low-Priority VMs for non-urgent workloads (80% savings)
- Enable auto-scale to match workload
- Set job termination policies
- Use lifecycle management for storage

## Security

- **Managed Identity Only**: No keys, connection strings, or secrets in code
- Azure Batch Account configured with User-Assigned Managed Identity
- Storage Account configured with `BatchAccountManagedIdentity` mode
- Container Registry authentication via managed identity
- RBAC for fine-grained access control (Storage Blob Data Contributor role)
- Network isolation with VNets (optional)

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

This setup ensures that:
- No secrets are stored in configuration files
- Authentication tokens are managed by Azure automatically
- Access permissions are controlled through Azure RBAC
- Credentials cannot be extracted or compromised from running tasks

## Contributing

This is a demonstration project. Feel free to:
- Customize processing logic for your use case
- Add new analytics or validation rules
- Integrate with your existing systems
- Extend with additional Azure services

## License

MIT License - feel free to use and modify for your needs.

## Support

For issues or questions:
1. Check [Deployment Guide](docs/DEPLOYMENT.md) troubleshooting section
2. Review Azure Batch documentation
3. Check container logs in Azure Portal
4. Review task output files

## Resources

- [Azure Batch Documentation](https://docs.microsoft.com/azure/batch/)
- [Azure Managed Identity](https://docs.microsoft.com/azure/active-directory/managed-identities-azure-resources/)
- [Azure Container Registry](https://docs.microsoft.com/azure/container-registry/)
- [Docker Documentation](https://docs.docker.com/)

---

**Built for scalable, secure, and efficient batch processing on Azure.**

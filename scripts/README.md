# Azure Batch Setup Scripts

This directory contains idempotent scripts to create and manage Azure resources for the Batch processing project.

## Scripts Overview

### 1. `setup-azure-resources-from-config.ps1` (PowerShell)
### 2. `setup-azure-resources-from-config.sh` (Bash)

These scripts read your `config/config.json` file and create all required Azure resources:

- ✅ **Resource Group**: Creates or verifies the resource group
- ✅ **User-Assigned Managed Identity**: Creates identity for secure authentication  
- ✅ **Storage Account**: Standard_LRS, no key-based access, HTTPS-only
- ✅ **Azure Container Registry**: Basic SKU, admin disabled
- ✅ **Batch Account**: Linked with storage and managed identity
- ✅ **RBAC Roles**: 
  - Storage Blob Data Contributor (at resource group level)
  - AcrPull (for container registry access)

### 3. `verify-azure-resources.ps1` (PowerShell)

Verification script that checks all resources are properly configured.

## Usage

### Prerequisites
- Azure CLI installed and authenticated (`az login`)
- PowerShell 5.1+ or Bash shell
- jq (for bash script JSON parsing)

### Running the Setup

**PowerShell:**
```powershell
.\scripts\setup-azure-resources-from-config.ps1
```

**Bash:**
```bash
./scripts/setup-azure-resources-from-config.sh
```

### Verification

```powershell
.\scripts\verify-azure-resources.ps1
```

## Configuration

All scripts read from `config/config.json`. The configuration structure is:

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
      "principal_id": "your-principal-id",
      "client_id": "your-client-id"
    }
  }
}
```

### Script Configuration Usage

| Script | Config Values Used |
|--------|-------------------|
| `setup-azure-resources-from-config.*` | All values (reads and updates config) |
| `verify-azure-resources.ps1` | All values for verification |
| `acr-build-push.*` | `acr.name`, `acr.login_server`, `acr.image_name`, `acr.image_tag` |
| `login-acr.*` | `acr.name` |
| `create-batch-pool-managed-identity.py` | `subscription_id`, `resource_group`, `batch.*`, `acr.*` |
| `submit-batch-job.py` | `storage.account_name`, `storage.*_container`, `batch.*`, `acr.*` |
| `upload-to-storage.py` | `storage.account_name`, containers |
| `download-results.py` | `storage.account_name`, `storage.output_container` |
| `monitor-autoscale.ps1` | `batch.pool_id`, `batch.account_name`, `batch.account_url` |

## What Gets Updated

After running the setup script, your config.json will be updated with:

- `azure.acr.login_server`: ACR login server URL
- `azure.batch.account_url`: Batch account endpoint URL  
- `azure.batch.managed_identity_id`: Full resource ID of the managed identity
- `azure.identity`: Complete identity information (name, IDs, etc.)
- Resource IDs for all created resources

## Security Features

✅ **Managed Identity Only**: No connection strings or access keys
✅ **RBAC-based**: Proper role assignments for least privilege access
✅ **Secure Storage**: No shared key access, HTTPS-only, TLS 1.2+
✅ **Private Registry**: ACR with admin disabled

## Idempotent Design

- Scripts can be run multiple times safely
- Existing resources are detected and skipped
- Role assignments are checked before creation
- No destructive operations

## Next Steps

After running the setup script successfully:

1. **Build and Push Docker Image:**
   ```bash
   az acr login --name <your-acr-name>
   docker build -t <acr-login-server>/batch-json-processor:latest src/
   docker push <acr-login-server>/batch-json-processor:latest
   ```

2. **Create Batch Pool:**
   ```bash
   python scripts/create-batch-pool-managed-identity.py
   ```

3. **Submit Jobs:**
   ```bash
   python scripts/submit-batch-job.py
   ```

## Troubleshooting

### Common Issues

1. **Permission Errors**: Ensure you have Contributor access to the subscription
2. **Name Conflicts**: Resource names must be globally unique (especially storage and ACR)
3. **Role Assignment Delays**: RBAC assignments can take a few minutes to propagate

### Verification Failures

If verification script shows failures:
- Wait a few minutes for role assignments to propagate
- Re-run the setup script (it's idempotent)
- Check Azure Portal for resource status

## Cost Optimization

- **ACR Basic SKU**: Lowest cost option for development
- **Standard_LRS Storage**: Most cost-effective redundancy option  
- **Batch Account**: Pay-per-use model, no upfront costs

## Clean Up

To delete all resources:
```bash
az group delete --name <resource-group-name> --yes --no-wait
```

**⚠️ Warning**: This will delete ALL resources in the resource group!
# Quick Start Guide

Get up and running with Azure Batch JSON Processor in 10 minutes.

## Prerequisites Checklist

- [ ] Python 3.11+ installed
- [ ] Docker Desktop installed and running
- [ ] Azure CLI installed
- [ ] Logged in to Azure (`az login`)
- [ ] Azure resources provisioned:
  - [ ] Azure Container Registry (ACR)
  - [ ] Azure Batch Account with Managed Identity
  - [ ] Azure Storage Account

## Step-by-Step Commands

### 1. Configure (2 minutes)

```bash
# Copy sample config
copy config\config.sample.json config\config.json

# Edit with your Azure details
notepad config\config.json
```

**Required fields to update:**
- `subscription_id`
- `resource_group`
- `storage.account_name`
- `acr.name` and `acr.login_server`
- `batch.account_name` and `batch.account_url`
- `batch.managed_identity_id`

### 2. Setup Python Environment (2 minutes)

```bash
# Create virtual environment
python -m venv venv

# Activate
.\venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### 3. Setup Azure Storage (1 minute)

```bash
# Create containers
az storage container create --name batch-input --account-name YOUR_STORAGE_ACCOUNT --auth-mode login
az storage container create --name batch-output --account-name YOUR_STORAGE_ACCOUNT --auth-mode login
az storage container create --name batch-logs --account-name YOUR_STORAGE_ACCOUNT --auth-mode login
```

### 4. Assign Managed Identity Permissions (2 minutes)

```powershell
# PowerShell
$IDENTITY_PRINCIPAL_ID = az identity show --ids "YOUR_MANAGED_IDENTITY_RESOURCE_ID" --query principalId -o tsv
$STORAGE_ID = az storage account show --name YOUR_STORAGE_ACCOUNT --resource-group YOUR_RG --query id -o tsv
$ACR_ID = az acr show --name YOUR_ACR --resource-group YOUR_RG --query id -o tsv

# Assign Storage access
az role assignment create --assignee $IDENTITY_PRINCIPAL_ID --role "Storage Blob Data Contributor" --scope $STORAGE_ID

# Assign ACR access
az role assignment create --assignee $IDENTITY_PRINCIPAL_ID --role "AcrPull" --scope $ACR_ID
```

### 5. Generate Sample Data (1 minute)

```bash
# Generate 3 files with 100 transactions each
python scripts\generate-synthetic-data.py --count 100 --files 3 --output .\samples\
```

### 6. Build and Push Docker Image (3 minutes)

```bash
# Login to ACR
.\scripts\login-acr.ps1

# Build and push
.\scripts\acr-build-push.ps1
```

### 7. Upload Test Data (1 minute)

```bash
python scripts\upload-to-storage.py --container batch-input --path .\samples\
```

### 8. Create Batch Pool (Portal or CLI)

**Option A: Azure Portal**
1. Go to Batch Account → Pools → Add
2. Pool ID: `json-processor-pool`
3. VM Size: `Standard_D2s_v3`
4. Scale: 2 dedicated nodes
5. Container Configuration:
   - Type: Docker
   - Registry: Your ACR
   - Image: `yourregistry.azurecr.io/batch-json-processor:latest`
   - Auth: Managed Identity
6. Identity: Add your User-Assigned Managed Identity
7. Create

**Option B: Wait for auto-scale** (if configured)

### 9. Submit Batch Job (1 minute)

```bash
python scripts\submit-batch-job.py --pool-id json-processor-pool
```

### 10. Monitor and Download Results (2-5 minutes)

```bash
# Monitor job
az batch job list --output table

# Check task status
az batch task list --job-id YOUR_JOB_ID --output table

# Download results when complete
python scripts\download-results.py --output .\results\
```

## Verify Success

Check `.\results\` folder for processed JSON files with:
- Validation results
- Analytics (revenue, customers, products)
- Anomaly detection results

## Common Issues

### "Job pool does not exist"
→ Create the Batch pool first (Step 8)

### "Authentication failed"
→ Run `az login` and verify you're in the correct subscription

### "Permission denied to storage"
→ Check Managed Identity has "Storage Blob Data Contributor" role

### "Cannot pull container image"
→ Check Managed Identity has "AcrPull" role on ACR

### Docker build fails
→ Ensure Docker Desktop is running

## Next Steps

- **Read**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture
- **Deploy**: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for full deployment guide
- **Automate**: [docs/FUTURE_AZURE_FUNCTION.md](docs/FUTURE_AZURE_FUNCTION.md) for Azure Function integration

## Daily Usage

Once set up, your workflow is:

```bash
# 1. Generate or receive new data files
python scripts\generate-synthetic-data.py --count 1000 --files 10

# 2. Upload to storage
python scripts\upload-to-storage.py --path .\samples\

# 3. Submit batch job (or automate with Azure Function)
python scripts\submit-batch-job.py --pool-id json-processor-pool

# 4. Download results
python scripts\download-results.py --output .\results\
```

## Help

- All scripts support `--help` flag
- Check [README.md](README.md) for detailed documentation
- Review logs in Azure Portal → Batch Account → Jobs → Tasks

---

**Total Setup Time: ~15 minutes**
**First Run Time: ~5 minutes** (including processing)

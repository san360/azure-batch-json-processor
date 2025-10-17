# Azure Batch Task Failure - Fix Plan and Resolution

## Issue Summary

**Error**: `python: can't open file '/mnt/batch/tasks/workitems/json-processing-20251017-231345/job-1/task-0/wd/python': [Errno 2] No such file or directory`

**Root Cause**: The Azure Batch task was trying to execute `python processor/main.py` on the host system instead of inside the Docker container where Python is available.

## Fixes Applied

### 1. ✅ Fixed Task Command Line
**File**: `scripts/submit-batch-job.py`

**Before**:
```python
task = TaskAddParameter(
    id=task_id,
    command_line="python processor/main.py",  # This was the problem!
    container_settings=container_settings,
    environment_settings=environment_settings
)
```

**After**:
```python
task = TaskAddParameter(
    id=task_id,
    command_line="",  # Empty command line lets container run its default CMD
    container_settings=container_settings,
    environment_settings=environment_settings
)
```

**Explanation**: When using Docker containers in Azure Batch, the `command_line` parameter runs on the **host system**, not inside the container. By using an empty command line, the container runs its default `CMD ["processor/main.py"]` which executes inside the container where Python is available.

### 2. ✅ Enhanced Container Settings
**File**: `scripts/submit-batch-job.py`

**Enhanced**:
```python
container_settings = TaskContainerSettings(
    image_name=acr_image,
    container_run_options="--rm --workdir /app"  # Ensure correct working directory
)
```

**Explanation**: Added explicit working directory to ensure the container starts in the correct location.

### 3. ✅ Improved Dockerfile for Debugging
**File**: `src/Dockerfile`

**Enhanced with startup script**:
```dockerfile
# Create a startup script for better debugging
RUN echo '#!/bin/bash' > /app/start.sh && \
    echo 'echo "=== Container Starting ==="' >> /app/start.sh && \
    echo 'echo "Working Directory: $(pwd)"' >> /app/start.sh && \
    echo 'echo "Python Version: $(python --version)"' >> /app/start.sh && \
    # ... more debugging info ...
    echo 'exec python -u processor/main.py "$@"' >> /app/start.sh && \
    chmod +x /app/start.sh

ENTRYPOINT ["/app/start.sh"]
CMD []
```

**Benefits**:
- Provides detailed logging when container starts
- Shows working directory, Python version, and file listings
- Helps troubleshoot environment issues
- Still runs the main application correctly

## New Tools Created

### 1. 🔄 Rebuild and Test Script
**File**: `scripts/rebuild-and-test.ps1`

**Usage**:
```powershell
# Full rebuild and test
.\scripts\rebuild-and-test.ps1

# Skip Docker build
.\scripts\rebuild-and-test.ps1 -SkipBuild

# Recreate pool
.\scripts\rebuild-and-test.ps1 -RecreatePool
```

**Features**:
- Builds and pushes Docker image
- Optionally recreates batch pool
- Submits test job
- Provides monitoring commands

### 2. 🔍 Troubleshooting Script
**File**: `scripts/troubleshoot.py`

**Usage**:
```bash
# Check pool status
python scripts/troubleshoot.py --check-pool

# Analyze job
python scripts/troubleshoot.py --job-id json-processing-20251017-231345

# Analyze specific task
python scripts/troubleshoot.py --job-id json-processing-20251017-231345 --task-id task-0
```

**Features**:
- Checks job and task status
- Downloads and displays task output files
- Analyzes pool configuration
- Provides detailed error analysis

## Testing Steps

### Step 1: Rebuild and Deploy
```powershell
# Navigate to project directory
cd C:\dev\azure-batch

# Run the rebuild script
.\scripts\rebuild-and-test.ps1
```

This will:
1. Build the updated Docker image
2. Push it to Azure Container Registry
3. Submit a test job
4. Provide monitoring commands

### Step 2: Monitor Job Progress
```bash
# Check job status
az batch job show --job-id test-YYYYMMDD-HHMMSS --account-name batchsan360 --account-endpoint https://batchsan360.eastus.batch.azure.com

# List tasks
az batch task list --job-id test-YYYYMMDD-HHMMSS --account-name batchsan360 --account-endpoint https://batchsan360.eastus.batch.azure.com --output table
```

### Step 3: Analyze Results
```bash
# Use troubleshooting script
python scripts/troubleshoot.py --job-id test-YYYYMMDD-HHMMSS

# Download task logs manually if needed
az batch task file download --job-id test-YYYYMMDD-HHMMSS --task-id task-0 --file-path stdout.txt --destination logs/stdout.txt --account-name batchsan360 --account-endpoint https://batchsan360.eastus.batch.azure.com
```

## Expected Results

After applying these fixes:

1. **Container should start successfully** with debugging output showing:
   - Working directory: `/app`
   - Python version information
   - File listings showing processor files are available

2. **Tasks should complete successfully** with:
   - Exit code: 0
   - Processing results uploaded to `batch-output` container
   - Execution logs uploaded to `batch-logs` container

3. **If issues persist**, the enhanced logging will provide detailed information about:
   - Container environment
   - File availability
   - Python execution path
   - Any remaining errors

## Common Issues and Solutions

### Issue: Container not found
**Solution**: Ensure ACR authentication is working:
```bash
az acr login --name azbatchacr
docker pull azbatchacr.azurecr.io/batch-json-processor:latest
```

### Issue: Pool nodes not starting
**Solution**: Check pool autoscale settings or manually set target nodes:
```bash
az batch pool resize --pool-id json-processor-pool --target-dedicated-nodes 1 --account-name batchsan360 --account-endpoint https://batchsan360.eastus.batch.azure.com
```

### Issue: Managed Identity permissions
**Solution**: Verify the managed identity has Storage Blob Data Contributor role:
```bash
az role assignment list --assignee e8471968-b071-4bec-8107-b7bab17f56fb --scope /subscriptions/1da52b57-468a-4dc6-ba36-1255cc1f6e8e/resourceGroups/azure-batch/providers/Microsoft.Storage/storageAccounts/batchsta
```

## Next Steps

1. **Run the rebuild script** to apply all fixes
2. **Monitor the job** using the provided commands
3. **Use the troubleshooting script** if issues occur
4. **Check Azure Portal** for visual job monitoring
5. **Review task output files** for detailed execution logs

The enhanced debugging in the Docker container should now provide much better visibility into what's happening during task execution, making it easier to identify and resolve any remaining issues.
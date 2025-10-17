# Azure Function Integration Guide (Future Enhancement)

This guide explains how to convert the manual trigger script into an automated Azure Function that triggers when new files are uploaded to Azure Storage.

## Overview

Currently, you manually run `submit-batch-job.py` to process files. With Azure Functions, you can automatically trigger batch processing when new JSON files arrive in the storage container.

## Architecture with Azure Function

```
[Upload File to Storage] → [Blob Trigger Function] → [Submit Batch Job] → [Azure Batch Processing]
```

## Prerequisites

- Azure Functions Core Tools
- Azure Functions Python runtime (Python 3.11)
- Existing Azure Function App (Consumption or Premium plan)

## Step 1: Create Function App

```bash
# Create Function App
az functionapp create \
  --resource-group YOUR_RESOURCE_GROUP \
  --consumption-plan-location eastus \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --name batch-trigger-function \
  --storage-account yourstorageaccount \
  --os-type Linux

# Assign Managed Identity
az functionapp identity assign \
  --name batch-trigger-function \
  --resource-group YOUR_RESOURCE_GROUP
```

## Step 2: Grant Permissions

The Function App needs:
1. Storage Blob Data Contributor (to read input container)
2. Batch Contributor (to submit jobs)

```bash
# Get Function App Managed Identity Principal ID
FUNCTION_IDENTITY=$(az functionapp identity show --name batch-trigger-function --resource-group YOUR_RESOURCE_GROUP --query principalId -o tsv)

# Grant Storage access
STORAGE_ID=$(az storage account show --name yourstorageaccount --resource-group YOUR_RESOURCE_GROUP --query id -o tsv)
az role assignment create --assignee $FUNCTION_IDENTITY --role "Storage Blob Data Contributor" --scope $STORAGE_ID

# Grant Batch access
BATCH_ID=$(az batch account show --name yourbatchaccount --resource-group YOUR_RESOURCE_GROUP --query id -o tsv)
az role assignment create --assignee $FUNCTION_IDENTITY --role "Batch Contributor" --scope $BATCH_ID
```

## Step 3: Function Code Structure

Create a new directory for the Azure Function:

```
function_app/
├── function_app.py          # Main function code
├── host.json                # Function host configuration
├── requirements.txt         # Python dependencies
└── .funcignore              # Files to ignore
```

### function_app.py

```python
import azure.functions as func
import logging
from datetime import datetime
from azure.batch import BatchServiceClient
from azure.batch.models import (
    JobAddParameter, PoolInformation, TaskAddParameter,
    TaskContainerSettings, EnvironmentSetting
)
from azure.identity import DefaultAzureCredential

app = func.FunctionApp()

@app.blob_trigger(
    arg_name="myblob",
    path="batch-input/{name}",
    connection="AzureWebJobsStorage"
)
def batch_trigger(myblob: func.InputStream):
    """
    Triggered when a new blob is uploaded to batch-input container.
    Creates an Azure Batch task to process the file.
    """
    logging.info(f"Blob trigger function processing: {myblob.name}")
    logging.info(f"Blob size: {myblob.length} bytes")

    # Extract blob name
    blob_name = myblob.name.split('/')[-1]

    # Only process JSON files
    if not blob_name.endswith('.json'):
        logging.info(f"Skipping non-JSON file: {blob_name}")
        return

    # Configuration (get from environment variables)
    batch_account_url = "https://yourbatchaccount.eastus.batch.azure.com"
    pool_id = "json-processor-pool"
    storage_account = "yourstorageaccount"
    input_container = "batch-input"
    output_container = "batch-output"
    acr_image = "yourregistry.azurecr.io/batch-json-processor:latest"

    # Authenticate with Managed Identity
    credential = DefaultAzureCredential()
    batch_client = BatchServiceClient(
        credential=credential,
        batch_url=batch_account_url
    )

    # Generate unique job ID
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    job_id = f"auto-{timestamp}-{blob_name.replace('.json', '')}"

    try:
        # Create job
        logging.info(f"Creating job: {job_id}")

        job = JobAddParameter(
            id=job_id,
            pool_info=PoolInformation(pool_id=pool_id)
        )
        batch_client.job.add(job)

        # Create task
        task_id = "task-0"

        environment_settings = [
            EnvironmentSetting(name="STORAGE_ACCOUNT_NAME", value=storage_account),
            EnvironmentSetting(name="INPUT_CONTAINER", value=input_container),
            EnvironmentSetting(name="OUTPUT_CONTAINER", value=output_container),
            EnvironmentSetting(name="INPUT_BLOB_NAME", value=blob_name),
            EnvironmentSetting(name="JOB_ID", value=job_id),
            EnvironmentSetting(name="TASK_ID", value=task_id),
        ]

        container_settings = TaskContainerSettings(
            image_name=acr_image,
            container_run_options="--rm"
        )

        task = TaskAddParameter(
            id=task_id,
            command_line="",
            container_settings=container_settings,
            environment_settings=environment_settings
        )

        batch_client.task.add(job_id=job_id, task=task)

        logging.info(f"✓ Successfully created job {job_id} with task {task_id}")
        logging.info(f"Processing file: {blob_name}")

    except Exception as e:
        logging.error(f"✗ Error creating batch job: {str(e)}")
        raise
```

### requirements.txt

```txt
azure-functions
azure-batch==14.0.0
azure-identity==1.15.0
azure-storage-blob==12.19.0
```

### host.json

```json
{
  "version": "2.0",
  "logging": {
    "applicationInsights": {
      "samplingSettings": {
        "isEnabled": true,
        "maxTelemetryItemsPerSecond": 20
      }
    }
  },
  "extensionBundle": {
    "id": "Microsoft.Azure.Functions.ExtensionBundle",
    "version": "[4.*, 5.0.0)"
  }
}
```

## Step 4: Configure Application Settings

```bash
# Set Batch account URL
az functionapp config appsettings set \
  --name batch-trigger-function \
  --resource-group YOUR_RESOURCE_GROUP \
  --settings BATCH_ACCOUNT_URL="https://yourbatchaccount.eastus.batch.azure.com"

# Set Pool ID
az functionapp config appsettings set \
  --name batch-trigger-function \
  --resource-group YOUR_RESOURCE_GROUP \
  --settings BATCH_POOL_ID="json-processor-pool"

# Set Storage account
az functionapp config appsettings set \
  --name batch-trigger-function \
  --resource-group YOUR_RESOURCE_GROUP \
  --settings STORAGE_ACCOUNT_NAME="yourstorageaccount"

# Set ACR image
az functionapp config appsettings set \
  --name batch-trigger-function \
  --resource-group YOUR_RESOURCE_GROUP \
  --settings ACR_IMAGE="yourregistry.azurecr.io/batch-json-processor:latest"
```

## Step 5: Deploy Function

```bash
# Initialize function (if starting from scratch)
func init function_app --python

# Deploy
cd function_app
func azure functionapp publish batch-trigger-function
```

## Step 6: Test

```bash
# Upload a test file to trigger the function
az storage blob upload \
  --account-name yourstorageaccount \
  --container-name batch-input \
  --name test_upload.json \
  --file ../samples/sample-input.json \
  --auth-mode login

# Monitor function logs
func azure functionapp logstream batch-trigger-function
```

## Monitoring

### View Function Logs
```bash
# Live logs
az webapp log tail --name batch-trigger-function --resource-group YOUR_RESOURCE_GROUP

# Application Insights query
az monitor app-insights query \
  --app YOUR_APP_INSIGHTS \
  --analytics-query "traces | where message contains 'Blob trigger' | order by timestamp desc | take 50"
```

### View Batch Jobs Created by Function
```bash
# List recent jobs
az batch job list --query "[?contains(id, 'auto-')]" --output table
```

## Advanced: Event Grid Integration

For more control, use Event Grid instead of Blob Trigger:

1. Create Event Grid subscription on Storage Account
2. Filter for blob created events on batch-input container
3. Function triggered by Event Grid (more reliable than blob trigger)
4. Access to additional metadata (blob properties, etc.)

```bash
# Create Event Grid subscription
az eventgrid event-subscription create \
  --name batch-blob-created \
  --source-resource-id $STORAGE_ID \
  --endpoint-type azurefunction \
  --endpoint "/subscriptions/.../resourceGroups/.../providers/Microsoft.Web/sites/batch-trigger-function/functions/batch_trigger" \
  --included-event-types Microsoft.Storage.BlobCreated \
  --subject-begins-with /blobServices/default/containers/batch-input/
```

## Benefits of Azure Function Approach

1. **Automation**: No manual script execution
2. **Scalability**: Handles multiple uploads automatically
3. **Monitoring**: Built-in Application Insights
4. **Reliability**: Automatic retries on failure
5. **Cost-effective**: Pay only for executions (Consumption plan)

## Comparison: Manual vs Automated

| Aspect | Manual Script | Azure Function |
|--------|--------------|----------------|
| Trigger | Manual execution | Automatic (file upload) |
| Monitoring | Manual log checking | Application Insights |
| Scalability | One-by-one | Parallel automatic |
| Cost | Script runtime only | Per execution |
| Complexity | Simple | Moderate |
| Best for | Testing, demos | Production workloads |

## Migration Path

1. **Phase 1 (Current)**: Manual script execution
2. **Phase 2**: Azure Function with blob trigger
3. **Phase 3**: Event Grid + Durable Functions for complex orchestration
4. **Phase 4**: Full event-driven architecture with multiple triggers

## Next Steps

When you're ready to implement:

1. Create Function App
2. Copy submit-batch-job.py logic into function_app.py
3. Configure Managed Identity permissions
4. Deploy and test with sample file
5. Monitor and adjust as needed

## Resources

- [Azure Functions Python Developer Guide](https://docs.microsoft.com/azure/azure-functions/functions-reference-python)
- [Blob Storage Trigger](https://docs.microsoft.com/azure/azure-functions/functions-bindings-storage-blob-trigger)
- [Event Grid Integration](https://docs.microsoft.com/azure/event-grid/overview)
- [Durable Functions](https://docs.microsoft.com/azure/azure-functions/durable/durable-functions-overview)

---

This guide provides the foundation for converting your manual batch processing to a fully automated, event-driven architecture.

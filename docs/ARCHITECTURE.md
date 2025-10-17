# Azure Batch JSON Processor - Architecture Documentation

## Overview

This solution demonstrates a scalable batch processing system using Azure Batch to process JSON files stored in Azure Blob Storage. The system uses Managed Identity for secure authentication and can be triggered manually or automated with Azure Functions.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Data Flow                                 │
└─────────────────────────────────────────────────────────────────┘

[Synthetic Data Generator]
         │
         ├─► Generate JSON files (sales transactions)
         │
         ▼
[Azure Storage Account]
         │
         ├─► Container: batch-input
         │   └─► sales_batch_YYYYMMDD_HHMMSS.json
         │
         ├─► Container: batch-output
         │   └─► processed_sales_YYYYMMDD_HHMMSS.json
         │
         ▼
[Manual Trigger Script / Azure Function (future)]
         │
         ├─► Creates Azure Batch Job
         │   └─► Multiple Tasks (one per JSON file)
         │
         ▼
[Azure Batch Pool]
         │
         ├─► Managed Identity enabled
         ├─► Container Configuration
         │   └─► Pulls from ACR
         │
         ▼
[Docker Container Tasks]
         │
         ├─► Uses Managed Identity to access Storage
         ├─► Downloads JSON from batch-input
         ├─► Processes data (aggregation, validation)
         ├─► Uploads results to batch-output
         │
         ▼
[Results in Storage Account]
```

## Components

### 1. Synthetic Data Generator
**Location**: `scripts/generate-synthetic-data.py`

**Purpose**: Generates realistic sales transaction JSON data for batch processing simulation.

**Data Model**: E-commerce sales transactions
- Transaction ID, timestamp, customer info
- Multiple line items per transaction
- Product details, quantities, prices
- Payment and shipping information

**Output**: JSON files in the format:
```json
{
  "batch_id": "batch_20250117_143022",
  "generated_at": "2025-01-17T14:30:22Z",
  "transaction_count": 1000,
  "transactions": [...]
}
```

### 2. Python Processor Application
**Location**: `src/processor/`

**Purpose**: Containerized application that processes JSON files.

**Processing Operations**:
- **Data Validation**: Check for required fields, data types
- **Aggregation**: Calculate daily/monthly sales totals
- **Customer Analytics**: Top customers, average order value
- **Product Analytics**: Best-selling products, revenue by category
- **Anomaly Detection**: Flag suspicious transactions (high amounts, unusual patterns)
- **Report Generation**: Summary statistics and insights

**Key Files**:
- `main.py`: Entry point, handles Azure Storage operations
- `json_processor.py`: Core processing logic
- `storage_helper.py`: Azure Blob Storage operations with Managed Identity

### 3. Docker Container
**Location**: `src/Dockerfile`

**Base Image**: Python 3.11-slim

**Installed Packages**:
- `azure-storage-blob`: Blob Storage SDK
- `azure-identity`: Managed Identity authentication
- `pandas`: Data processing
- `python-dateutil`: Date handling

### 4. Azure Container Registry (ACR)
**Purpose**: Stores Docker images for Azure Batch

**Scripts**:
- `scripts/login-acr.sh`: Authenticate to ACR
- `scripts/acr-build-push.sh`: Build and push Docker image

### 5. Azure Storage Account

**Containers**:
- `batch-input`: Raw JSON files to be processed
- `batch-output`: Processed results and reports
- `batch-logs`: Application logs (optional)

**Access Method**: Managed Identity (no keys/SAS tokens needed)

### 6. Azure Batch

**Pool Configuration**:
- **Managed Identity**: Enabled for secure storage access
- **Container Configuration**: Uses custom Docker image from ACR
- **Node Size**: Standard_D2s_v3 (or as configured)
- **Auto-scale**: Optional (can scale based on workload)

**Job Structure**:
- One job per batch run
- Multiple tasks per job (one task per JSON file)
- Each task processes one input file

### 7. Trigger Mechanism

**Phase 1 - Manual (Current)**:
- Python script: `scripts/submit-batch-job.py`
- Lists files in storage, creates Batch job with tasks
- Can be run on-demand or via scheduler

**Phase 2 - Automated (Future)**:
- Azure Function with Blob Trigger
- Automatically creates Batch job when new files arrive
- Function code structure provided for future implementation

## Data Flow Details

### Step 1: Data Generation
```bash
python scripts/generate-synthetic-data.py --count 5000 --output ./samples/
```
Generates JSON files with 5000 transactions each.

### Step 2: Upload to Storage
```bash
python scripts/upload-to-storage.py --container batch-input --path ./samples/
```
Uploads JSON files to Azure Storage input container.

### Step 3: Build and Push Docker Image
```bash
./scripts/login-acr.sh
./scripts/acr-build-push.sh
```
Builds Docker image and pushes to ACR.

### Step 4: Submit Batch Job
```bash
python scripts/submit-batch-job.py --pool-id my-batch-pool
```
Creates Batch job with tasks for each input file.

### Step 5: Processing
- Batch tasks start automatically
- Each container:
  1. Authenticates using Managed Identity
  2. Downloads assigned JSON file from blob storage
  3. Processes data (validation, aggregation, analytics)
  4. Generates output JSON with results
  5. Uploads to batch-output container
  6. Logs status and metrics

### Step 6: Retrieve Results
```bash
python scripts/download-results.py --container batch-output --output ./results/
```
Downloads processed files for review.

## Authentication & Security

### Managed Identity Flow

```
[Azure Batch Pool]
    │
    ├─► Has User-Assigned Managed Identity
    │
    ▼
[Container Task Starts]
    │
    ├─► Azure Identity SDK (DefaultAzureCredential)
    ├─► Automatically detects Managed Identity
    │
    ▼
[Access Azure Storage]
    │
    ├─► No connection strings or keys needed
    ├─► RBAC role: "Storage Blob Data Contributor"
    │
    ▼
[Read/Write Blob Data]
```

### Required RBAC Roles

1. **Storage Account**:
   - Managed Identity → "Storage Blob Data Contributor"

2. **Container Registry**:
   - Managed Identity → "AcrPull"

3. **Batch Account**:
   - User/Service Principal → "Batch Contributor"

## Scalability Considerations

### Horizontal Scaling
- Increase Batch pool size
- Process multiple files in parallel
- Each task is independent

### Vertical Scaling
- Use larger VM sizes for compute-intensive operations
- Adjust memory for large JSON files

### Cost Optimization
- Use Low-Priority VMs for non-urgent workloads (80% cost savings)
- Auto-scale pool based on queue depth
- Use spot instances where appropriate

## Monitoring & Observability

### Logs
- Container stdout/stderr captured by Batch
- Custom logs uploaded to blob storage
- Application Insights integration (optional)

### Metrics
- Task completion rate
- Processing time per file
- Error rates and types
- Storage I/O metrics

### Alerts (Future)
- Task failures
- Processing time thresholds
- Storage quota warnings

## Future Enhancements

### Phase 2: Azure Function Integration
- Blob trigger for automatic job submission
- Event Grid integration
- Durable Functions for orchestration

### Phase 3: Advanced Processing
- Machine learning model inference
- Distributed processing with Apache Spark
- Real-time streaming with Event Hubs

### Phase 4: Monitoring Dashboard
- Azure Dashboard with metrics
- Power BI reports
- Custom monitoring portal

## Technology Stack

- **Language**: Python 3.11
- **Container**: Docker
- **Cloud**: Azure
  - Azure Batch
  - Azure Container Registry
  - Azure Blob Storage
  - Azure Managed Identity
- **Libraries**:
  - azure-storage-blob
  - azure-identity
  - azure-batch
  - pandas
  - python-dateutil

## Error Handling

### Container Level
- Retry logic for transient failures
- Graceful handling of malformed JSON
- Timeout management

### Batch Level
- Task retry policies (max 3 attempts)
- Job constraints (max wall-clock time)
- Failed task handling

### Storage Level
- Connection retry policies
- Blob upload/download timeouts
- Conflict resolution

## Performance Benchmarks

Expected performance (approximate):

| File Size | Records | Processing Time | VM Size |
|-----------|---------|-----------------|---------|
| 1 MB      | 1,000   | 10-15 sec      | D2s_v3  |
| 10 MB     | 10,000  | 45-60 sec      | D2s_v3  |
| 100 MB    | 100,000 | 5-8 min        | D4s_v3  |

*Actual performance depends on processing complexity and VM configuration.*

## Conclusion

This architecture provides a scalable, secure, and cost-effective solution for batch processing JSON data in Azure. The use of Managed Identity eliminates credential management overhead, while Azure Batch provides automatic scaling and parallel processing capabilities.

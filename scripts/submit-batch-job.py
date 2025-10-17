#!/usr/bin/env python3
"""
Submit Azure Batch Job

Creates an Azure Batch job with tasks to process JSON files from blob storage.
Each task processes one JSON file using the Docker container.
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

from azure.batch import BatchServiceClient
from azure.batch.models import (
    JobAddParameter,
    PoolInformation,
    TaskAddParameter,
    TaskContainerSettings,
    EnvironmentSetting,
    OnAllTasksComplete
)
from azure.identity import AzureCliCredential, DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
import subprocess
import json


def load_config(config_path: str = "../config/config.json") -> dict:
    """Load configuration from JSON file."""
    config_file = Path(__file__).parent / config_path

    if not config_file.exists():
        print(f"Error: Configuration file not found at {config_file}")
        print("Please create config/config.json from config/config.sample.json")
        sys.exit(1)

    with open(config_file, 'r') as f:
        return json.load(f)


def list_input_blobs(storage_account: str, container_name: str) -> list:
    """
    List all blobs in the input container.

    Args:
        storage_account: Storage account name
        container_name: Container name

    Returns:
        List of blob names
    """
    print(f"Listing blobs in {container_name}...")

    try:
        credential = AzureCliCredential()
        account_url = f"https://{storage_account}.blob.core.windows.net"

        blob_service_client = BlobServiceClient(
            account_url=account_url,
            credential=credential
        )

        container_client = blob_service_client.get_container_client(container_name)
        blob_list = list(container_client.list_blobs())

        blob_names = [blob.name for blob in blob_list if blob.name.endswith('.json')]

        print(f"✓ Found {len(blob_names)} JSON file(s)")
        return blob_names

    except Exception as e:
        print(f"✗ Error listing blobs: {str(e)}")
        sys.exit(1)


def create_batch_job(
    batch_client: BatchServiceClient,
    job_id: str,
    pool_id: str,
    blob_names: list,
    config: dict
):
    """
    Create Azure Batch job with tasks.

    Args:
        batch_client: Batch service client
        job_id: Job ID
        pool_id: Pool ID to run tasks on
        blob_names: List of blob names to process
        config: Configuration dictionary
    """
    print("\n" + "=" * 60)
    print("Creating Azure Batch Job")
    print("=" * 60)
    print(f"Job ID: {job_id}")
    print(f"Pool ID: {pool_id}")
    print(f"Tasks: {len(blob_names)}")
    print()

    # Extract configuration
    storage_account = config["azure"]["storage"]["account_name"]
    input_container = config["azure"]["storage"]["input_container"]
    output_container = config["azure"]["storage"]["output_container"]
    logs_container = config["azure"]["storage"].get("logs_container", "batch-logs")

    acr_image = f"{config['azure']['acr']['login_server']}/{config['azure']['acr']['image_name']}:{config['azure']['acr']['image_tag']}"

    # Create job
    try:
        print("Creating job...")

        job = JobAddParameter(
            id=job_id,
            pool_info=PoolInformation(pool_id=pool_id),
            on_all_tasks_complete=OnAllTasksComplete.terminate_job
        )

        batch_client.job.add(job)
        print(f"✓ Job created: {job_id}")

    except Exception as e:
        if "JobExists" in str(e):
            print(f"Job {job_id} already exists. Using existing job.")
        else:
            print(f"✗ Error creating job: {str(e)}")
            sys.exit(1)

    # Create tasks
    print(f"\nCreating {len(blob_names)} task(s)...")
    print("-" * 60)

    tasks_created = 0
    tasks_failed = 0

    for idx, blob_name in enumerate(blob_names):
        task_id = f"task-{idx}"

        try:
            # Environment variables for the container
            environment_settings = [
                EnvironmentSetting(name="STORAGE_ACCOUNT_NAME", value=storage_account),
                EnvironmentSetting(name="INPUT_CONTAINER", value=input_container),
                EnvironmentSetting(name="OUTPUT_CONTAINER", value=output_container),
                EnvironmentSetting(name="LOGS_CONTAINER", value=logs_container),
                EnvironmentSetting(name="INPUT_BLOB_NAME", value=blob_name),
                EnvironmentSetting(name="JOB_ID", value=job_id),
                EnvironmentSetting(name="TASK_ID", value=task_id),
            ]

            # Container settings
            container_settings = TaskContainerSettings(
                image_name=acr_image,
                container_run_options="--rm"
            )

            # Create task
            task = TaskAddParameter(
                id=task_id,
                command_line="python processor/main.py",  # Explicit command to run the processor
                container_settings=container_settings,
                environment_settings=environment_settings
            )

            batch_client.task.add(job_id=job_id, task=task)

            print(f"✓ Task {task_id}: {blob_name}")
            tasks_created += 1

        except Exception as e:
            if "TaskExists" in str(e):
                print(f"  Task {task_id} already exists, skipping")
            else:
                print(f"✗ Task {task_id} failed: {str(e)}")
                tasks_failed += 1

    # Summary
    print("\n" + "=" * 60)
    print("Job Submission Summary")
    print("=" * 60)
    print(f"  Job ID: {job_id}")
    print(f"  Pool ID: {pool_id}")
    print(f"  Tasks Created: {tasks_created}")
    print(f"  Tasks Failed: {tasks_failed}")
    print(f"  Total Tasks: {len(blob_names)}")
    print()

    if tasks_failed > 0:
        print("Some tasks failed to create. Check errors above.")
        sys.exit(1)

    print("✓ Job submitted successfully")
    print()
    print("Monitor job status:")
    print(f"  az batch job show --job-id {job_id} --account-name {config['azure']['batch']['account_name']} --account-endpoint {config['azure']['batch']['account_url']}")
    print()
    print("List tasks:")
    print(f"  az batch task list --job-id {job_id} --account-name {config['azure']['batch']['account_name']} --account-endpoint {config['azure']['batch']['account_url']}")
    print()
    print("View task output:")
    print(f"  az batch task file download --job-id {job_id} --task-id task-0 --file-path stdout.txt --destination ./logs/stdout.txt --account-name {config['azure']['batch']['account_name']} --account-endpoint {config['azure']['batch']['account_url']}")
    print()
    print("Download results when complete:")
    print(f"  python scripts/download-results.py --output ./results/")
    print()


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Submit Azure Batch job to process JSON files"
    )

    parser.add_argument(
        "--pool-id",
        type=str,
        required=True,
        help="Batch pool ID to use"
    )

    parser.add_argument(
        "--job-id",
        type=str,
        help="Job ID (default: auto-generated with timestamp)"
    )

    parser.add_argument(
        "--config",
        type=str,
        default="../config/config.json",
        help="Path to configuration file"
    )

    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)

    # Generate job ID if not provided
    if args.job_id:
        job_id = args.job_id
    else:
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        job_id = f"json-processing-{timestamp}"

    print("=" * 60)
    print("Azure Batch Job Submission")
    print("=" * 60)
    print()

    # Authenticate with Azure Batch
    print("Authenticating to Azure Batch...")
    try:
        # Get access token from Azure CLI using shell=True for Windows
        result = subprocess.run(
            'az account get-access-token --resource https://batch.core.windows.net/',
            shell=True,
            capture_output=True,
            text=True,
            check=True
        )
        token_data = json.loads(result.stdout)
        access_token = token_data['accessToken']
        
        # Create a simple token credential
        from msrest.authentication import BasicTokenAuthentication
        credentials = BasicTokenAuthentication({'access_token': access_token})
        
        batch_account_url = config["azure"]["batch"]["account_url"]

        batch_client = BatchServiceClient(
            credentials=credentials,
            batch_url=batch_account_url
        )

        # Test connection by listing pools
        pools = list(batch_client.pool.list())
        print(f"✓ Connected to Batch account ({len(pools)} pool(s) available)")

    except Exception as e:
        print(f"✗ Authentication failed: {str(e)}")
        print("\nPlease ensure:")
        print("  1. You are logged in with 'az login'")
        print("  2. Batch account URL is correct in config.json")
        print("  3. You have permissions to the Batch account")
        sys.exit(1)

    # Verify pool exists
    try:
        pool = batch_client.pool.get(args.pool_id)
        print(f"✓ Pool found: {args.pool_id}")
        print(f"  - VM Size: {pool.vm_size}")
        print(f"  - Dedicated Nodes: {pool.target_dedicated_nodes}")
        print(f"  - Low Priority Nodes: {pool.target_low_priority_nodes}")
    except Exception as e:
        print(f"✗ Pool not found: {args.pool_id}")
        print(f"Error: {str(e)}")
        print("\nAvailable pools:")
        for pool in batch_client.pool.list():
            print(f"  - {pool.id}")
        sys.exit(1)

    # List blobs to process
    storage_account = config["azure"]["storage"]["account_name"]
    input_container = config["azure"]["storage"]["input_container"]

    blob_names = list_input_blobs(storage_account, input_container)

    if not blob_names:
        print("\nNo JSON files found in input container")
        print("Please upload files first:")
        print("  python scripts/upload-to-storage.py --path ./samples/")
        sys.exit(0)

    # Create job and tasks
    create_batch_job(
        batch_client=batch_client,
        job_id=job_id,
        pool_id=args.pool_id,
        blob_names=blob_names,
        config=config
    )


if __name__ == "__main__":
    main()

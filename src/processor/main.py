#!/usr/bin/env python3
"""
Azure Batch JSON Processor - Main Entry Point

This script runs inside a Docker container in Azure Batch.
It downloads JSON files from Azure Blob Storage using Managed Identity,
processes them, and uploads results back to storage.
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Import our modules
from storage_helper import StorageHelper
from json_processor import JSONProcessor


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def get_env_var(name: str, required: bool = True, default: str = None) -> str:
    """
    Get environment variable with validation.

    Args:
        name: Environment variable name
        required: Whether the variable is required
        default: Default value if not required

    Returns:
        Environment variable value

    Raises:
        ValueError: If required variable is missing
    """
    value = os.environ.get(name, default)

    if required and not value:
        raise ValueError(f"Required environment variable '{name}' is not set")

    return value


def main():
    """Main execution function."""
    logger.info("=" * 70)
    logger.info("Azure Batch JSON Processor Starting")
    logger.info("=" * 70)

    start_time = datetime.now()

    try:
        # Get configuration from environment variables
        logger.info("Reading configuration from environment variables...")

        storage_account_name = get_env_var("STORAGE_ACCOUNT_NAME")
        input_container = get_env_var("INPUT_CONTAINER", default="batch-input")
        output_container = get_env_var("OUTPUT_CONTAINER", default="batch-output")
        input_blob_name = get_env_var("INPUT_BLOB_NAME")

        # Optional: logs container
        logs_container = get_env_var("LOGS_CONTAINER", required=False, default="batch-logs")

        # Task identification
        task_id = get_env_var("TASK_ID", required=False, default="unknown-task")
        job_id = get_env_var("JOB_ID", required=False, default="unknown-job")

        logger.info(f"Configuration:")
        logger.info(f"  - Storage Account: {storage_account_name}")
        logger.info(f"  - Input Container: {input_container}")
        logger.info(f"  - Output Container: {output_container}")
        logger.info(f"  - Input Blob: {input_blob_name}")
        logger.info(f"  - Job ID: {job_id}")
        logger.info(f"  - Task ID: {task_id}")

        # Initialize Storage Helper with Managed Identity
        logger.info("Initializing Azure Storage client with Managed Identity...")
        storage_helper = StorageHelper(
            storage_account_name=storage_account_name,
            use_managed_identity=True
        )

        # Create working directory
        work_dir = Path("/tmp/batch_work")
        work_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Working directory: {work_dir}")

        # Download input file
        logger.info(f"Downloading input file: {input_blob_name}")
        input_file_path = work_dir / "input.json"

        download_success = storage_helper.download_blob_to_file(
            container_name=input_container,
            blob_name=input_blob_name,
            local_path=str(input_file_path)
        )

        if not download_success:
            raise Exception("Failed to download input file from storage")

        logger.info(f"Successfully downloaded input file to {input_file_path}")

        # Read JSON content
        logger.info("Reading JSON content...")
        with open(input_file_path, 'r', encoding='utf-8') as f:
            json_content = f.read()

        logger.info(f"Read {len(json_content)} characters from input file")

        # Process JSON
        logger.info("Processing JSON data...")
        processor = JSONProcessor()
        result = processor.process(json_content)

        # Add task metadata to result
        result["task_metadata"] = {
            "job_id": job_id,
            "task_id": task_id,
            "input_blob": input_blob_name,
            "input_container": input_container,
            "output_container": output_container
        }

        logger.info("Processing completed successfully")

        # Prepare output file name
        # Extract original filename without extension
        input_name = Path(input_blob_name).stem
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_blob_name = f"processed_{input_name}_{timestamp}.json"

        # Save result locally
        output_file_path = work_dir / "output.json"
        logger.info(f"Saving result to {output_file_path}")

        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        # Upload result to output container
        logger.info(f"Uploading result to blob: {output_blob_name}")
        upload_success = storage_helper.upload_blob_from_file(
            container_name=output_container,
            blob_name=output_blob_name,
            local_path=str(output_file_path),
            overwrite=True
        )

        if not upload_success:
            raise Exception("Failed to upload result to storage")

        logger.info(f"Successfully uploaded result to {output_blob_name}")

        # Calculate total execution time
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()

        # Create execution summary
        summary = {
            "job_id": job_id,
            "task_id": task_id,
            "input_blob": input_blob_name,
            "output_blob": output_blob_name,
            "start_time": start_time.isoformat() + "Z",
            "end_time": end_time.isoformat() + "Z",
            "execution_time_seconds": round(total_time, 2),
            "status": "success",
            "transactions_processed": result.get("validation", {}).get("total_transactions", 0),
            "valid_transactions": result.get("validation", {}).get("valid_transactions", 0),
            "invalid_transactions": result.get("validation", {}).get("invalid_transactions", 0)
        }

        # Upload execution log to logs container (optional)
        if logs_container:
            log_blob_name = f"logs/{job_id}/{task_id}_{timestamp}.json"
            logger.info(f"Uploading execution log to {log_blob_name}")

            storage_helper.upload_blob_from_string(
                container_name=logs_container,
                blob_name=log_blob_name,
                content=json.dumps(summary, indent=2),
                overwrite=True
            )

        logger.info("=" * 70)
        logger.info("Execution Summary:")
        logger.info(f"  - Status: SUCCESS")
        logger.info(f"  - Input: {input_blob_name}")
        logger.info(f"  - Output: {output_blob_name}")
        logger.info(f"  - Transactions: {summary['transactions_processed']}")
        logger.info(f"  - Valid: {summary['valid_transactions']}")
        logger.info(f"  - Invalid: {summary['invalid_transactions']}")
        logger.info(f"  - Execution Time: {total_time:.2f} seconds")
        logger.info("=" * 70)

        return 0

    except Exception as e:
        logger.error("=" * 70)
        logger.error(f"FATAL ERROR: {str(e)}")
        logger.error("=" * 70)
        logger.exception("Full traceback:")

        # Try to upload error log
        try:
            error_summary = {
                "job_id": get_env_var("JOB_ID", required=False, default="unknown"),
                "task_id": get_env_var("TASK_ID", required=False, default="unknown"),
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat() + "Z"
            }

            storage_account_name = get_env_var("STORAGE_ACCOUNT_NAME", required=False)
            logs_container = get_env_var("LOGS_CONTAINER", required=False, default="batch-logs")

            if storage_account_name:
                storage_helper = StorageHelper(storage_account_name, use_managed_identity=True)
                log_blob_name = f"logs/errors/{error_summary['job_id']}/{error_summary['task_id']}_error.json"

                storage_helper.upload_blob_from_string(
                    container_name=logs_container,
                    blob_name=log_blob_name,
                    content=json.dumps(error_summary, indent=2),
                    overwrite=True
                )
                logger.info(f"Uploaded error log to {log_blob_name}")

        except Exception as upload_error:
            logger.error(f"Failed to upload error log: {str(upload_error)}")

        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

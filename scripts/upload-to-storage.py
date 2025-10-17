#!/usr/bin/env python3
"""
Upload files to Azure Blob Storage

Uploads JSON files from local directory to Azure Storage container
using Azure CLI authentication.
"""

import argparse
import json
import sys
from pathlib import Path
from azure.storage.blob import BlobServiceClient
from azure.identity import AzureCliCredential


def load_config(config_path: str = "../config/config.json") -> dict:
    """Load configuration from JSON file."""
    config_file = Path(__file__).parent / config_path

    if not config_file.exists():
        print(f"Error: Configuration file not found at {config_file}")
        print("Please create config/config.json from config/config.sample.json")
        sys.exit(1)

    with open(config_file, 'r') as f:
        return json.load(f)


def upload_files(storage_account: str, container_name: str, local_path: str, pattern: str = "*.json"):
    """
    Upload files to Azure Blob Storage.

    Args:
        storage_account: Storage account name
        container_name: Container name
        local_path: Local directory or file path
        pattern: File pattern to match (default: *.json)
    """
    print("=" * 60)
    print("Azure Blob Storage Upload")
    print("=" * 60)
    print(f"Storage Account: {storage_account}")
    print(f"Container: {container_name}")
    print(f"Local Path: {local_path}")
    print(f"Pattern: {pattern}")
    print()

    # Initialize Azure CLI credential
    print("Authenticating with Azure CLI...")
    try:
        credential = AzureCliCredential()
        account_url = f"https://{storage_account}.blob.core.windows.net"

        blob_service_client = BlobServiceClient(
            account_url=account_url,
            credential=credential
        )
        print("✓ Authentication successful")
    except Exception as e:
        print(f"✗ Authentication failed: {str(e)}")
        print("\nPlease ensure you are logged in with 'az login'")
        sys.exit(1)

    # Get container client
    try:
        container_client = blob_service_client.get_container_client(container_name)

        # Check if container exists
        if not container_client.exists():
            print(f"\nWarning: Container '{container_name}' does not exist")
            response = input("Create container? (y/n): ")
            if response.lower() == 'y':
                container_client.create_container()
                print(f"✓ Created container: {container_name}")
            else:
                print("Upload cancelled")
                sys.exit(0)

    except Exception as e:
        print(f"✗ Error accessing container: {str(e)}")
        sys.exit(1)

    # Get files to upload
    local_path_obj = Path(local_path)

    if local_path_obj.is_file():
        # Single file
        files_to_upload = [local_path_obj]
    elif local_path_obj.is_dir():
        # Directory - find matching files
        files_to_upload = list(local_path_obj.glob(pattern))
    else:
        print(f"Error: Path does not exist: {local_path}")
        sys.exit(1)

    if not files_to_upload:
        print(f"No files found matching pattern: {pattern}")
        sys.exit(0)

    print(f"\nFound {len(files_to_upload)} file(s) to upload")
    print("-" * 60)

    # Upload files
    uploaded_count = 0
    failed_count = 0

    for file_path in files_to_upload:
        try:
            blob_name = file_path.name
            file_size = file_path.stat().st_size
            file_size_mb = file_size / (1024 * 1024)

            print(f"\nUploading: {blob_name} ({file_size_mb:.2f} MB)")

            blob_client = container_client.get_blob_client(blob_name)

            with open(file_path, "rb") as data:
                blob_client.upload_blob(data, overwrite=True)

            print(f"  ✓ Uploaded successfully")
            uploaded_count += 1

        except Exception as e:
            print(f"  ✗ Upload failed: {str(e)}")
            failed_count += 1
            continue

    # Summary
    print("\n" + "=" * 60)
    print("Upload Summary")
    print("=" * 60)
    print(f"  Uploaded: {uploaded_count}")
    print(f"  Failed: {failed_count}")
    print(f"  Total: {len(files_to_upload)}")
    print()

    if failed_count > 0:
        print("Some uploads failed. Check errors above.")
        sys.exit(1)
    else:
        print("✓ All files uploaded successfully")
        print()
        print("Next steps:")
        print("  1. Build and push Docker image: ./scripts/acr-build-push.sh")
        print("  2. Submit batch job: python scripts/submit-batch-job.py")
        print()


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Upload files to Azure Blob Storage"
    )

    parser.add_argument(
        "--container",
        type=str,
        help="Container name (overrides config)"
    )

    parser.add_argument(
        "--path",
        type=str,
        required=True,
        help="Local file or directory path to upload"
    )

    parser.add_argument(
        "--pattern",
        type=str,
        default="*.json",
        help="File pattern to match (default: *.json)"
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

    # Get storage account name
    storage_account = config["azure"]["storage"]["account_name"]

    # Get container name (from args or config)
    if args.container:
        container_name = args.container
    else:
        container_name = config["azure"]["storage"]["input_container"]

    # Upload files
    upload_files(
        storage_account=storage_account,
        container_name=container_name,
        local_path=args.path,
        pattern=args.pattern
    )


if __name__ == "__main__":
    main()

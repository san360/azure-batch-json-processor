#!/usr/bin/env python3
"""
Download results from Azure Blob Storage

Downloads processed files from Azure Storage output container.
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
        sys.exit(1)

    with open(config_file, 'r') as f:
        return json.load(f)


def download_results(storage_account: str, container_name: str, output_path: str, prefix: str = ""):
    """
    Download blobs from Azure Storage.

    Args:
        storage_account: Storage account name
        container_name: Container name
        output_path: Local directory to save files
        prefix: Blob name prefix filter
    """
    print("=" * 60)
    print("Azure Blob Storage Download")
    print("=" * 60)
    print(f"Storage Account: {storage_account}")
    print(f"Container: {container_name}")
    print(f"Output Path: {output_path}")
    if prefix:
        print(f"Prefix Filter: {prefix}")
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

        if not container_client.exists():
            print(f"\nError: Container '{container_name}' does not exist")
            sys.exit(1)

    except Exception as e:
        print(f"✗ Error accessing container: {str(e)}")
        sys.exit(1)

    # List blobs
    print("\nListing blobs...")
    try:
        blob_list = list(container_client.list_blobs(name_starts_with=prefix))

        if not blob_list:
            print("No blobs found in container")
            return

        print(f"Found {len(blob_list)} blob(s)")
        print("-" * 60)

    except Exception as e:
        print(f"✗ Error listing blobs: {str(e)}")
        sys.exit(1)

    # Create output directory
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Download blobs
    downloaded_count = 0
    failed_count = 0

    for blob in blob_list:
        try:
            blob_name = blob.name
            file_size_mb = blob.size / (1024 * 1024)

            print(f"\nDownloading: {blob_name} ({file_size_mb:.2f} MB)")

            # Create subdirectories if blob name contains path
            local_file_path = output_dir / blob_name
            local_file_path.parent.mkdir(parents=True, exist_ok=True)

            blob_client = container_client.get_blob_client(blob_name)

            with open(local_file_path, "wb") as file:
                download_stream = blob_client.download_blob()
                file.write(download_stream.readall())

            print(f"  ✓ Downloaded to: {local_file_path}")
            downloaded_count += 1

        except Exception as e:
            print(f"  ✗ Download failed: {str(e)}")
            failed_count += 1
            continue

    # Summary
    print("\n" + "=" * 60)
    print("Download Summary")
    print("=" * 60)
    print(f"  Downloaded: {downloaded_count}")
    print(f"  Failed: {failed_count}")
    print(f"  Total: {len(blob_list)}")
    print()

    if failed_count > 0:
        print("Some downloads failed. Check errors above.")
        sys.exit(1)
    else:
        print("✓ All files downloaded successfully")
        print(f"\nResults saved to: {output_dir.absolute()}")
        print()


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Download results from Azure Blob Storage"
    )

    parser.add_argument(
        "--container",
        type=str,
        help="Container name (overrides config)"
    )

    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Local directory to save downloaded files"
    )

    parser.add_argument(
        "--prefix",
        type=str,
        default="",
        help="Filter blobs by prefix (optional)"
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
        container_name = config["azure"]["storage"]["output_container"]

    # Download files
    download_results(
        storage_account=storage_account,
        container_name=container_name,
        output_path=args.output,
        prefix=args.prefix
    )


if __name__ == "__main__":
    main()

"""
Azure Storage Helper with Managed Identity Authentication

Handles all blob storage operations using Azure Managed Identity.
"""

import os
import logging
from typing import Optional
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.core.exceptions import HttpResponseError


logger = logging.getLogger(__name__)


class StorageHelper:
    """Helper class for Azure Blob Storage operations with Managed Identity."""

    def __init__(
        self,
        storage_account_name: str,
        use_managed_identity: bool = True,
        managed_identity_client_id: Optional[str] = None,
    ):
        """
        Initialize Storage Helper.

        Args:
            storage_account_name: Name of the Azure Storage account
            use_managed_identity: If True, use Managed Identity. If False, use DefaultAzureCredential
            managed_identity_client_id: Optional client ID for a user-assigned managed identity
        """
        self.storage_account_name = storage_account_name
        self.account_url = f"https://{storage_account_name}.blob.core.windows.net"

        # Set up authentication - prefer explicit user-assigned MI when provided
        if use_managed_identity:
            if managed_identity_client_id:
                self.credential = ManagedIdentityCredential(client_id=managed_identity_client_id)
                logger.info(
                    "Using User-Assigned Managed Identity (client_id=%s) for authentication",
                    managed_identity_client_id,
                )
            else:
                self.credential = ManagedIdentityCredential()
                logger.info("Using System-Assigned (or default) Managed Identity for authentication")
        else:
            # Use DefaultAzureCredential (tries multiple methods)
            self.credential = DefaultAzureCredential()
            logger.info("Using DefaultAzureCredential for authentication")

        # Initialize BlobServiceClient
        self.blob_service_client = BlobServiceClient(
            account_url=self.account_url,
            credential=self.credential
        )

        logger.info(f"Initialized StorageHelper for account: {storage_account_name}")

    def download_blob_to_file(self, container_name: str, blob_name: str, local_path: str) -> bool:
        """
        Download a blob to a local file.

        Args:
            container_name: Name of the container
            blob_name: Name of the blob
            local_path: Local file path to save to

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Downloading blob: {blob_name} from container: {container_name}")

            # Get blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )

            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(local_path) or '.', exist_ok=True)

            # Download blob
            with open(local_path, "wb") as file:
                download_stream = blob_client.download_blob()
                file.write(download_stream.readall())

            file_size = os.path.getsize(local_path)
            logger.info(f"Successfully downloaded {blob_name} ({file_size} bytes) to {local_path}")
            return True

        except HttpResponseError as e:
            if getattr(e, 'error_code', '') == 'AuthorizationFailure':
                logger.error(
                    "Authorization failure downloading blob %s from container %s. Ensure managed identity has 'Storage Blob Data Reader' or 'Storage Blob Data Contributor' on storage account %s.",
                    blob_name,
                    container_name,
                    self.storage_account_name,
                )
            logger.error(f"HTTP error downloading blob {blob_name}: {e.message}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error downloading blob {blob_name}: {str(e)}", exc_info=True)
            return False

    def download_blob_to_string(self, container_name: str, blob_name: str) -> Optional[str]:
        """
        Download a blob as a string.

        Args:
            container_name: Name of the container
            blob_name: Name of the blob

        Returns:
            Blob content as string, or None if error
        """
        try:
            logger.info(f"Downloading blob to string: {blob_name}")

            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )

            download_stream = blob_client.download_blob()
            content = download_stream.readall().decode('utf-8')

            logger.info(f"Successfully downloaded {blob_name} ({len(content)} characters)")
            return content

        except HttpResponseError as e:
            if getattr(e, 'error_code', '') == 'AuthorizationFailure':
                logger.error(
                    "Authorization failure downloading blob %s from container %s. Assign appropriate RBAC role ('Storage Blob Data Reader/Contributor') to managed identity on %s.",
                    blob_name,
                    container_name,
                    self.storage_account_name,
                )
            logger.error(f"HTTP error downloading blob {blob_name}: {e.message}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading blob {blob_name}: {str(e)}", exc_info=True)
            return None

    def test_blob_access(self, container_name: str) -> bool:
        """Perform a lightweight access test against a container to validate RBAC.

        Tries to get container properties. If AuthorizationFailure occurs, logs remediation guidance.

        Returns:
            True if access appears authorized, False otherwise.
        """
        try:
            container_client = self.blob_service_client.get_container_client(container_name)
            container_client.get_container_properties()
            logger.info(
                "Access test succeeded for container '%s' using storage account '%s' (managed identity).",
                container_name,
                self.storage_account_name,
            )
            return True
        except HttpResponseError as e:
            if getattr(e, 'error_code', '') == 'AuthorizationFailure':
                logger.error(
                    "Authorization failure accessing container %s. Assign role 'Storage Blob Data Reader/Contributor' at scope: /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/%s",
                    container_name,
                    self.storage_account_name,
                )
            else:
                logger.error(f"HTTP error during access test for container {container_name}: {e.message}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during access test for container {container_name}: {str(e)}", exc_info=True)
            return False

    def upload_blob_from_file(self, container_name: str, blob_name: str, local_path: str, overwrite: bool = True) -> bool:
        """
        Upload a local file to blob storage.

        Args:
            container_name: Name of the container
            blob_name: Name of the blob
            local_path: Local file path to upload
            overwrite: Whether to overwrite if blob exists

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Uploading file {local_path} to blob: {blob_name}")

            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )

            with open(local_path, "rb") as data:
                blob_client.upload_blob(data, overwrite=overwrite)

            file_size = os.path.getsize(local_path)
            logger.info(f"Successfully uploaded {local_path} ({file_size} bytes) to {blob_name}")
            return True

        except HttpResponseError as e:
            if getattr(e, 'error_code', '') == 'AuthorizationFailure':
                logger.error(
                    "Authorization failure uploading blob %s. Ensure the managed identity has the 'Storage Blob Data Contributor' role on the storage account %s.",
                    blob_name,
                    self.storage_account_name,
                )
            logger.error(f"HTTP error uploading blob {blob_name}: {e.message}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error uploading blob {blob_name}: {str(e)}", exc_info=True)
            return False

    def upload_blob_from_string(self, container_name: str, blob_name: str, content: str, overwrite: bool = True) -> bool:
        """
        Upload a string to blob storage.

        Args:
            container_name: Name of the container
            blob_name: Name of the blob
            content: String content to upload
            overwrite: Whether to overwrite if blob exists

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Uploading string content to blob: {blob_name}")

            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )

            blob_client.upload_blob(content, overwrite=overwrite)

            logger.info(f"Successfully uploaded content ({len(content)} characters) to {blob_name}")
            return True

        except HttpResponseError as e:
            if getattr(e, 'error_code', '') == 'AuthorizationFailure':
                logger.error(
                    "Authorization failure uploading blob %s. Assign role 'Storage Blob Data Contributor' to the managed identity on storage account %s.",
                    blob_name,
                    self.storage_account_name,
                )
            logger.error(f"HTTP error uploading blob {blob_name}: {e.message}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error uploading blob {blob_name}: {str(e)}", exc_info=True)
            return False

    def list_blobs(self, container_name: str, name_starts_with: Optional[str] = None) -> list:
        """
        List blobs in a container.

        Args:
            container_name: Name of the container
            name_starts_with: Filter blobs by prefix (optional)

        Returns:
            List of blob names
        """
        try:
            logger.info(f"Listing blobs in container: {container_name}")

            container_client = self.blob_service_client.get_container_client(container_name)
            blob_list = container_client.list_blobs(name_starts_with=name_starts_with)

            blob_names = [blob.name for blob in blob_list]
            logger.info(f"Found {len(blob_names)} blob(s) in {container_name}")

            return blob_names

        except Exception as e:
            logger.error(f"Error listing blobs in {container_name}: {str(e)}", exc_info=True)
            return []

    def blob_exists(self, container_name: str, blob_name: str) -> bool:
        """
        Check if a blob exists.

        Args:
            container_name: Name of the container
            blob_name: Name of the blob

        Returns:
            True if blob exists, False otherwise
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )

            return blob_client.exists()

        except Exception as e:
            logger.error(f"Error checking if blob {blob_name} exists: {str(e)}", exc_info=True)
            return False

    def delete_blob(self, container_name: str, blob_name: str) -> bool:
        """
        Delete a blob.

        Args:
            container_name: Name of the container
            blob_name: Name of the blob

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Deleting blob: {blob_name}")

            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )

            blob_client.delete_blob()
            logger.info(f"Successfully deleted blob: {blob_name}")
            return True

        except Exception as e:
            logger.error(f"Error deleting blob {blob_name}: {str(e)}", exc_info=True)
            return False

    def get_blob_properties(self, container_name: str, blob_name: str) -> Optional[dict]:
        """
        Get blob properties (metadata, size, etc.).

        Args:
            container_name: Name of the container
            blob_name: Name of the blob

        Returns:
            Dictionary of properties, or None if error
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )

            properties = blob_client.get_blob_properties()

            return {
                "name": blob_name,
                "size": properties.size,
                "last_modified": properties.last_modified,
                "content_type": properties.content_settings.content_type,
                "metadata": properties.metadata
            }

        except Exception as e:
            logger.error(f"Error getting properties for blob {blob_name}: {str(e)}", exc_info=True)
            return None

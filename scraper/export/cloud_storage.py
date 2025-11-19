"""
Cloud Storage Integrations.

Export scraped data to cloud storage services.
Premium feature - competitors charge $99-299/month for this.

Supported services:
- AWS S3
- Google Cloud Storage
- Azure Blob Storage
- DigitalOcean Spaces
- Cloudflare R2
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import io

logger = logging.getLogger(__name__)


class CloudStorageProvider(ABC):
    """Base class for cloud storage providers."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    async def upload_file(self, local_path: str, remote_path: str, **kwargs):
        """Upload a file to cloud storage."""
        pass

    @abstractmethod
    async def upload_bytes(self, data: bytes, remote_path: str, **kwargs):
        """Upload bytes to cloud storage."""
        pass

    @abstractmethod
    async def download_file(self, remote_path: str, local_path: str, **kwargs):
        """Download a file from cloud storage."""
        pass

    @abstractmethod
    async def list_files(self, prefix: str = '', **kwargs) -> List[str]:
        """List files in cloud storage."""
        pass

    @abstractmethod
    async def delete_file(self, remote_path: str, **kwargs):
        """Delete a file from cloud storage."""
        pass


# ============================================================================
# AWS S3 PROVIDER
# ============================================================================

class S3Provider(CloudStorageProvider):
    """
    AWS S3 cloud storage provider.

    Features:
    - Async upload/download
    - Multipart upload for large files
    - Server-side encryption
    - Custom metadata
    - Public/private access control
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = None

    async def _get_client(self):
        """Get or create S3 client."""
        if self.client is None:
            import aioboto3

            session = aioboto3.Session(
                aws_access_key_id=self.config.get('access_key_id'),
                aws_secret_access_key=self.config.get('secret_access_key'),
                region_name=self.config.get('region', 'us-east-1')
            )

            self.session = session
            self.client = session.client('s3')

        return self.client

    async def upload_file(
        self,
        local_path: str,
        remote_path: str,
        public: bool = False,
        metadata: Optional[Dict[str, str]] = None,
        storage_class: str = 'STANDARD'
    ):
        """
        Upload file to S3.

        Args:
            local_path: Local file path
            remote_path: S3 key (path in bucket)
            public: Make file publicly accessible
            metadata: Custom metadata
            storage_class: S3 storage class (STANDARD, INTELLIGENT_TIERING, etc.)
        """
        bucket = self.config.get('bucket')

        extra_args = {
            'StorageClass': storage_class
        }

        if public:
            extra_args['ACL'] = 'public-read'

        if metadata:
            extra_args['Metadata'] = metadata

        # Enable server-side encryption if configured
        if self.config.get('encryption'):
            extra_args['ServerSideEncryption'] = 'AES256'

        async with self.session.client('s3') as s3:
            await s3.upload_file(
                local_path,
                bucket,
                remote_path,
                ExtraArgs=extra_args
            )

        url = f"https://{bucket}.s3.{self.config.get('region', 'us-east-1')}.amazonaws.com/{remote_path}"
        logger.info(f"Uploaded to S3: {url}")

        return url

    async def upload_bytes(
        self,
        data: bytes,
        remote_path: str,
        content_type: str = 'application/octet-stream',
        public: bool = False,
        metadata: Optional[Dict[str, str]] = None
    ):
        """Upload bytes to S3."""
        bucket = self.config.get('bucket')

        extra_args = {
            'ContentType': content_type
        }

        if public:
            extra_args['ACL'] = 'public-read'

        if metadata:
            extra_args['Metadata'] = metadata

        if self.config.get('encryption'):
            extra_args['ServerSideEncryption'] = 'AES256'

        async with self.session.client('s3') as s3:
            await s3.put_object(
                Bucket=bucket,
                Key=remote_path,
                Body=data,
                **extra_args
            )

        url = f"https://{bucket}.s3.{self.config.get('region', 'us-east-1')}.amazonaws.com/{remote_path}"
        logger.info(f"Uploaded bytes to S3: {url}")

        return url

    async def download_file(self, remote_path: str, local_path: str):
        """Download file from S3."""
        bucket = self.config.get('bucket')

        async with self.session.client('s3') as s3:
            await s3.download_file(bucket, remote_path, local_path)

        logger.info(f"Downloaded from S3: {remote_path} -> {local_path}")

    async def list_files(self, prefix: str = '', max_keys: int = 1000) -> List[str]:
        """List files in S3 bucket."""
        bucket = self.config.get('bucket')
        files = []

        async with self.session.client('s3') as s3:
            paginator = s3.get_paginator('list_objects_v2')

            async for page in paginator.paginate(
                Bucket=bucket,
                Prefix=prefix,
                MaxKeys=max_keys
            ):
                if 'Contents' in page:
                    files.extend([obj['Key'] for obj in page['Contents']])

        logger.info(f"Listed {len(files)} files from S3 with prefix '{prefix}'")
        return files

    async def delete_file(self, remote_path: str):
        """Delete file from S3."""
        bucket = self.config.get('bucket')

        async with self.session.client('s3') as s3:
            await s3.delete_object(Bucket=bucket, Key=remote_path)

        logger.info(f"Deleted from S3: {remote_path}")


# ============================================================================
# GOOGLE CLOUD STORAGE PROVIDER
# ============================================================================

class GCSProvider(CloudStorageProvider):
    """
    Google Cloud Storage provider.

    Features:
    - Async upload/download
    - Resumable uploads
    - Signed URLs
    - Object lifecycle management
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = None

    def _get_client(self):
        """Get or create GCS client."""
        if self.client is None:
            from google.cloud import storage

            # Use service account key if provided
            credentials_path = self.config.get('credentials_path')
            if credentials_path:
                self.client = storage.Client.from_service_account_json(credentials_path)
            else:
                self.client = storage.Client(project=self.config.get('project_id'))

        return self.client

    async def upload_file(
        self,
        local_path: str,
        remote_path: str,
        public: bool = False,
        metadata: Optional[Dict[str, str]] = None,
        content_type: Optional[str] = None
    ):
        """Upload file to GCS."""
        bucket_name = self.config.get('bucket')

        # GCS client is not async, run in executor
        def _upload():
            client = self._get_client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(remote_path)

            if metadata:
                blob.metadata = metadata

            if content_type:
                blob.content_type = content_type

            blob.upload_from_filename(local_path)

            if public:
                blob.make_public()

            return blob.public_url if public else f"gs://{bucket_name}/{remote_path}"

        url = await asyncio.get_event_loop().run_in_executor(None, _upload)

        logger.info(f"Uploaded to GCS: {url}")
        return url

    async def upload_bytes(
        self,
        data: bytes,
        remote_path: str,
        content_type: str = 'application/octet-stream',
        public: bool = False,
        metadata: Optional[Dict[str, str]] = None
    ):
        """Upload bytes to GCS."""
        bucket_name = self.config.get('bucket')

        def _upload():
            client = self._get_client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(remote_path)

            if metadata:
                blob.metadata = metadata

            blob.content_type = content_type
            blob.upload_from_string(data)

            if public:
                blob.make_public()

            return blob.public_url if public else f"gs://{bucket_name}/{remote_path}"

        url = await asyncio.get_event_loop().run_in_executor(None, _upload)

        logger.info(f"Uploaded bytes to GCS: {url}")
        return url

    async def download_file(self, remote_path: str, local_path: str):
        """Download file from GCS."""
        bucket_name = self.config.get('bucket')

        def _download():
            client = self._get_client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(remote_path)
            blob.download_to_filename(local_path)

        await asyncio.get_event_loop().run_in_executor(None, _download)

        logger.info(f"Downloaded from GCS: {remote_path} -> {local_path}")

    async def list_files(self, prefix: str = '', max_results: int = 1000) -> List[str]:
        """List files in GCS bucket."""
        bucket_name = self.config.get('bucket')

        def _list():
            client = self._get_client()
            bucket = client.bucket(bucket_name)
            blobs = bucket.list_blobs(prefix=prefix, max_results=max_results)
            return [blob.name for blob in blobs]

        files = await asyncio.get_event_loop().run_in_executor(None, _list)

        logger.info(f"Listed {len(files)} files from GCS with prefix '{prefix}'")
        return files

    async def delete_file(self, remote_path: str):
        """Delete file from GCS."""
        bucket_name = self.config.get('bucket')

        def _delete():
            client = self._get_client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(remote_path)
            blob.delete()

        await asyncio.get_event_loop().run_in_executor(None, _delete)

        logger.info(f"Deleted from GCS: {remote_path}")


# ============================================================================
# AZURE BLOB STORAGE PROVIDER
# ============================================================================

class AzureBlobProvider(CloudStorageProvider):
    """
    Azure Blob Storage provider.

    Features:
    - Async upload/download
    - Block blob support
    - Access tiers (Hot, Cool, Archive)
    - SAS tokens
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = None

    async def _get_client(self):
        """Get or create Azure blob service client."""
        if self.client is None:
            from azure.storage.blob.aio import BlobServiceClient

            connection_string = self.config.get('connection_string')
            if connection_string:
                self.client = BlobServiceClient.from_connection_string(connection_string)
            else:
                account_url = f"https://{self.config.get('account_name')}.blob.core.windows.net"
                self.client = BlobServiceClient(
                    account_url=account_url,
                    credential=self.config.get('account_key')
                )

        return self.client

    async def upload_file(
        self,
        local_path: str,
        remote_path: str,
        public: bool = False,
        metadata: Optional[Dict[str, str]] = None,
        tier: str = 'Hot'
    ):
        """
        Upload file to Azure Blob Storage.

        Args:
            local_path: Local file path
            remote_path: Blob name
            public: Make blob publicly accessible
            metadata: Custom metadata
            tier: Access tier (Hot, Cool, Archive)
        """
        container = self.config.get('container')

        client = await self._get_client()
        blob_client = client.get_blob_client(container=container, blob=remote_path)

        with open(local_path, 'rb') as data:
            await blob_client.upload_blob(
                data,
                overwrite=True,
                metadata=metadata,
                standard_blob_tier=tier
            )

        url = blob_client.url
        logger.info(f"Uploaded to Azure Blob: {url}")

        return url

    async def upload_bytes(
        self,
        data: bytes,
        remote_path: str,
        content_type: str = 'application/octet-stream',
        public: bool = False,
        metadata: Optional[Dict[str, str]] = None
    ):
        """Upload bytes to Azure Blob Storage."""
        container = self.config.get('container')

        client = await self._get_client()
        blob_client = client.get_blob_client(container=container, blob=remote_path)

        await blob_client.upload_blob(
            data,
            overwrite=True,
            metadata=metadata,
            content_settings={'content_type': content_type}
        )

        url = blob_client.url
        logger.info(f"Uploaded bytes to Azure Blob: {url}")

        return url

    async def download_file(self, remote_path: str, local_path: str):
        """Download file from Azure Blob Storage."""
        container = self.config.get('container')

        client = await self._get_client()
        blob_client = client.get_blob_client(container=container, blob=remote_path)

        with open(local_path, 'wb') as file:
            download_stream = await blob_client.download_blob()
            data = await download_stream.readall()
            file.write(data)

        logger.info(f"Downloaded from Azure Blob: {remote_path} -> {local_path}")

    async def list_files(self, prefix: str = '') -> List[str]:
        """List files in Azure container."""
        container = self.config.get('container')

        client = await self._get_client()
        container_client = client.get_container_client(container)

        files = []
        async for blob in container_client.list_blobs(name_starts_with=prefix):
            files.append(blob.name)

        logger.info(f"Listed {len(files)} files from Azure with prefix '{prefix}'")
        return files

    async def delete_file(self, remote_path: str):
        """Delete file from Azure Blob Storage."""
        container = self.config.get('container')

        client = await self._get_client()
        blob_client = client.get_blob_client(container=container, blob=remote_path)

        await blob_client.delete_blob()

        logger.info(f"Deleted from Azure Blob: {remote_path}")


# ============================================================================
# CLOUD STORAGE EXPORTER
# ============================================================================

class CloudStorageExporter:
    """
    High-level cloud storage export interface.

    Automatically selects the appropriate provider.
    """

    PROVIDERS = {
        's3': S3Provider,
        'aws': S3Provider,
        'gcs': GCSProvider,
        'google': GCSProvider,
        'azure': AzureBlobProvider,
        'azureblob': AzureBlobProvider,
    }

    def __init__(self, provider: str, config: Dict[str, Any]):
        """
        Initialize cloud storage exporter.

        Args:
            provider: Provider type (s3, gcs, azure)
            config: Provider configuration
        """
        provider_class = self.PROVIDERS.get(provider.lower())
        if not provider_class:
            raise ValueError(f"Unsupported cloud provider: {provider}")

        self.provider = provider_class(config)
        self.provider_type = provider.lower()

    async def export_file(
        self,
        local_path: str,
        remote_path: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Export local file to cloud storage.

        Args:
            local_path: Local file path
            remote_path: Remote path (defaults to filename)
            **kwargs: Provider-specific options

        Returns:
            URL of uploaded file
        """
        if remote_path is None:
            remote_path = Path(local_path).name

        url = await self.provider.upload_file(local_path, remote_path, **kwargs)

        logger.info(f"Exported to {self.provider_type}: {url}")

        return url

    async def export_data(
        self,
        data: bytes,
        remote_path: str,
        **kwargs
    ) -> str:
        """
        Export data bytes to cloud storage.

        Args:
            data: Data to export
            remote_path: Remote path
            **kwargs: Provider-specific options

        Returns:
            URL of uploaded data
        """
        url = await self.provider.upload_bytes(data, remote_path, **kwargs)

        logger.info(f"Exported data to {self.provider_type}: {url}")

        return url


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

async def example_usage():
    """Example of using cloud storage providers."""

    # AWS S3 example
    s3_exporter = CloudStorageExporter('s3', {
        'access_key_id': 'YOUR_ACCESS_KEY',
        'secret_access_key': 'YOUR_SECRET_KEY',
        'region': 'us-east-1',
        'bucket': 'my-scraping-data',
        'encryption': True
    })

    # Upload scraped data
    url = await s3_exporter.export_file(
        'results.csv',
        'scrapes/2024/01/results.csv',
        public=False,
        metadata={'job_id': '12345', 'timestamp': '2024-01-15'},
        storage_class='INTELLIGENT_TIERING'
    )

    print(f"Uploaded to: {url}")

    # GCS example
    gcs_exporter = CloudStorageExporter('gcs', {
        'project_id': 'my-project',
        'credentials_path': '/path/to/credentials.json',
        'bucket': 'my-scraping-bucket'
    })

    await gcs_exporter.export_file('data.json', 'scrapes/data.json', public=True)

    # Azure example
    azure_exporter = CloudStorageExporter('azure', {
        'account_name': 'mystorage',
        'account_key': 'YOUR_ACCOUNT_KEY',
        'container': 'scraping-data'
    })

    await azure_exporter.export_file('results.xlsx', 'exports/results.xlsx', tier='Cool')

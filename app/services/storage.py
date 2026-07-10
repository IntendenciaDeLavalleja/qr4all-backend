import io
import logging
import socket
import uuid
from datetime import timedelta

from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)


class StorageError(Exception):
    pass


class StorageService:
    def __init__(self, app=None):
        self.client = None
        self.bucket_name = None
        self.public_base_url = None
        if app:
            self.init_app(app)

    def init_app(self, app):
        endpoint = app.config.get('MINIO_ENDPOINT')
        access_key = app.config.get('MINIO_ACCESS_KEY')
        secret_key = app.config.get('MINIO_SECRET_KEY')
        secure = app.config.get('MINIO_SECURE', True)
        self.bucket_name = app.config.get('MINIO_BUCKET_NAME')
        self.public_base_url = app.config.get('MINIO_PUBLIC_URL')
        is_local = app.config.get('DEPLOYMENT_MODE') == 'local'

        if not all([endpoint, access_key, secret_key, self.bucket_name]):
            if is_local:
                logger.info(
                    "MinIO not configured. Image storage unavailable in local mode. "
                    "Link creation still works without images."
                )
            else:
                logger.warning(
                    "MinIO configuration incomplete (endpoint=%s, bucket=%s). "
                    "Storage will be unavailable.",
                    bool(endpoint), bool(self.bucket_name),
                )
            return

        # In local mode, set a short global socket timeout before the MinIO
        # probe so DNS lookups for unresolvable Docker hostnames like 'minio'
        # don't block for 20+ seconds.  We restore the original timeout
        # afterwards so it doesn't affect other network calls.
        old_timeout = socket.getdefaulttimeout()
        if is_local:
            socket.setdefaulttimeout(3)

        try:
            client = Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure,
            )
            self._ensure_bucket_exists_with(client)
            self.client = client
            logger.info(
                "MinIO storage ready: bucket=%s endpoint=%s",
                self.bucket_name, endpoint,
            )
        except Exception as exc:
            self.client = None
            if is_local:
                logger.warning(
                    "MinIO unavailable at %s (local mode). "
                    "Image features disabled. Link creation still works. "
                    "To use MinIO locally, run a local MinIO instance and set "
                    "MINIO_ENDPOINT=localhost:9000. Error: %s",
                    endpoint, exc,
                )
            else:
                logger.error("Failed to initialize MinIO client: %s", exc)
        finally:
            socket.setdefaulttimeout(old_timeout)

    @property
    def available(self) -> bool:
        return self.client is not None

    def _ensure_bucket_exists_with(self, client):
        import json
        try:
            if not client.bucket_exists(self.bucket_name):
                client.make_bucket(self.bucket_name)
                logger.info("Bucket '%s' created.", self.bucket_name)
            else:
                logger.info("Bucket '%s' already exists.", self.bucket_name)

            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": ["*"]},
                        "Action": ["s3:GetBucketLocation", "s3:ListBucket"],
                        "Resource": [f"arn:aws:s3:::{self.bucket_name}"],
                    },
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": ["*"]},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{self.bucket_name}/*"],
                    },
                ],
            }
            client.set_bucket_policy(self.bucket_name, json.dumps(policy))
            logger.info("Public read policy applied to '%s'.", self.bucket_name)
        except S3Error as exc:
            logger.error("Bucket init error: %s", exc)
            raise StorageError("Could not initialize storage bucket.")

    def upload_bytes(
        self,
        data: bytes,
        object_key: str,
        content_type: str = 'application/octet-stream',
    ) -> str:
        if not self.client:
            raise StorageError("Storage service not initialized.")
        try:
            self.client.put_object(
                self.bucket_name,
                object_key,
                io.BytesIO(data),
                len(data),
                content_type=content_type,
            )
            logger.info("Uploaded: %s (%d bytes)", object_key, len(data))
            return object_key
        except S3Error as exc:
            logger.error("MinIO upload error: %s", exc)
            raise StorageError("Failed to upload to storage.")

    def get_object_bytes(self, object_key: str) -> bytes | None:
        if not self.client:
            raise StorageError("Storage service not initialized.")
        try:
            response = self.client.get_object(self.bucket_name, object_key)
            return response.read()
        except Exception as exc:
            logger.error("MinIO get error for '%s': %s", object_key, exc)
            return None

    def delete_object(self, object_key: str):
        if not self.client:
            raise StorageError("Storage service not initialized.")
        try:
            self.client.remove_object(self.bucket_name, object_key)
            logger.info("Deleted: %s", object_key)
        except S3Error as exc:
            logger.error("MinIO delete error for '%s': %s", object_key, exc)
            raise StorageError("Failed to delete from storage.")

    def get_object_url(self, object_key: str) -> str:
        if not self.client:
            raise StorageError("Storage service not initialized.")
        if self.public_base_url:
            base = self.public_base_url.rstrip('/')
            key = object_key.lstrip('/')
            return f"{base}/{self.bucket_name}/{key}"
        try:
            return self.client.get_presigned_url(
                "GET",
                self.bucket_name,
                object_key,
                expires=timedelta(hours=1),
            )
        except S3Error as exc:
            logger.error("MinIO URL error: %s", exc)
            raise StorageError("Could not generate storage URL.")

    def build_logo_key(self, link_id: int, ext: str = 'png') -> str:
        return f"logos/{link_id}/{uuid.uuid4().hex}.{ext}"


storage_service = StorageService()
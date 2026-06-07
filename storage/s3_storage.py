# -*- coding: utf-8 -*-
"""
S3兼容对象存储后端
支持阿里云OSS、腾讯云COS、Amazon S3等S3协议兼容存储
"""

import logging
from typing import Optional
from storage.base import StorageBackend, StoredFile

logger = logging.getLogger(__name__)


class S3Storage(StorageBackend):
    """S3兼容对象存储（支持阿里云OSS、腾讯云COS、AWS S3）"""

    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        region: str = "us-east-1",
        prefix: str = "",
    ):
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket_name = bucket_name
        self.region = region
        self.prefix = prefix
        self._client = None
        self._bucket = None

    def _get_client(self):
        """延迟初始化S3客户端"""
        if self._client is not None:
            return self._client, self._bucket

        try:
            import boto3
            from botocore.config import Config

            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                config=Config(signature_version="s3v4"),
            )

            # 确保bucket存在
            try:
                self._client.head_bucket(Bucket=self.bucket_name)
            except Exception:
                self._client.create_bucket(Bucket=self.bucket_name)

            self._bucket = self.bucket_name
            logger.info(f"S3存储客户端初始化完成: {self.endpoint_url}/{self.bucket_name}")

        except ImportError:
            raise ImportError("boto3未安装，请执行: pip install boto3")

        return self._client, self._bucket

    async def save(self, file_data: bytes, path: str, content_type: Optional[str] = None) -> StoredFile:
        client, bucket = self._get_client()
        key = f"{self.prefix}{path}" if self.prefix else path

        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        client.put_object(Bucket=bucket, Key=key, Body=file_data, **extra_args)
        url = client.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=3600
        )

        return StoredFile(path=key, url=url, size=len(file_data), content_type=content_type)

    async def save_from_file(self, file_path: str, dest_path: str) -> StoredFile:
        import os
        client, bucket = self._get_client()
        key = f"{self.prefix}{dest_path}" if self.prefix else dest_path

        client.upload_file(file_path, bucket, key)
        url = client.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=3600
        )
        size = os.path.getsize(file_path)

        return StoredFile(path=key, url=url, size=size)

    async def get(self, path: str) -> bytes:
        client, bucket = self._get_client()
        key = f"{self.prefix}{path}" if self.prefix else path
        response = client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()

    async def delete(self, path: str) -> bool:
        client, bucket = self._get_client()
        key = f"{self.prefix}{path}" if self.prefix else path
        try:
            client.delete_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            return False

    async def exists(self, path: str) -> bool:
        client, bucket = self._get_client()
        key = f"{self.prefix}{path}" if self.prefix else path
        try:
            client.head_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            return False

    async def get_url(self, path: str, expires: int = 3600) -> Optional[str]:
        client, bucket = self._get_client()
        key = f"{self.prefix}{path}" if self.prefix else path
        try:
            return client.generate_presigned_url(
                "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires
            )
        except Exception:
            return None

    async def list_files(self, prefix: str = "") -> list:
        client, bucket = self._get_client()
        full_prefix = f"{self.prefix}{prefix}" if self.prefix else prefix
        files = []
        response = client.list_objects_v2(Bucket=bucket, Prefix=full_prefix)
        for obj in response.get("Contents", []):
            files.append({"path": obj["Key"], "size": obj["Size"]})
        return files

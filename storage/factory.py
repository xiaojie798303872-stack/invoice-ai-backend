# -*- coding: utf-8 -*-
"""
存储后端工厂
根据配置创建对应的存储后端实例
"""

import logging
from config import settings
from storage.base import StorageBackend
from storage.local import LocalStorage

logger = logging.getLogger(__name__)

_storage_instance: StorageBackend = None


def get_storage() -> StorageBackend:
    """获取存储后端实例（单例）"""
    global _storage_instance
    if _storage_instance is not None:
        return _storage_instance

    storage_type = getattr(settings, "STORAGE_TYPE", "local")

    if storage_type == "local":
        _storage_instance = LocalStorage(settings.UPLOAD_DIR)
        logger.info(f"使用本地文件存储: {settings.UPLOAD_DIR}")

    elif storage_type in ("oss", "cos", "s3"):
        try:
            from storage.s3_storage import S3Storage

            endpoint_map = {
                "oss": f"https://oss-cn-{getattr(settings, 'OSS_REGION', 'hangzhou')}.aliyuncs.com",
                "cos": f"https://cos.{getattr(settings, 'COS_REGION', 'ap-guangzhou')}.myqcloud.com",
                "s3": f"https://s3.{getattr(settings, 'S3_REGION', 'us-east-1')}.amazonaws.com",
            }

            _storage_instance = S3Storage(
                endpoint_url=endpoint_map.get(storage_type, ""),
                access_key=getattr(settings, "STORAGE_ACCESS_KEY", ""),
                secret_key=getattr(settings, "STORAGE_SECRET_KEY", ""),
                bucket_name=getattr(settings, "STORAGE_BUCKET", ""),
                region=getattr(settings, "STORAGE_REGION", ""),
                prefix=getattr(settings, "STORAGE_PREFIX", "invoices/"),
            )
            logger.info(f"使用S3兼容对象存储: {storage_type}")
        except Exception as e:
            logger.warning(f"S3存储初始化失败({e})，降级为本地存储")
            _storage_instance = LocalStorage(settings.UPLOAD_DIR)
    else:
        _storage_instance = LocalStorage(settings.UPLOAD_DIR)
        logger.info(f"未知存储类型 '{storage_type}'，使用本地存储")

    return _storage_instance

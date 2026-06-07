# -*- coding: utf-8 -*-
"""
文件存储抽象基类
定义统一的文件存储接口，支持本地存储/阿里云OSS/腾讯云COS/Amazon S3
"""

import abc
from typing import Optional, BinaryIO
from dataclasses import dataclass


@dataclass
class StoredFile:
    """存储文件信息"""
    path: str           # 存储路径/Key
    url: Optional[str]  # 可访问的URL（对象存储时可用）
    size: int           # 文件大小（字节）
    content_type: Optional[str] = None


class StorageBackend(abc.ABC):
    """文件存储后端抽象基类"""

    @abc.abstractmethod
    async def save(self, file_data: bytes, path: str, content_type: Optional[str] = None) -> StoredFile:
        """保存文件"""
        raise NotImplementedError

    @abc.abstractmethod
    async def save_from_file(self, file_path: str, dest_path: str) -> StoredFile:
        """从本地文件保存"""
        raise NotImplementedError

    @abc.abstractmethod
    async def get(self, path: str) -> bytes:
        """获取文件内容"""
        raise NotImplementedError

    @abc.abstractmethod
    async def delete(self, path: str) -> bool:
        """删除文件"""
        raise NotImplementedError

    @abc.abstractmethod
    async def exists(self, path: str) -> bool:
        """检查文件是否存在"""
        raise NotImplementedError

    @abc.abstractmethod
    async def get_url(self, path: str, expires: int = 3600) -> Optional[str]:
        """获取文件的访问URL"""
        raise NotImplementedError

    @abc.abstractmethod
    async def list_files(self, prefix: str = "") -> list:
        """列出文件"""
        raise NotImplementedError

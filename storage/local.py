# -*- coding: utf-8 -*-
"""
本地文件存储后端
将文件存储在本地文件系统中
"""

import os
import logging
from typing import Optional
from storage.base import StorageBackend, StoredFile

logger = logging.getLogger(__name__)


class LocalStorage(StorageBackend):
    """本地文件系统存储"""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    async def save(self, file_data: bytes, path: str, content_type: Optional[str] = None) -> StoredFile:
        full_path = os.path.join(self.base_dir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(file_data)
        return StoredFile(path=path, url=None, size=len(file_data), content_type=content_type)

    async def save_from_file(self, file_path: str, dest_path: str) -> StoredFile:
        import shutil
        full_path = os.path.join(self.base_dir, dest_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        shutil.copy2(file_path, full_path)
        size = os.path.getsize(full_path)
        return StoredFile(path=dest_path, url=None, size=size)

    async def get(self, path: str) -> bytes:
        full_path = os.path.join(self.base_dir, path)
        with open(full_path, "rb") as f:
            return f.read()

    async def delete(self, path: str) -> bool:
        full_path = os.path.join(self.base_dir, path)
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
        return False

    async def exists(self, path: str) -> bool:
        full_path = os.path.join(self.base_dir, path)
        return os.path.exists(full_path)

    async def get_url(self, path: str, expires: int = 3600) -> Optional[str]:
        return None  # 本地存储不提供URL

    async def list_files(self, prefix: str = "") -> list:
        base = os.path.join(self.base_dir, prefix) if prefix else self.base_dir
        files = []
        if os.path.exists(base):
            for item in os.listdir(base):
                full = os.path.join(base, item)
                if os.path.isfile(full):
                    files.append({"path": os.path.join(prefix, item) if prefix else item, "size": os.path.getsize(full)})
        return files

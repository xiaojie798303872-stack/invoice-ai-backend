# -*- coding: utf-8 -*-
"""
数据备份路由
提供手动备份、查看备份列表等接口
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from services.backup_service import backup_service
from notification.service import notification_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backup", tags=["数据备份"])


@router.post("/database", summary="备份数据库")
async def backup_database(
    label: Optional[str] = Query(None, description="备份标签"),
    db: AsyncSession = Depends(get_db),
):
    """手动触发数据库备份"""
    result = await backup_service.backup_database(label)

    if result.get("success"):
        await notification_service.notify_backup_complete(
            db, result["path"], result["size"] / 1024 / 1024
        )

    return {"code": 200, "data": result}


@router.post("/files", summary="备份上传文件")
async def backup_files(
    label: Optional[str] = Query(None, description="备份标签"),
    db: AsyncSession = Depends(get_db),
):
    """手动触发文件备份"""
    result = await backup_service.backup_files(label)
    return {"code": 200, "data": result}


@router.post("/full", summary="完整备份")
async def full_backup(
    label: Optional[str] = Query(None, description="备份标签"),
    db: AsyncSession = Depends(get_db),
):
    """完整备份（数据库+文件）"""
    result = await backup_service.full_backup(label)
    return {"code": 200, "data": result}


@router.get("/list", summary="查看备份列表")
async def list_backups():
    """查看所有备份文件"""
    backups = backup_service.list_backups()
    stats = backup_service.get_backup_stats()
    return {
        "code": 200,
        "data": {"backups": backups, "stats": stats},
    }


@router.get("/stats", summary="备份统计")
async def backup_stats():
    """获取备份统计信息"""
    stats = backup_service.get_backup_stats()
    return {"code": 200, "data": stats}


@router.get("/download/{filename}", summary="下载备份文件")
async def download_backup(filename: str):
    """下载指定备份文件"""
    import os
    from services.backup_service import backup_service

    filepath = os.path.join(backup_service.backup_dir, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="备份文件不存在")

    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="application/octet-stream",
    )

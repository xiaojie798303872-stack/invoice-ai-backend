# -*- coding: utf-8 -*-
"""
消息通知路由
提供站内消息的查询、标记已读、删除等接口
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from notification.service import notification_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["消息通知"])


@router.get("", summary="获取通知列表")
async def get_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取通知列表"""
    result = await notification_service.get_user_notifications(
        db, page=page, page_size=page_size,
        unread_only=unread_only, category=category,
    )
    return {"code": 200, "data": result}


@router.get("/unread-count", summary="获取未读通知数量")
async def get_unread_count(db: AsyncSession = Depends(get_db)):
    """获取未读通知数量"""
    count = await notification_service._get_unread_count(db)
    return {"code": 200, "data": {"count": count}}


@router.put("/{notification_id}/read", summary="标记通知为已读")
async def mark_as_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
):
    """标记通知为已读"""
    await notification_service.mark_as_read(db, notification_id)
    return {"code": 200, "message": "已标记为已读"}


@router.put("/read-all", summary="标记所有通知为已读")
async def mark_all_as_read(db: AsyncSession = Depends(get_db)):
    """标记所有通知为已读"""
    count = await notification_service.mark_all_as_read(db)
    return {"code": 200, "message": f"已标记 {count} 条通知为已读"}


@router.delete("/{notification_id}", summary="删除通知")
async def delete_notification(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除通知"""
    await notification_service.delete_notification(db, notification_id)
    return {"code": 200, "message": "删除成功"}

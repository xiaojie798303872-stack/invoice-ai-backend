# -*- coding: utf-8 -*-
"""
消息通知服务
支持站内消息和邮件通知
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from sqlalchemy import select, func, delete, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models import Notification
from config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """消息通知服务"""

    async def create_notification(
        self,
        db: AsyncSession,
        title: str,
        content: str = "",
        type: str = "info",
        category: str = "system",
        user_id: Optional[int] = None,
        related_id: Optional[int] = None,
        extra_data: Optional[dict] = None,
    ) -> Notification:
        """
        创建站内通知

        Args:
            db: 数据库会话
            title: 通知标题
            content: 通知内容
            type: 类型: info/success/warning/error
            category: 分类: system/upload/ocr/backup/export
            user_id: 关联用户ID
            related_id: 关联业务ID
            extra_data: 额外数据
        """
        notification = Notification(
            title=title,
            content=content,
            type=type,
            category=category,
            user_id=user_id,
            related_id=related_id,
            extra_data=json.dumps(extra_data) if extra_data else None,
        )
        db.add(notification)
        await db.commit()
        await db.refresh(notification)
        return notification

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html: bool = False,
    ) -> bool:
        """
        发送邮件通知

        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            body: 邮件内容
            html: 是否为HTML格式
        """
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            smtp_host = getattr(settings, "SMTP_HOST", "smtp.qq.com")
            smtp_port = getattr(settings, "SMTP_PORT", 465)
            smtp_user = getattr(settings, "SMTP_USER", "")
            smtp_password = getattr(settings, "SMTP_PASSWORD", "")
            smtp_from = getattr(settings, "SMTP_FROM", smtp_user)

            if not smtp_user or not smtp_password:
                logger.warning("邮件服务未配置(SMTP_USER/SMTP_PASSWORD)")
                return False

            msg = MIMEMultipart()
            msg["From"] = smtp_from
            msg["To"] = to_email
            msg["Subject"] = subject

            if html:
                msg.attach(MIMEText(body, "html", "utf-8"))
            else:
                msg.attach(MIMEText(body, "plain", "utf-8"))

            if smtp_port == 465:
                server = smtplib.SMTP_SSL(smtp_host, smtp_port)
            else:
                server = smtplib.SMTP(smtp_host, smtp_port)
                server.starttls()

            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, to_email, msg.as_string())
            server.quit()

            logger.info(f"邮件发送成功: {to_email} - {subject}")
            return True

        except Exception as e:
            logger.error(f"邮件发送失败: {e}", exc_info=True)
            return False

    async def notify_upload_complete(
        self, db: AsyncSession, success_count: int, fail_count: int, user_id: Optional[int] = None
    ):
        """上传完成通知"""
        title = "发票上传完成"
        if fail_count == 0:
            content = f"成功上传并识别 {success_count} 张发票"
            ntype = "success"
        else:
            content = f"上传完成：{success_count} 张成功，{fail_count} 张失败"
            ntype = "warning"

        await self.create_notification(
            db=db, title=title, content=content, type=ntype,
            category="upload", user_id=user_id,
        )

    async def notify_ocr_failed(
        self, db: AsyncSession, filename: str, error: str, user_id: Optional[int] = None
    ):
        """OCR识别失败通知"""
        await self.create_notification(
            db=db,
            title="发票识别失败",
            content=f"文件 {filename} 识别失败：{error}",
            type="error",
            category="ocr",
            user_id=user_id,
        )

    async def notify_export_complete(
        self, db: AsyncSession, filename: str, record_count: int, user_id: Optional[int] = None
    ):
        """导出完成通知"""
        await self.create_notification(
            db=db,
            title="数据导出完成",
            content=f"已导出 {record_count} 条记录，文件：{filename}",
            type="success",
            category="export",
            user_id=user_id,
        )

    async def notify_backup_complete(
        self, db: AsyncSession, backup_path: str, size_mb: float, user_id: Optional[int] = None
    ):
        """备份完成通知"""
        await self.create_notification(
            db=db,
            title="数据备份完成",
            content=f"备份文件：{backup_path}，大小：{size_mb:.2f}MB",
            type="success",
            category="backup",
            user_id=user_id,
        )

    async def get_user_notifications(
        self,
        db: AsyncSession,
        user_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
        unread_only: bool = False,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取用户通知列表"""
        query = select(Notification)
        count_query = select(func.count()).select_from(Notification)

        conditions = []
        if user_id:
            conditions.append(Notification.user_id == user_id)
        if unread_only:
            conditions.append(Notification.is_read == False)
        if category:
            conditions.append(Notification.category == category)

        if conditions:
            from sqlalchemy import and_
            filter_cond = and_(*conditions)
            query = query.where(filter_cond)
            count_query = count_query.where(filter_cond)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        query = query.order_by(Notification.created_at.desc()).offset(offset).limit(page_size)

        result = await db.execute(query)
        notifications = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "unread_count": total if unread_only else await self._get_unread_count(db, user_id),
            "items": [n.to_dict() for n in notifications],
        }

    async def _get_unread_count(self, db: AsyncSession, user_id: Optional[int] = None) -> int:
        """获取未读通知数量"""
        conditions = [Notification.is_read == False]
        if user_id:
            conditions.append(Notification.user_id == user_id)
        from sqlalchemy import and_
        result = await db.execute(
            select(func.count()).select_from(Notification).where(and_(*conditions))
        )
        return result.scalar() or 0

    async def mark_as_read(self, db: AsyncSession, notification_id: int, user_id: Optional[int] = None) -> bool:
        """标记通知为已读"""
        conditions = [Notification.id == notification_id]
        if user_id:
            conditions.append(Notification.user_id == user_id)
        from sqlalchemy import and_
        await db.execute(
            update(Notification).where(and_(*conditions)).values(is_read=True)
        )
        await db.commit()
        return True

    async def mark_all_as_read(self, db: AsyncSession, user_id: Optional[int] = None) -> int:
        """标记所有通知为已读"""
        conditions = [Notification.is_read == False]
        if user_id:
            conditions.append(Notification.user_id == user_id)
        from sqlalchemy import and_
        result = await db.execute(
            update(Notification).where(and_(*conditions)).values(is_read=True)
        )
        await db.commit()
        return result.rowcount

    async def delete_notification(self, db: AsyncSession, notification_id: int) -> bool:
        """删除通知"""
        await db.execute(delete(Notification).where(Notification.id == notification_id))
        await db.commit()
        return True


# 全局通知服务实例
notification_service = NotificationService()

# -*- coding: utf-8 -*-
"""
SQLAlchemy数据模型
定义发票（Invoice）数据表结构
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime,
    Enum as SAEnum, Index, Boolean
)
from database import Base


class Invoice(Base):
    """发票数据模型"""

    __tablename__ = "invoices"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")

    # 发票基本信息
    invoice_number = Column(String(50), nullable=True, index=True, comment="发票号码")
    invoice_code = Column(String(50), nullable=True, index=True, comment="发票代码")
    invoice_type = Column(
        String(20), nullable=True, index=True,
        comment="发票类型: 增值税专票/增值税普票/电子发票/火车票/机票"
    )
    invoice_date = Column(String(20), nullable=True, comment="开票日期")

    # 金额信息
    amount = Column(Float, nullable=True, comment="金额（不含税）")
    tax_amount = Column(Float, nullable=True, comment="税额")
    total_amount = Column(Float, nullable=True, index=True, comment="价税合计")

    # 销方信息
    seller_name = Column(String(200), nullable=True, comment="销方名称")
    seller_tax_number = Column(String(50), nullable=True, comment="销方税号")

    # 购方信息
    buyer_name = Column(String(200), nullable=True, comment="购方名称")
    buyer_tax_number = Column(String(50), nullable=True, comment="购方税号")

    # 校验码
    check_code = Column(String(50), nullable=True, comment="校验码")

    # 自动分类
    category = Column(
        String(20), nullable=True, index=True,
        comment="自动分类: 餐饮/交通/办公/住宿/其他"
    )

    # 状态
    status = Column(
        String(20), nullable=False, default="pending", index=True,
        comment="状态: pending/reviewed/exported"
    )

    # 文件存储路径
    file_path = Column(String(500), nullable=True, comment="上传文件存储路径")

    # OCR原始识别文本
    ocr_raw_text = Column(Text, nullable=True, comment="OCR原始识别文本")

    # 时间戳
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    updated_at = Column(
        DateTime, nullable=False,
        default=datetime.now, onupdate=datetime.now,
        comment="更新时间"
    )

    # 创建索引以提高查询性能
    __table_args__ = (
        Index("idx_type_status", "invoice_type", "status"),
        Index("idx_category_status", "category", "status"),
        Index("idx_date", "invoice_date"),
    )

    def to_dict(self) -> dict:
        """将模型转换为字典"""
        return {
            "id": self.id,
            "invoice_number": self.invoice_number,
            "invoice_code": self.invoice_code,
            "invoice_type": self.invoice_type,
            "invoice_date": self.invoice_date,
            "amount": self.amount,
            "tax_amount": self.tax_amount,
            "total_amount": self.total_amount,
            "seller_name": self.seller_name,
            "seller_tax_number": self.seller_tax_number,
            "buyer_name": self.buyer_name,
            "buyer_tax_number": self.buyer_tax_number,
            "check_code": self.check_code,
            "category": self.category,
            "status": self.status,
            "file_path": self.file_path,
            "ocr_raw_text": self.ocr_raw_text,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ==================== 用户认证相关模型 ====================

class User(Base):
    """用户数据模型"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True, comment="用户名")
    email = Column(String(100), unique=True, nullable=True, index=True, comment="邮箱")
    hashed_password = Column(String(200), nullable=False, comment="密码哈希")
    full_name = Column(String(100), nullable=True, comment="姓名")
    role = Column(String(20), nullable=False, default="user", comment="角色: admin/user")
    is_active = Column(Boolean, nullable=False, default=True, comment="是否激活")
    last_login = Column(DateTime, nullable=True, comment="最后登录时间")
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        """将用户模型转换为字典（不包含密码）"""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "is_active": self.is_active,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ==================== 消息通知相关模型 ====================

class Notification(Base):
    """消息通知模型"""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True, index=True, comment="关联用户ID（None为系统通知）")
    title = Column(String(200), nullable=False, comment="通知标题")
    content = Column(Text, nullable=True, comment="通知内容")
    type = Column(String(30), nullable=False, default="info", comment="通知类型: info/success/warning/error")
    category = Column(String(30), nullable=False, default="system", comment="通知分类: system/upload/ocr/backup/export")
    is_read = Column(Boolean, nullable=False, default=False, comment="是否已读")
    related_id = Column(Integer, nullable=True, comment="关联的业务ID（如发票ID）")
    extra_data = Column(Text, nullable=True, comment="额外数据（JSON格式）")
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment="创建时间")

    __table_args__ = (
        Index("idx_user_read", "user_id", "is_read"),
        Index("idx_category", "category"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "content": self.content,
            "type": self.type,
            "category": self.category,
            "is_read": self.is_read,
            "related_id": self.related_id,
            "extra_data": self.extra_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

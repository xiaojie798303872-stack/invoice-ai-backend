# -*- coding: utf-8 -*-
"""
配置文件 - 发票AI自动排序整理系统
包含数据库、上传、OCR等相关配置
"""

import os
from pathlib import Path
from typing import List


class Settings:
    """应用配置类"""

    # 项目基础路径
    BASE_DIR: Path = Path(__file__).resolve().parent

    # 数据库配置（使用SQLite，生产环境可切换为PostgreSQL/MySQL）
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./invoice_ai.db"
    )

    # ===== 数据库引擎配置 =====
    # 数据库引擎类型: sqlite / postgresql / mysql
    DB_ENGINE: str = os.getenv("DB_ENGINE", "sqlite")

    # PostgreSQL配置
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "invoice_ai")

    # MySQL配置
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "root")
    MYSQL_DB: str = os.getenv("MYSQL_DB", "invoice_ai")

    @property
    def database_url(self) -> str:
        """根据引擎类型构建数据库URL"""
        if self.DB_ENGINE == "postgresql":
            return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        elif self.DB_ENGINE == "mysql":
            return f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}?charset=utf8mb4"
        else:
            return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./invoice_ai.db")

    # 上传文件存储目录
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads"))

    # 允许上传的文件类型
    ALLOWED_FILE_TYPES: List[str] = [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".pdf"]

    # 文件大小限制（单位：字节，默认50MB）
    MAX_FILE_SIZE: int = 50 * 1024 * 1024

    # OCR相关配置
    # OCR置信度阈值，低于此阈值的结果将被过滤
    OCR_CONFIDENCE_THRESHOLD: float = 0.5

    # PaddleOCR使用GPU
    OCR_USE_GPU: bool = False

    # PaddleOCR语言设置
    OCR_LANG: str = "ch"

    # 发票类型枚举
    INVOICE_TYPES: List[str] = [
        "增值税专票",
        "增值税普票",
        "电子发票",
        "火车票",
        "机票",
    ]

    # 发票自动分类枚举
    INVOICE_CATEGORIES: List[str] = [
        "餐饮",
        "交通",
        "办公",
        "住宿",
        "其他",
    ]

    # 发票状态枚举
    INVOICE_STATUSES: List[str] = ["pending", "reviewed", "exported"]

    # 分页默认配置
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # CORS配置
    # 生产环境请修改为实际的前端域名
    CORS_ORIGINS: List[str] = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5500"
    ).split(",")

    # API标题和描述
    API_TITLE: str = "发票AI自动排序整理系统"
    API_DESCRIPTION: str = "基于PaddleOCR的发票智能识别、分类与管理系统"
    API_VERSION: str = "1.0.0"

    # ===== JWT认证配置 =====
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "120"))
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    # ===== 云OCR配置 =====
    # OCR引擎选择: local(本地PaddleOCR) / baidu(百度云) / tencent(腾讯云)
    OCR_ENGINE: str = os.getenv("OCR_ENGINE", "local")

    # 百度云OCR配置
    BAIDU_OCR_API_KEY: str = os.getenv("BAIDU_OCR_API_KEY", "")
    BAIDU_OCR_SECRET_KEY: str = os.getenv("BAIDU_OCR_SECRET_KEY", "")
    BAIDU_OCR_VAT_INVOICE_URL: str = "https://aip.baidubce.com/rest/2.0/ocr/v1/vat_invoice"
    BAIDU_OCR_GENERAL_URL: str = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"

    # 腾讯云OCR配置
    TENCENT_OCR_SECRET_ID: str = os.getenv("TENCENT_OCR_SECRET_ID", "")
    TENCENT_OCR_SECRET_KEY: str = os.getenv("TENCENT_OCR_SECRET_KEY", "")
    TENCENT_OCR_REGION: str = os.getenv("TENCENT_OCR_REGION", "ap-guangzhou")
    TENCENT_OCR_VAT_INVOICE_URL: str = "https://ocr.tencentcloudapi.com"

    # ===== 文件存储配置 =====
    # 存储类型: local / oss(阿里云) / cos(腾讯云) / s3(AWS)
    STORAGE_TYPE: str = os.getenv("STORAGE_TYPE", "local")
    STORAGE_ACCESS_KEY: str = os.getenv("STORAGE_ACCESS_KEY", "")
    STORAGE_SECRET_KEY: str = os.getenv("STORAGE_SECRET_KEY", "")
    STORAGE_BUCKET: str = os.getenv("STORAGE_BUCKET", "")
    STORAGE_REGION: str = os.getenv("STORAGE_REGION", "")
    STORAGE_PREFIX: str = os.getenv("STORAGE_PREFIX", "invoices/")
    OSS_REGION: str = os.getenv("OSS_REGION", "hangzhou")
    COS_REGION: str = os.getenv("COS_REGION", "ap-guangzhou")
    S3_REGION: str = os.getenv("S3_REGION", "us-east-1")

    # ===== 邮件通知配置 =====
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.qq.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "465"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    # ===== 数据备份配置 =====
    BACKUP_RETENTION_DAYS: int = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))
    BACKUP_MAX_COUNT: int = int(os.getenv("BACKUP_MAX_COUNT", "50"))
    BACKUP_CRON: str = os.getenv("BACKUP_CRON", "0 2 * * *")  # 每天凌晨2点自动备份


# 全局配置实例
settings = Settings()

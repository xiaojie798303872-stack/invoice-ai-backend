# -*- coding: utf-8 -*-
"""
数据库连接与初始化模块
支持SQLite（开发）/ PostgreSQL（生产）/ MySQL（生产）
通过环境变量 DB_ENGINE 切换引擎
"""

import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from config import settings

logger = logging.getLogger(__name__)

# 根据配置构建数据库URL
DATABASE_URL = settings.database_url

# 根据引擎类型设置连接池参数
engine_kwargs = {
    "echo": False,
    "future": True,
}

if settings.DB_ENGINE == "sqlite":
    # SQLite不需要连接池
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL/MySQL使用连接池
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = 3600

logger.info(f"数据库引擎: {settings.DB_ENGINE}, URL: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")

# 创建异步引擎
engine = create_async_engine(DATABASE_URL, **engine_kwargs)

# 创建异步会话工厂
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy声明式基类"""
    pass


async def init_db() -> None:
    """初始化数据库，创建所有表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info(f"数据库表初始化完成（引擎: {settings.DB_ENGINE}）")


async def get_db() -> AsyncSession:
    """
    获取数据库会话的依赖注入函数
    用作FastAPI路由的Depends参数
    """
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def close_db() -> None:
    """关闭数据库引擎连接"""
    await engine.dispose()
    logger.info("数据库连接已关闭")

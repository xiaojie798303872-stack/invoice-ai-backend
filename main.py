# -*- coding: utf-8 -*-
"""
FastAPI应用入口 - 发票AI自动排序整理系统
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from database import init_db
from routers import invoice, upload, stats
from routers.backup import router as backup_router
from auth.router import router as auth_router
from notification.router import router as notification_router

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化，关闭时清理"""
    # 启动时执行
    logger.info("=" * 50)
    logger.info(f"发票AI自动排序整理系统 v{settings.API_VERSION}")
    logger.info("=" * 50)

    # 创建上传目录
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    logger.info(f"上传目录: {settings.UPLOAD_DIR}")

    # 初始化数据库（创建所有表）
    logger.info("正在初始化数据库...")
    await init_db()
    logger.info("数据库初始化完成")

    logger.info("系统启动完成，等待请求...")

    # 启动自动备份定时任务
    import asyncio
    from datetime import datetime
    from services.backup_service import backup_service

    async def auto_backup_task():
        """自动备份定时任务"""
        while True:
            await asyncio.sleep(3600)  # 每小时检查一次
            now = datetime.now()
            # 检查是否到了备份时间（每天凌晨2点）
            if now.hour == 2 and now.minute < 5:
                logger.info("触发自动备份...")
                try:
                    await backup_service.full_backup("auto")
                except Exception as e:
                    logger.error(f"自动备份失败: {e}")

    backup_task = asyncio.create_task(auto_backup_task())

    yield

    # 关闭时执行
    logger.info("系统正在关闭...")


# 创建FastAPI应用
app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
    lifespan=lifespan,
)


# 配置CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": f"服务器内部错误: {str(exc)}",
            "data": None,
        },
    )


# 注册路由
app.include_router(invoice.router)
app.include_router(upload.router)
app.include_router(stats.router)
app.include_router(auth_router)
app.include_router(notification_router)
app.include_router(backup_router)


# 根路径 - 健康检查
@app.get("/", tags=["系统"])
async def root():
    """根路径，返回系统基本信息"""
    return {
        "name": settings.API_TITLE,
        "version": settings.API_VERSION,
        "description": settings.API_DESCRIPTION,
        "status": "running",
    }


@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查接口"""
    return {"status": "ok"}


# 启动命令提示
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )

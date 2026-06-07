# -*- coding: utf-8 -*-
"""
FastAPI认证依赖注入模块
提供获取当前用户、角色权限验证等依赖函数
"""

import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt_handler import verify_token
from database import get_db
from models import User

logger = logging.getLogger(__name__)

# OAuth2密码承载方案，指定令牌获取地址
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    根据JWT令牌获取当前用户

    Args:
        token: JWT访问令牌
        db: 数据库会话

    Returns:
        User: 当前用户对象

    Raises:
        HTTPException: 令牌无效或用户不存在时抛出401异常
    """
    # 验证令牌
    payload = verify_token(token)
    if payload is None:
        logger.warning("认证失败：无效的令牌")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 检查令牌类型是否为access_token
    token_type = payload.get("type")
    if token_type != "access":
        logger.warning(f"认证失败：令牌类型不正确，期望access，实际{token_type}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌类型不正确，请使用access_token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 从payload中提取用户ID
    user_id_str = payload.get("sub")
    if user_id_str is None:
        logger.warning("认证失败：令牌中缺少用户标识")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌中缺少用户标识",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 查询数据库获取用户
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        logger.warning(f"认证失败：无效的用户ID格式: {user_id_str}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的用户标识",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning(f"认证失败：用户不存在，ID: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    获取当前已激活的用户

    Args:
        current_user: 当前用户对象（由get_current_user注入）

    Returns:
        User: 当前已激活的用户对象

    Raises:
        HTTPException: 用户已被禁用时抛出403异常
    """
    if not current_user.is_active:
        logger.warning(f"用户已被禁用: {current_user.username}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用，请联系管理员",
        )
    return current_user


def require_role(role: str):
    """
    角色权限验证依赖工厂函数

    Args:
        role: 要求的角色名称（如 "admin"）

    Returns:
        依赖函数，用于验证当前用户是否具有指定角色
    """
    async def check_role(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        """
        检查当前用户是否具有所需角色

        Args:
            current_user: 当前激活用户

        Returns:
            User: 验证通过的用户对象

        Raises:
            HTTPException: 用户角色不匹配时抛出403异常
        """
        if current_user.role != role:
            logger.warning(
                f"权限不足：用户 {current_user.username} "
                f"角色为 {current_user.role}，需要 {role}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要 {role} 角色",
            )
        return current_user

    return check_role

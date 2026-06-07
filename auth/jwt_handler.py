# -*- coding: utf-8 -*-
"""
JWT令牌处理模块
负责生成和验证JWT访问令牌与刷新令牌
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt

from config import settings

logger = logging.getLogger(__name__)


def create_access_token(user_id: int, role: str) -> str:
    """
    生成访问令牌（access_token）

    Args:
        user_id: 用户ID
        role: 用户角色

    Returns:
        str: JWT访问令牌
    """
    try:
        # 计算过期时间
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )
        # 构造payload
        payload = {
            "sub": str(user_id),       # subject，用户唯一标识
            "role": role,              # 用户角色
            "type": "access",          # 令牌类型
            "exp": expire,             # 过期时间
            "iat": datetime.now(timezone.utc),  # 签发时间
        }
        # 生成JWT令牌
        token = jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        logger.info(f"成功生成access_token，用户ID: {user_id}")
        return token
    except Exception as e:
        logger.error(f"生成access_token失败: {e}", exc_info=True)
        raise


def create_refresh_token(user_id: int) -> str:
    """
    生成刷新令牌（refresh_token）

    Args:
        user_id: 用户ID

    Returns:
        str: JWT刷新令牌
    """
    try:
        # 计算过期时间
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )
        # 构造payload
        payload = {
            "sub": str(user_id),       # subject，用户唯一标识
            "type": "refresh",         # 令牌类型
            "exp": expire,             # 过期时间
            "iat": datetime.now(timezone.utc),  # 签发时间
        }
        # 生成JWT令牌
        token = jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        logger.info(f"成功生成refresh_token，用户ID: {user_id}")
        return token
    except Exception as e:
        logger.error(f"生成refresh_token失败: {e}", exc_info=True)
        raise


def verify_token(token: str) -> Optional[dict]:
    """
    验证JWT令牌并返回payload

    Args:
        token: JWT令牌字符串

    Returns:
        dict: 令牌payload数据，验证失败返回None
    """
    try:
        # 解码并验证JWT令牌
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        logger.debug(f"令牌验证成功，payload: {payload}")
        return payload
    except JWTError as e:
        logger.warning(f"令牌验证失败: {e}")
        return None
    except Exception as e:
        logger.error(f"验证令牌时发生未知错误: {e}", exc_info=True)
        return None

# -*- coding: utf-8 -*-
"""
认证路由模块
提供用户注册、登录、刷新令牌、修改密码、获取当前用户信息、登出等接口
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_active_user, oauth2_scheme
from auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    verify_token,
)
from auth.password import hash_password, verify_password
from config import settings
from database import get_db
from models import User
from schemas import (
    ApiResponse,
    ChangePasswordRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)

logger = logging.getLogger(__name__)

# 创建认证路由器
router = APIRouter(prefix="/api/auth", tags=["用户认证"])


@router.post("/register", response_model=ApiResponse, summary="用户注册")
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db),
):
    """
    用户注册接口

    - 创建新用户账号
    - 密码经过bcrypt哈希加密存储
    - 默认角色为普通用户（user）
    """
    # 检查用户名是否已存在
    result = await db.execute(
        select(User).where(User.username == user_data.username)
    )
    existing_user = result.scalar_one_or_none()
    if existing_user:
        logger.warning(f"注册失败：用户名已存在: {user_data.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在",
        )

    # 检查邮箱是否已被使用（如果提供了邮箱）
    if user_data.email:
        result = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        existing_email = result.scalar_one_or_none()
        if existing_email:
            logger.warning(f"注册失败：邮箱已被使用: {user_data.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该邮箱已被注册",
            )

    # 创建新用户
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        role="user",           # 默认角色为普通用户
        is_active=True,       # 默认激活
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    logger.info(f"新用户注册成功: {user_data.username}，ID: {new_user.id}")

    return ApiResponse(
        code=201,
        message="注册成功",
        data={
            "id": new_user.id,
            "username": new_user.username,
        },
    )


@router.post("/login", response_model=TokenResponse, summary="用户登录")
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """
    用户登录接口

    - 验证用户名和密码
    - 返回access_token和refresh_token
    - access_token有效期2小时，refresh_token有效期7天
    """
    # 查询用户
    result = await db.execute(
        select(User).where(User.username == login_data.username)
    )
    user = result.scalar_one_or_none()

    # 验证用户是否存在
    if not user:
        logger.warning(f"登录失败：用户不存在: {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    # 验证密码
    if not verify_password(login_data.password, user.hashed_password):
        logger.warning(f"登录失败：密码错误: {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    # 检查用户是否被禁用
    if not user.is_active:
        logger.warning(f"登录失败：用户已被禁用: {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用，请联系管理员",
        )

    # 更新最后登录时间
    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    # 生成令牌
    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id)

    logger.info(f"用户登录成功: {login_data.username}，ID: {user.id}")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse, summary="刷新令牌")
async def refresh_token(
    request_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    刷新令牌接口

    - 使用refresh_token获取新的access_token和refresh_token
    - 旧的refresh_token同时失效（单次使用策略）
    """
    # 验证refresh_token
    payload = verify_token(request_data.refresh_token)
    if payload is None:
        logger.warning("令牌刷新失败：无效的refresh_token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌",
        )

    # 检查令牌类型
    token_type = payload.get("type")
    if token_type != "refresh":
        logger.warning(f"令牌刷新失败：令牌类型不正确，期望refresh，实际{token_type}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请使用refresh_token进行刷新",
        )

    # 提取用户ID
    user_id_str = payload.get("sub")
    if user_id_str is None:
        logger.warning("令牌刷新失败：令牌中缺少用户标识")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌中缺少用户标识",
        )

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的用户标识",
        )

    # 查询用户是否存在且激活
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(f"令牌刷新失败：用户不存在，ID: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )

    if not user.is_active:
        logger.warning(f"令牌刷新失败：用户已被禁用，ID: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )

    # 生成新的令牌对
    new_access_token = create_access_token(user.id, user.role)
    new_refresh_token = create_refresh_token(user.id)

    logger.info(f"令牌刷新成功，用户ID: {user_id}")

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/change-password", response_model=ApiResponse, summary="修改密码")
async def change_password(
    request_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    修改密码接口

    - 需要提供旧密码进行验证
    - 修改成功后所有已发放的令牌仍然有效（可考虑强制失效）
    """
    # 验证旧密码
    if not verify_password(request_data.old_password, current_user.hashed_password):
        logger.warning(
            f"修改密码失败：旧密码验证失败，用户: {current_user.username}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码不正确",
        )

    # 更新密码
    current_user.hashed_password = hash_password(request_data.new_password)
    await db.commit()

    logger.info(f"密码修改成功，用户: {current_user.username}")

    return ApiResponse(
        code=200,
        message="密码修改成功",
    )


@router.get("/me", response_model=UserResponse, summary="获取当前用户信息")
async def get_me(
    current_user: User = Depends(get_current_active_user),
):
    """
    获取当前登录用户的信息

    - 需要携带有效的access_token
    - 返回用户基本信息（不包含密码）
    """
    logger.debug(f"获取用户信息: {current_user.username}")
    return current_user


@router.post("/logout", response_model=ApiResponse, summary="用户登出")
async def logout(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_active_user),
):
    """
    用户登出接口

    - 客户端应丢弃本地存储的令牌
    - 服务端为无状态JWT，当前实现仅记录日志
    - 如需服务端令牌失效，可扩展实现令牌黑名单机制
    """
    logger.info(f"用户登出: {current_user.username}")

    # TODO: 可扩展实现令牌黑名单（将token加入Redis/数据库黑名单）
    # 当前为无状态JWT，服务端不维护会话状态
    # 客户端应在登出后清除本地存储的access_token和refresh_token

    return ApiResponse(
        code=200,
        message="登出成功",
    )

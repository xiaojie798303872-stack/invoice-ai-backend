# -*- coding: utf-8 -*-
"""
密码处理模块
负责密码的哈希加密与验证
"""

import logging

from passlib.context import CryptContext

# 创建密码上下文，使用bcrypt算法
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    """
    对明文密码进行哈希加密

    Args:
        password: 明文密码

    Returns:
        str: 哈希后的密码字符串
    """
    try:
        hashed = pwd_context.hash(password)
        logger.info("密码哈希成功")
        return hashed
    except Exception as e:
        logger.error(f"密码哈希失败: {e}", exc_info=True)
        raise


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码是否与哈希密码匹配

    Args:
        plain_password: 明文密码
        hashed_password: 哈希后的密码

    Returns:
        bool: 密码匹配返回True，否则返回False
    """
    try:
        result = pwd_context.verify(plain_password, hashed_password)
        if not result:
            logger.warning("密码验证失败，密码不匹配")
        return result
    except Exception as e:
        logger.error(f"密码验证过程发生错误: {e}", exc_info=True)
        return False

# -*- coding: utf-8 -*-
"""
工具函数模块
提供文件类型验证、唯一文件名生成、日期格式化等通用工具
"""

import os
import uuid
import re
from datetime import datetime
from typing import Optional

from config import settings


def validate_file_type(filename: str) -> bool:
    """
    验证文件类型是否在允许的范围内

    Args:
        filename: 文件名

    Returns:
        bool: 文件类型是否合法
    """
    if not filename:
        return False
    ext = os.path.splitext(filename)[1].lower()
    return ext in settings.ALLOWED_FILE_TYPES


def generate_unique_filename(original_filename: str) -> str:
    """
    生成唯一文件名，保留原始文件扩展名

    Args:
        original_filename: 原始文件名

    Returns:
        str: 唯一文件名
    """
    ext = os.path.splitext(original_filename)[1].lower()
    unique_id = uuid.uuid4().hex[:12]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{unique_id}{ext}"


def format_date(date_str: str) -> Optional[str]:
    """
    格式化日期字符串，统一为 YYYY-MM-DD 格式

    Args:
        date_str: 原始日期字符串

    Returns:
        Optional[str]: 格式化后的日期字符串，解析失败返回None
    """
    if not date_str:
        return None

    # 常见日期格式正则匹配
    patterns = [
        # YYYY年MM月DD日
        (r"(\d{4})年(\d{1,2})月(\d{1,2})日", lambda m: f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"),
        # YYYYMMDD
        (r"(\d{4})(\d{2})(\d{2})", lambda m: f"{m.group(1)}-{m.group(2)}-{m.group(3)}"),
        # YYYY-MM-DD
        (r"(\d{4})-(\d{1,2})-(\d{1,2})", lambda m: f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"),
        # YYYY/MM/DD
        (r"(\d{4})/(\d{1,2})/(\d{1,2})", lambda m: f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"),
    ]

    for pattern, formatter in patterns:
        match = re.search(pattern, date_str)
        if match:
            try:
                return formatter(match)
            except (ValueError, IndexError):
                continue

    return None


def format_amount(amount_str: str) -> Optional[float]:
    """
    格式化金额字符串为浮点数

    Args:
        amount_str: 金额字符串

    Returns:
        Optional[float]: 格式化后的金额，解析失败返回None
    """
    if not amount_str:
        return None

    # 移除常见干扰字符
    cleaned = re.sub(r"[¥￥,，\s元圆]", "", amount_str)

    # 处理中文大写数字（简单处理）
    chinese_num_map = {
        "零": "0", "壹": "1", "贰": "2", "叁": "3", "肆": "4",
        "伍": "5", "陆": "6", "柒": "7", "捌": "8", "玖": "9",
    }
    for cn, num in chinese_num_map.items():
        cleaned = cleaned.replace(cn, num)

    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def clean_text(text: str) -> str:
    """
    清理OCR识别文本中的多余空白和特殊字符

    Args:
        text: 原始文本

    Returns:
        str: 清理后的文本
    """
    if not text:
        return ""
    # 替换多个连续空白为单个空格
    text = re.sub(r"\s+", " ", text)
    # 去除首尾空白
    text = text.strip()
    return text


def extract_month_key(date_str: Optional[str]) -> Optional[str]:
    """
    从日期字符串中提取月份键（YYYY-MM格式）

    Args:
        date_str: 日期字符串

    Returns:
        Optional[str]: YYYY-MM格式的月份键
    """
    if not date_str:
        return None
    match = re.match(r"(\d{4})-(\d{2})", date_str)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    return None

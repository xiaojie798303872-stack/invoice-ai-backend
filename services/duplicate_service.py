# -*- coding: utf-8 -*-
"""
发票查重服务
基于发票号码和金额进行智能查重，避免重复录入
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models import Invoice

logger = logging.getLogger(__name__)


class DuplicateService:
    """发票查重服务"""

    async def check_duplicate(
        self,
        db: AsyncSession,
        invoice_number: Optional[str] = None,
        invoice_code: Optional[str] = None,
        amount: Optional[float] = None,
        invoice_date: Optional[str] = None,
        exclude_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        检查发票是否重复

        查重规则（按优先级）：
        1. 发票号码 + 发票代码 完全匹配（高置信度）
        2. 发票号码 + 金额 匹配（中置信度）
        3. 发票号码 + 日期 匹配（低置信度）
        4. 仅发票号码匹配（最低置信度）

        Args:
            db: 数据库会话
            invoice_number: 发票号码
            invoice_code: 发票代码
            amount: 金额
            invoice_date: 开票日期
            exclude_id: 排除的发票ID（编辑时使用）

        Returns:
            Dict: {"is_duplicate": bool, "confidence": str, "matched": list}
        """
        if not invoice_number:
            return {"is_duplicate": False, "confidence": "none", "matched": []}

        conditions = [Invoice.invoice_number == invoice_number]
        if exclude_id:
            conditions.append(Invoice.id != exclude_id)

        # 规则1: 发票号码 + 发票代码 完全匹配
        if invoice_code:
            rule1_conditions = conditions + [Invoice.invoice_code == invoice_code]
            result = await db.execute(
                select(Invoice).where(and_(*rule1_conditions))
            )
            matched = result.scalars().all()
            if matched:
                return {
                    "is_duplicate": True,
                    "confidence": "high",
                    "reason": "发票号码和发票代码完全匹配",
                    "matched": [inv.to_dict() for inv in matched],
                }

        # 规则2: 发票号码 + 金额 匹配
        if amount is not None:
            rule2_conditions = conditions + [Invoice.total_amount == amount]
            result = await db.execute(
                select(Invoice).where(and_(*rule2_conditions))
            )
            matched = result.scalars().all()
            if matched:
                return {
                    "is_duplicate": True,
                    "confidence": "medium",
                    "reason": "发票号码和金额匹配",
                    "matched": [inv.to_dict() for inv in matched],
                }

        # 规则3: 发票号码 + 日期 匹配
        if invoice_date:
            rule3_conditions = conditions + [Invoice.invoice_date == invoice_date]
            result = await db.execute(
                select(Invoice).where(and_(*rule3_conditions))
            )
            matched = result.scalars().all()
            if matched:
                return {
                    "is_duplicate": True,
                    "confidence": "low",
                    "reason": "发票号码和日期匹配",
                    "matched": [inv.to_dict() for inv in matched],
                }

        # 规则4: 仅发票号码
        result = await db.execute(
            select(Invoice).where(and_(*conditions))
        )
        matched = result.scalars().all()
        if matched:
            return {
                "is_duplicate": True,
                "confidence": "lowest",
                "reason": "发票号码匹配（仅参考）",
                "matched": [inv.to_dict() for inv in matched],
            }

        return {"is_duplicate": False, "confidence": "none", "matched": []}

    async def find_all_duplicates(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        查找系统中所有疑似重复的发票

        Returns:
            List[Dict]: 重复发票组列表
        """
        # 查找有相同发票号码的发票组
        result = await db.execute(
            select(
                Invoice.invoice_number,
                func.count(Invoice.id).label("count"),
            )
            .where(Invoice.invoice_number.isnot(None))
            .group_by(Invoice.invoice_number)
            .having(func.count(Invoice.id) > 1)
        )

        duplicate_groups = []
        for row in result.all():
            group_result = await db.execute(
                select(Invoice)
                .where(Invoice.invoice_number == row.invoice_number)
                .order_by(Invoice.created_at)
            )
            invoices = group_result.scalars().all()
            duplicate_groups.append({
                "invoice_number": row.invoice_number,
                "count": row.count,
                "invoices": [inv.to_dict() for inv in invoices],
            })

        return duplicate_groups

    async def merge_duplicates(
        self, db: AsyncSession, keep_id: int, remove_ids: List[int]
    ) -> Dict[str, Any]:
        """
        合并重复发票（保留一个，删除其余）

        Args:
            db: 数据库会话
            keep_id: 保留的发票ID
            remove_ids: 要删除的发票ID列表

        Returns:
            Dict: 操作结果
        """
        removed = []
        for rid in remove_ids:
            if rid == keep_id:
                continue
            invoice = await db.execute(
                select(Invoice).where(Invoice.id == rid)
            )
            inv = invoice.scalar_one_or_none()
            if inv:
                await db.delete(inv)
                removed.append(rid)

        await db.commit()
        return {"kept": keep_id, "removed": removed, "count": len(removed)}


# 全局查重服务实例
duplicate_service = DuplicateService()

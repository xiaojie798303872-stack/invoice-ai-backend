# -*- coding: utf-8 -*-
"""
发票业务逻辑服务
封装发票的CRUD操作、分页查询、排序、筛选等功能
"""

import logging
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy import select, func, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from models import Invoice
from schemas import InvoiceCreate, InvoiceUpdate
from config import settings

logger = logging.getLogger(__name__)


class InvoiceService:
    """发票业务逻辑服务类"""

    async def get_invoice_by_id(
        self, db: AsyncSession, invoice_id: int
    ) -> Optional[Invoice]:
        """
        根据ID获取发票

        Args:
            db: 数据库会话
            invoice_id: 发票ID

        Returns:
            Optional[Invoice]: 发票对象，不存在返回None
        """
        result = await db.execute(
            select(Invoice).where(Invoice.id == invoice_id)
        )
        return result.scalar_one_or_none()

    async def get_invoice_list(
        self,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        invoice_type: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        """
        获取发票列表（支持分页、筛选、排序）

        Args:
            db: 数据库会话
            page: 页码（从1开始）
            page_size: 每页数量
            invoice_type: 按发票类型筛选
            category: 按分类筛选
            status: 按状态筛选
            keyword: 关键词搜索（发票号码/销方名称/购方名称）
            start_date: 起始日期
            end_date: 截止日期
            sort_by: 排序字段
            sort_order: 排序方向（asc/desc）

        Returns:
            Dict[str, Any]: 包含total, page, page_size, items的字典
        """
        # 限制分页参数范围
        page = max(1, page)
        page_size = min(max(1, page_size), settings.MAX_PAGE_SIZE)

        # 构建基础查询
        query: Select = select(Invoice)
        count_query: Select = select(func.count()).select_from(Invoice)

        # 应用筛选条件
        filters = self._build_filters(
            invoice_type=invoice_type,
            category=category,
            status=status,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
        )

        if filters is not None:
            query = query.where(filters)
            count_query = count_query.where(filters)

        # 应用排序
        query = self._apply_sort(query, sort_by, sort_order)

        # 查询总数
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # 应用分页
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # 执行查询
        result = await db.execute(query)
        invoices = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": invoices,
        }

    async def create_invoice(
        self, db: AsyncSession, invoice_data: InvoiceCreate
    ) -> Invoice:
        """
        创建发票记录

        Args:
            db: 数据库会话
            invoice_data: 发票创建数据

        Returns:
            Invoice: 创建的发票对象
        """
        invoice = Invoice(**invoice_data.model_dump(exclude_unset=True))
        db.add(invoice)
        await db.commit()
        await db.refresh(invoice)
        return invoice

    async def update_invoice(
        self, db: AsyncSession, invoice_id: int, invoice_data: InvoiceUpdate
    ) -> Optional[Invoice]:
        """
        更新发票信息

        Args:
            db: 数据库会话
            invoice_id: 发票ID
            invoice_data: 更新数据

        Returns:
            Optional[Invoice]: 更新后的发票对象，不存在返回None
        """
        invoice = await self.get_invoice_by_id(db, invoice_id)
        if not invoice:
            return None

        # 只更新非None字段
        update_data = invoice_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(invoice, field, value)

        await db.commit()
        await db.refresh(invoice)
        return invoice

    async def delete_invoice(
        self, db: AsyncSession, invoice_id: int
    ) -> bool:
        """
        删除发票

        Args:
            db: 数据库会话
            invoice_id: 发票ID

        Returns:
            bool: 是否删除成功
        """
        invoice = await self.get_invoice_by_id(db, invoice_id)
        if not invoice:
            return False

        await db.delete(invoice)
        await db.commit()
        return True

    async def batch_delete_invoices(
        self, db: AsyncSession, invoice_ids: List[int]
    ) -> Tuple[int, List[int]]:
        """
        批量删除发票

        Args:
            db: 数据库会话
            invoice_ids: 要删除的发票ID列表

        Returns:
            Tuple[int, List[int]]: (成功删除数量, 未找到的ID列表)
        """
        # 查询存在的ID
        result = await db.execute(
            select(Invoice.id).where(Invoice.id.in_(invoice_ids))
        )
        existing_ids = {row[0] for row in result.all()}

        # 计算未找到的ID
        not_found_ids = list(set(invoice_ids) - existing_ids)

        # 批量删除
        if existing_ids:
            await db.execute(
                delete(Invoice).where(Invoice.id.in_(existing_ids))
            )
            await db.commit()

        return len(existing_ids), not_found_ids

    async def get_stats_overview(self, db: AsyncSession) -> Dict[str, Any]:
        """
        获取统计总览

        Args:
            db: 数据库会话

        Returns:
            Dict[str, Any]: 统计总览数据
        """
        # 总数和总金额
        result = await db.execute(
            select(
                func.count(Invoice.id).label("total_count"),
                func.coalesce(func.sum(Invoice.total_amount), 0).label("total_amount"),
                func.coalesce(func.sum(Invoice.tax_amount), 0).label("total_tax"),
            )
        )
        row = result.one()
        overview = {
            "total_count": row.total_count,
            "total_amount": round(float(row.total_amount), 2),
            "total_tax": round(float(row.total_tax), 2),
        }

        # 按状态统计
        status_result = await db.execute(
            select(Invoice.status, func.count(Invoice.id))
            .group_by(Invoice.status)
        )
        status_counts = {row[0]: row[1] for row in status_result.all()}
        overview["pending_count"] = status_counts.get("pending", 0)
        overview["reviewed_count"] = status_counts.get("reviewed", 0)
        overview["exported_count"] = status_counts.get("exported", 0)

        # 按类型分布
        type_result = await db.execute(
            select(
                Invoice.invoice_type,
                func.count(Invoice.id),
                func.coalesce(func.sum(Invoice.total_amount), 0),
            )
            .group_by(Invoice.invoice_type)
        )
        overview["type_distribution"] = [
            {
                "type_name": row[0] or "未知",
                "count": row[1],
                "total_amount": round(float(row[2]), 2),
            }
            for row in type_result.all()
        ]

        # 按分类分布
        category_result = await db.execute(
            select(
                Invoice.category,
                func.count(Invoice.id),
                func.coalesce(func.sum(Invoice.total_amount), 0),
            )
            .group_by(Invoice.category)
        )
        overview["category_distribution"] = [
            {
                "category_name": row[0] or "未知",
                "count": row[1],
                "total_amount": round(float(row[2]), 2),
            }
            for row in category_result.all()
        ]

        return overview

    async def get_monthly_stats(
        self, db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """获取按月统计数据（兼容SQLite/PostgreSQL/MySQL）"""
        from sqlalchemy import case

        engine_type = settings.DB_ENGINE

        if engine_type == "postgresql":
            date_expr = func.to_char(Invoice.invoice_date, 'YYYY-MM')
        elif engine_type == "mysql":
            date_expr = func.date_format(Invoice.invoice_date, '%Y-%m')
        else:
            date_expr = func.substr(Invoice.invoice_date, 1, 7)

        result = await db.execute(
            select(
                date_expr.label("month"),
                func.count(Invoice.id).label("count"),
                func.coalesce(func.sum(Invoice.total_amount), 0).label("total_amount"),
            )
            .where(Invoice.invoice_date.isnot(None))
            .group_by(date_expr)
            .order_by(date_expr.desc())
        )

        return [
            {
                "month": str(row.month),
                "count": row.count,
                "total_amount": round(float(row.total_amount), 2),
            }
            for row in result.all()
        ]

    async def get_category_stats(
        self, db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        获取按分类统计数据

        Args:
            db: 数据库会话

        Returns:
            List[Dict[str, Any]]: 分类统计列表
        """
        result = await db.execute(
            select(
                Invoice.category,
                func.count(Invoice.id).label("count"),
                func.coalesce(func.sum(Invoice.total_amount), 0).label("total_amount"),
                func.coalesce(func.sum(Invoice.tax_amount), 0).label("total_tax"),
            )
            .group_by(Invoice.category)
            .order_by(func.count(Invoice.id).desc())
        )

        return [
            {
                "category_name": row[0] or "未知",
                "count": row[1],
                "total_amount": round(float(row.total_amount), 2),
                "total_tax": round(float(row.total_tax), 2),
            }
            for row in result.all()
        ]

    def _build_filters(
        self,
        invoice_type: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ):
        """
        构建筛选条件

        Args:
            invoice_type: 发票类型
            category: 分类
            status: 状态
            keyword: 关键词
            start_date: 起始日期
            end_date: 截止日期

        Returns:
            筛选条件表达式或None
        """
        conditions = []

        if invoice_type:
            conditions.append(Invoice.invoice_type == invoice_type)
        if category:
            conditions.append(Invoice.category == category)
        if status:
            conditions.append(Invoice.status == status)
        if start_date:
            conditions.append(Invoice.invoice_date >= start_date)
        if end_date:
            conditions.append(Invoice.invoice_date <= end_date)
        if keyword:
            keyword_pattern = f"%{keyword}%"
            conditions.append(
                or_(
                    Invoice.invoice_number.like(keyword_pattern),
                    Invoice.seller_name.like(keyword_pattern),
                    Invoice.buyer_name.like(keyword_pattern),
                    Invoice.invoice_code.like(keyword_pattern),
                )
            )

        if conditions:
            from sqlalchemy import and_
            return and_(*conditions)
        return None

    def _apply_sort(self, query: Select, sort_by: str, sort_order: str) -> Select:
        """
        应用排序

        Args:
            query: 查询对象
            sort_by: 排序字段名
            sort_order: 排序方向（asc/desc）

        Returns:
            Select: 添加了排序的查询对象
        """
        # 允许的排序字段映射
        sort_field_map = {
            "created_at": Invoice.created_at,
            "updated_at": Invoice.updated_at,
            "invoice_date": Invoice.invoice_date,
            "amount": Invoice.amount,
            "total_amount": Invoice.total_amount,
            "invoice_number": Invoice.invoice_number,
        }

        sort_field = sort_field_map.get(sort_by, Invoice.created_at)

        if sort_order.lower() == "asc":
            return query.order_by(sort_field.asc())
        else:
            return query.order_by(sort_field.desc())


# 全局服务实例
invoice_service = InvoiceService()

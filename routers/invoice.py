# -*- coding: utf-8 -*-
"""
发票相关API路由
提供发票的查询、更新、删除等接口
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from schemas import (
    InvoiceResponse, InvoiceUpdate, InvoiceListResponse,
    BatchDeleteRequest, ApiResponse,
)
from services.invoice_service import invoice_service
from services.duplicate_service import duplicate_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/invoices", tags=["发票管理"])


@router.get(
    "",
    response_model=InvoiceListResponse,
    summary="获取发票列表",
    description="支持分页、筛选、排序的发票列表查询",
)
async def get_invoices(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    invoice_type: Optional[str] = Query(None, description="发票类型筛选"),
    category: Optional[str] = Query(None, description="分类筛选"),
    status: Optional[str] = Query(None, description="状态筛选"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    start_date: Optional[str] = Query(None, description="起始日期"),
    end_date: Optional[str] = Query(None, description="截止日期"),
    sort_by: str = Query("created_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向: asc/desc"),
    db: AsyncSession = Depends(get_db),
):
    """获取发票列表"""
    try:
        result = await invoice_service.get_invoice_list(
            db=db,
            page=page,
            page_size=page_size,
            invoice_type=invoice_type,
            category=category,
            status=status,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        return InvoiceListResponse(
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
            items=result["items"],
        )
    except Exception as e:
        logger.error(f"获取发票列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取发票列表失败: {str(e)}")


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    summary="获取发票详情",
    description="根据ID获取单张发票的详细信息",
)
async def get_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取发票详情"""
    invoice = await invoice_service.get_invoice_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail=f"发票不存在 (ID: {invoice_id})")
    return invoice


@router.put(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    summary="更新发票信息",
    description="更新指定发票的字段信息",
)
async def update_invoice(
    invoice_id: int,
    invoice_data: InvoiceUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新发票信息"""
    try:
        updated = await invoice_service.update_invoice(
            db=db,
            invoice_id=invoice_id,
            invoice_data=invoice_data,
        )
        if not updated:
            raise HTTPException(status_code=404, detail=f"发票不存在 (ID: {invoice_id})")
        return updated
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新发票失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新发票失败: {str(e)}")


@router.delete(
    "/{invoice_id}",
    response_model=ApiResponse,
    summary="删除发票",
    description="根据ID删除单张发票",
)
async def delete_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除发票"""
    try:
        success = await invoice_service.delete_invoice(db, invoice_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"发票不存在 (ID: {invoice_id})")
        return ApiResponse(message="删除成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除发票失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除发票失败: {str(e)}")


@router.post(
    "/batch-delete",
    response_model=ApiResponse,
    summary="批量删除发票",
    description="根据ID列表批量删除多张发票",
)
async def batch_delete_invoices(
    request: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
):
    """批量删除发票"""
    try:
        deleted_count, not_found_ids = await invoice_service.batch_delete_invoices(
            db=db,
            invoice_ids=request.ids,
        )

        message = f"成功删除 {deleted_count} 条记录"
        if not_found_ids:
            message += f"，未找到的ID: {not_found_ids}"

        return ApiResponse(message=message)
    except Exception as e:
        logger.error(f"批量删除失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量删除失败: {str(e)}")


@router.get(
    "/check-duplicate",
    summary="检查发票是否重复",
    description="根据发票号码、代码、金额等检查是否已存在相同发票",
)
async def check_duplicate(
    invoice_number: str = Query(..., description="发票号码"),
    invoice_code: Optional[str] = Query(None, description="发票代码"),
    amount: Optional[float] = Query(None, description="金额"),
    invoice_date: Optional[str] = Query(None, description="开票日期"),
    exclude_id: Optional[int] = Query(None, description="排除的发票ID"),
    db: AsyncSession = Depends(get_db),
):
    """检查发票重复"""
    result = await duplicate_service.check_duplicate(
        db=db,
        invoice_number=invoice_number,
        invoice_code=invoice_code,
        amount=amount,
        invoice_date=invoice_date,
        exclude_id=exclude_id,
    )
    return result


@router.get(
    "/duplicates",
    summary="查找所有重复发票",
    description="查找系统中所有疑似重复的发票组",
)
async def find_duplicates(db: AsyncSession = Depends(get_db)):
    """查找所有重复发票"""
    duplicates = await duplicate_service.find_all_duplicates(db)
    return {"code": 200, "data": duplicates}


@router.post(
    "/merge-duplicates",
    summary="合并重复发票",
    description="保留指定发票，删除其余重复发票",
)
async def merge_duplicates(
    keep_id: int = Query(..., description="保留的发票ID"),
    remove_ids: List[int] = Query(..., description="要删除的发票ID列表"),
    db: AsyncSession = Depends(get_db),
):
    """合并重复发票"""
    result = await duplicate_service.merge_duplicates(db, keep_id, remove_ids)
    return {"code": 200, "message": f"已合并，删除 {result['count']} 条重复记录", "data": result}

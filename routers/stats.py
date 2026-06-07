# -*- coding: utf-8 -*-
"""
统计分析路由
提供发票数据的统计总览、月度统计、分类统计等接口
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from schemas import (
    StatsResponse, StatsOverview,
    TypeDistribution, CategoryDistribution,
    MonthlyStats, ExportRequest, PrintRequest,
)
from services.invoice_service import invoice_service
from services.export_service import export_service
from services.print_service import print_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stats", tags=["统计分析"])


@router.get(
    "/overview",
    response_model=StatsResponse,
    summary="统计总览",
    description="获取发票总数、总金额、按类型和分类的分布统计",
)
async def get_stats_overview(
    db: AsyncSession = Depends(get_db),
):
    """获取统计总览"""
    try:
        overview_data = await invoice_service.get_stats_overview(db)

        overview = StatsOverview(
            total_count=overview_data["total_count"],
            total_amount=overview_data["total_amount"],
            total_tax=overview_data["total_tax"],
            pending_count=overview_data["pending_count"],
            reviewed_count=overview_data["reviewed_count"],
            exported_count=overview_data["exported_count"],
            type_distribution=[
                TypeDistribution(**item)
                for item in overview_data["type_distribution"]
            ],
            category_distribution=[
                CategoryDistribution(**item)
                for item in overview_data["category_distribution"]
            ],
        )

        return StatsResponse(code=200, message="success", data=overview)
    except Exception as e:
        logger.error(f"获取统计总览失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取统计总览失败: {str(e)}")


@router.get(
    "/monthly",
    summary="按月统计",
    description="获取发票按月份的统计数据",
)
async def get_monthly_stats(
    db: AsyncSession = Depends(get_db),
):
    """获取按月统计"""
    try:
        monthly_data = await invoice_service.get_monthly_stats(db)

        return {
            "code": 200,
            "message": "success",
            "data": [
                MonthlyStats(**item) for item in monthly_data
            ],
        }
    except Exception as e:
        logger.error(f"获取月度统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取月度统计失败: {str(e)}")


@router.get(
    "/category",
    summary="按分类统计",
    description="获取发票按分类的统计数据",
)
async def get_category_stats(
    db: AsyncSession = Depends(get_db),
):
    """获取按分类统计"""
    try:
        category_data = await invoice_service.get_category_stats(db)

        return {
            "code": 200,
            "message": "success",
            "data": [
                CategoryDistribution(
                    category_name=item["category_name"],
                    count=item["count"],
                    total_amount=item["total_amount"],
                )
                for item in category_data
            ],
        }
    except Exception as e:
        logger.error(f"获取分类统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取分类统计失败: {str(e)}")


@router.post(
    "/export",
    summary="导出发票数据",
    description="将发票数据导出为Excel或PDF文件",
)
async def export_invoices(
    request: ExportRequest,
    db: AsyncSession = Depends(get_db),
):
    """导出发票数据"""
    try:
        # 获取待导出的发票
        invoices = await export_service.get_invoices_for_export(
            db=db,
            invoice_ids=request.invoice_ids,
            invoice_type=request.invoice_type,
            category=request.category,
            status=request.status,
            start_date=request.start_date,
            end_date=request.end_date,
        )

        if not invoices:
            raise HTTPException(status_code=404, detail="没有符合条件的数据可导出")

        # 根据格式导出
        if request.format == "pdf":
            output_path = await export_service.export_to_pdf(db, invoices)
        else:
            output_path = await export_service.export_to_excel(db, invoices)

        # 返回文件下载
        filename = output_path.split("/")[-1]
        return FileResponse(
            path=output_path,
            filename=filename,
            media_type="application/octet-stream",
        )

    except HTTPException:
        raise
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"导出依赖缺失: {str(e)}")
    except Exception as e:
        logger.error(f"导出发票失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导出发票失败: {str(e)}")


@router.post(
    "/print",
    summary="生成打印PDF",
    description="生成A5尺寸的可打印PDF文件，支持按日期排序和每页1~2张发票排版",
)
async def generate_print_pdf(
    request: PrintRequest,
    db: AsyncSession = Depends(get_db),
):
    """生成可打印的A5尺寸PDF"""
    try:
        output_path = await print_service.generate_print_pdf(
            db=db,
            invoice_ids=request.invoice_ids,
            invoices_per_page=request.invoices_per_page,
            sort_by_date=request.sort_by_date,
            start_date=request.start_date,
            end_date=request.end_date,
            invoice_type=request.invoice_type,
            category=request.category,
            status=request.status,
            title=request.title,
        )

        filename = os.path.basename(output_path)
        return FileResponse(
            path=output_path,
            filename=filename,
            media_type="application/pdf",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"生成打印PDF失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成打印PDF失败: {str(e)}")

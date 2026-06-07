# -*- coding: utf-8 -*-
"""
文件上传路由
提供发票图片上传和重新OCR识别的接口
"""

import os
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from config import settings
from schemas import InvoiceResponse, UploadResponse, ApiResponse
from services.invoice_service import invoice_service
from ocr.engine import ocr_engine
from ocr.classifier import invoice_classifier
from ocr.extractor import invoice_extractor
from utils.helpers import validate_file_type, generate_unique_filename

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/upload", tags=["文件上传"])


async def _process_uploaded_file(
    file: UploadFile,
    db: AsyncSession,
) -> dict:
    """
    处理单个上传文件：保存 -> OCR识别 -> 提取信息 -> 分类 -> 入库

    Args:
        file: 上传的文件对象
        db: 数据库会话

    Returns:
        dict: 处理结果
    """
    # 验证文件类型
    if not validate_file_type(file.filename or ""):
        return {
            "success": False,
            "error": f"不支持的文件类型，允许的类型: {settings.ALLOWED_FILE_TYPES}",
        }

    # 生成唯一文件名并保存
    unique_filename = generate_unique_filename(file.filename or "unknown.jpg")
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    try:
        # 确保上传目录存在
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

        # 保存文件
        import aiofiles
        async with aiofiles.open(file_path, "wb") as f:
            content = await file.read()
            await f.write(content)

        logger.info(f"文件已保存: {file_path}")

        # OCR识别
        ocr_result = ocr_engine.recognize(file_path)

        if not ocr_result["success"]:
            # OCR失败，仍然创建记录但标记为pending
            logger.warning(f"OCR识别失败: {ocr_result.get('error')}")
            from schemas import InvoiceCreate
            invoice = await invoice_service.create_invoice(db, InvoiceCreate(
                file_path=file_path,
                ocr_raw_text="",
                status="pending",
            ))
            return {"success": True, "invoice": invoice}

        ocr_text = ocr_result["full_text"]

        # 提取发票信息
        extracted_data = invoice_extractor.extract(ocr_text)

        # 识别发票类型
        invoice_type = invoice_classifier.classify_invoice_type(ocr_text)

        # 自动分类
        category = invoice_classifier.classify_with_jieba(ocr_text)

        # 创建发票记录
        from schemas import InvoiceCreate
        invoice_data = InvoiceCreate(
            file_path=file_path,
            ocr_raw_text=ocr_text,
            status="pending",
            invoice_type=invoice_type,
            category=category,
            **extracted_data,
        )
        invoice = await invoice_service.create_invoice(db, invoice_data)

        logger.info(
            f"发票处理完成: ID={invoice.id}, "
            f"类型={invoice_type}, 分类={category}, "
            f"号码={extracted_data.get('invoice_number', 'N/A')}"
        )

        return {"success": True, "invoice": invoice}

    except Exception as e:
        logger.error(f"处理上传文件失败: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


@router.post(
    "",
    response_model=UploadResponse,
    summary="上传发票图片",
    description="上传发票图片（支持多文件），自动进行OCR识别、信息提取和分类入库",
)
async def upload_invoices(
    files: List[UploadFile] = File(..., description="发票图片文件（支持多文件上传）"),
    db: AsyncSession = Depends(get_db),
):
    """
    上传发票图片
    支持同时上传多个文件，每个文件都会进行OCR识别并自动入库
    """
    if not files:
        raise HTTPException(status_code=400, detail="请上传至少一个文件")

    # 限制单次上传文件数量
    if len(files) > 20:
        raise HTTPException(
            status_code=400,
            detail=f"单次最多上传20个文件，当前上传了 {len(files)} 个",
        )

    results = []
    errors = []

    for file in files:
        result = await _process_uploaded_file(file, db)
        if result["success"]:
            results.append(result["invoice"])
        else:
            errors.append({
                "filename": file.filename,
                "error": result.get("error", "未知错误"),
            })

    message = f"成功处理 {len(results)} 个文件"
    if errors:
        message += f"，{len(errors)} 个文件处理失败"

    return UploadResponse(
        code=200 if results else 500,
        message=message,
        data=results,
    )


@router.post(
    "/re-ocr/{invoice_id}",
    response_model=InvoiceResponse,
    summary="重新识别发票",
    description="对已上传的发票图片重新进行OCR识别和 信息提取",
)
async def re_ocr_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    重新OCR识别指定发票
    使用原始上传的图片文件重新进行OCR识别，更新发票信息
    """
    # 查找发票
    invoice = await invoice_service.get_invoice_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail=f"发票不存在 (ID: {invoice_id})")

    if not invoice.file_path or not os.path.exists(invoice.file_path):
        raise HTTPException(
            status_code=400,
            detail="发票对应的文件不存在，无法重新识别",
        )

    try:
        # 重新OCR识别
        ocr_result = ocr_engine.recognize(invoice.file_path)

        if not ocr_result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"OCR重新识别失败: {ocr_result.get('error', '未知错误')}",
            )

        ocr_text = ocr_result["full_text"]

        # 重新提取信息
        extracted_data = invoice_extractor.extract(ocr_text)

        # 重新识别类型和分类
        invoice_type = invoice_classifier.classify_invoice_type(ocr_text)
        category = invoice_classifier.classify_with_jieba(ocr_text)

        # 更新发票记录
        from schemas import InvoiceUpdate
        update_data = InvoiceUpdate(
            ocr_raw_text=ocr_text,
            invoice_type=invoice_type,
            category=category,
            **extracted_data,
        )

        updated = await invoice_service.update_invoice(db, invoice_id, update_data)

        logger.info(f"发票重新识别完成: ID={invoice_id}")
        return updated

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重新识别发票失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"重新识别失败: {str(e)}")


from services.batch_service import batch_service


@router.post(
    "/batch-zip",
    summary="ZIP批量导入",
    description="上传ZIP压缩包，批量导入发票",
)
async def batch_import_zip(
    file: UploadFile = File(..., description="ZIP压缩包文件"),
    db: AsyncSession = Depends(get_db),
):
    """ZIP批量导入发票"""
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="请上传ZIP格式的压缩包")

    content = await file.read()
    if len(content) > 500 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="ZIP文件大小不能超过500MB")

    result = await batch_service.import_from_zip(content, db)

    return {
        "code": 200,
        "message": f"批量导入完成：成功{result['success']}，失败{result['failed']}，跳过{result['skipped']}",
        "data": result,
    }

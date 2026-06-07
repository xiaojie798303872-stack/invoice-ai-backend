# -*- coding: utf-8 -*-
"""
批量导入服务
支持ZIP压缩包批量上传和识别发票
"""

import os
import zipfile
import logging
import tempfile
import shutil
from typing import List, Dict, Any, Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from services.invoice_service import invoice_service
from ocr.engine import ocr_engine
from ocr.classifier import invoice_classifier
from ocr.extractor import invoice_extractor
from utils.helpers import validate_file_type, generate_unique_filename
from schemas import InvoiceCreate

logger = logging.getLogger(__name__)


class BatchImportService:
    """批量导入服务"""

    # ZIP中允许的图片文件扩展名
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".pdf"}

    # 单次批量导入的最大文件数
    MAX_FILES_PER_BATCH = 200

    async def import_from_zip(
        self,
        zip_bytes: bytes,
        db: AsyncSession,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        从ZIP压缩包批量导入发票

        Args:
            zip_bytes: ZIP文件的字节数据
            db: 数据库会话
            user_id: 操作用户ID

        Returns:
            Dict: 导入结果统计
        """
        result = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "errors": [],
            "invoices": [],
        }

        # 创建临时目录解压
        temp_dir = tempfile.mkdtemp(prefix="invoice_batch_")

        try:
            # 保存ZIP文件
            zip_path = os.path.join(temp_dir, "upload.zip")
            with open(zip_path, "wb") as f:
                f.write(zip_bytes)

            # 验证ZIP文件
            if not zipfile.is_zipfile(zip_path):
                return {**result, "errors": ["无效的ZIP文件"]}

            # 解压ZIP
            with zipfile.ZipFile(zip_path, "r") as zf:
                # 安全检查：防止ZIP炸弹
                total_size = sum(info.file_size for info in zf.infolist())
                max_zip_size = 500 * 1024 * 1024  # 500MB
                if total_size > max_zip_size:
                    return {**result, "errors": [f"ZIP文件总大小超过限制({max_zip_size // 1024 // 1024}MB)"]}

                file_list = [
                    info for info in zf.infolist()
                    if not info.is_dir()
                    and self._is_allowed_file(info.filename)
                ]

                if len(file_list) > self.MAX_FILES_PER_BATCH:
                    return {**result, "errors": [f"文件数量超过限制(最多{self.MAX_FILES_PER_BATCH}个)"]}

                result["total"] = len(file_list)

                for file_info in file_list:
                    filename = os.path.basename(file_info.filename)
                    try:
                        # 解压单个文件
                        extract_path = os.path.join(temp_dir, f"file_{result['success'] + result['failed']}")
                        zf.extract(file_info, extract_path)

                        # 找到解压后的实际文件
                        extracted_file = self._find_extracted_file(extract_path, file_info.filename)
                        if not extracted_file:
                            result["skipped"] += 1
                            continue

                        # 处理单个文件（OCR + 入库）
                        process_result = await self._process_single_file(
                            extracted_file, filename, db
                        )

                        if process_result["success"]:
                            result["success"] += 1
                            result["invoices"].append(process_result["invoice"])
                        else:
                            result["failed"] += 1
                            result["errors"].append({
                                "filename": filename,
                                "error": process_result.get("error", "未知错误"),
                            })

                    except Exception as e:
                        result["failed"] += 1
                        result["errors"].append({
                            "filename": filename,
                            "error": str(e),
                        })
                        logger.error(f"批量导入文件处理失败 {filename}: {e}")

            logger.info(
                f"批量导入完成: 总计{result['total']}, "
                f"成功{result['success']}, 失败{result['failed']}, 跳过{result['skipped']}"
            )

        except Exception as e:
            logger.error(f"批量导入异常: {e}", exc_info=True)
            result["errors"].append(f"批量导入异常: {str(e)}")

        finally:
            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)

        return result

    async def _process_single_file(
        self, file_path: str, filename: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """处理单个文件：OCR识别 -> 信息提取 -> 分类 -> 入库"""
        # 生成唯一文件名并保存到正式目录
        unique_filename = generate_unique_filename(filename)
        dest_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        shutil.copy2(file_path, dest_path)

        # OCR识别
        ocr_result = ocr_engine.recognize(dest_path)

        if not ocr_result["success"]:
            invoice = await invoice_service.create_invoice(db, InvoiceCreate(
                file_path=dest_path,
                ocr_raw_text="",
                status="pending",
            ))
            return {"success": True, "invoice": invoice}

        ocr_text = ocr_result["full_text"]

        # 提取发票信息
        extracted_data = invoice_extractor.extract(ocr_text)
        invoice_type = invoice_classifier.classify_invoice_type(ocr_text)
        category = invoice_classifier.classify_with_jieba(ocr_text)

        # 创建发票记录
        invoice_data = InvoiceCreate(
            file_path=dest_path,
            ocr_raw_text=ocr_text,
            status="pending",
            invoice_type=invoice_type,
            category=category,
            **extracted_data,
        )
        invoice = await invoice_service.create_invoice(db, invoice_data)

        return {"success": True, "invoice": invoice}

    def _is_allowed_file(self, filename: str) -> bool:
        """检查文件扩展名是否允许"""
        ext = os.path.splitext(filename)[1].lower()
        return ext in self.ALLOWED_EXTENSIONS

    def _find_extracted_file(self, extract_dir: str, original_path: str) -> Optional[str]:
        """在解压目录中找到实际文件"""
        # 直接查找
        parts = original_path.replace("\\", "/").split("/")
        target = parts[-1] if parts else ""

        for root, dirs, files in os.walk(extract_dir):
            for f in files:
                if f == target:
                    return os.path.join(root, f)

        # 如果找不到精确匹配，返回第一个文件
        for root, dirs, files in os.walk(extract_dir):
            if files:
                return os.path.join(root, files[0])

        return None


# 全局批量导入服务实例
batch_service = BatchImportService()

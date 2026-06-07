# -*- coding: utf-8 -*-
"""
云OCR集成模块
支持百度云和腾讯云发票专用OCR API
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from typing import Dict, Any, Optional
from datetime import datetime

import httpx

from config import settings

logger = logging.getLogger(__name__)


class CloudOCRProvider:
    """云OCR提供者基类"""

    async def recognize_invoice(self, image_path: str) -> Dict[str, Any]:
        """识别发票，返回统一格式的结果"""
        raise NotImplementedError

    async def recognize_invoice_from_bytes(self, image_bytes: bytes) -> Dict[str, Any]:
        """从字节数据识别发票"""
        raise NotImplementedError


class BaiduOCREngine(CloudOCRProvider):
    """
    百度云OCR引擎
    使用百度智能云的增值税发票识别API
    API文档: https://ai.baidu.com/ai-doc/OCR/zk3h7yx52
    """

    def __init__(self):
        self.api_key = settings.BAIDU_OCR_API_KEY
        self.secret_key = settings.BAIDU_OCR_SECRET_KEY
        self.vat_url = settings.BAIDU_OCR_VAT_INVOICE_URL
        self.general_url = settings.BAIDU_OCR_GENERAL_URL
        self._access_token = None
        self._token_expires = 0

    async def _get_access_token(self) -> str:
        """获取百度API的access_token（带缓存）"""
        # 如果token未过期，直接返回
        if self._access_token and time.time() < self._token_expires:
            return self._access_token

        # 请求新token
        token_url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(token_url, params=params)
            resp.raise_for_status()
            data = resp.json()

        self._access_token = data["access_token"]
        self._token_expires = time.time() + data.get("expires_in", 2592000) - 300  # 提前5分钟刷新
        logger.info("百度云OCR access_token获取成功")
        return self._access_token

    async def recognize_invoice(self, image_path: str) -> Dict[str, Any]:
        """使用百度云增值税发票API识别"""
        try:
            # 读取图片并base64编码
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            return await self._call_vat_api(image_data)
        except Exception as e:
            logger.error(f"百度云OCR识别失败: {e}", exc_info=True)
            return {"success": False, "error": f"百度云OCR识别失败: {str(e)}", "source": "baidu"}

    async def recognize_invoice_from_bytes(self, image_bytes: bytes) -> Dict[str, Any]:
        """从字节数据识别"""
        try:
            image_data = base64.b64encode(image_bytes).decode("utf-8")
            return await self._call_vat_api(image_data)
        except Exception as e:
            logger.error(f"百度云OCR识别失败: {e}", exc_info=True)
            return {"success": False, "error": f"百度云OCR识别失败: {str(e)}", "source": "baidu"}

    async def _call_vat_api(self, image_base64: str) -> Dict[str, Any]:
        """调用百度增值税发票识别API"""
        token = await self._get_access_token()

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {"image": image_base64, "pdf_file_size": "0"}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.vat_url}?access_token={token}",
                headers=headers,
                data=data,
            )
            resp.raise_for_status()
            result = resp.json()

        if "error_code" in result and result["error_code"] != 0:
            logger.warning(f"百度OCR返回错误: {result.get('error_msg', '未知错误')}")
            # 降级到通用OCR
            return await self._call_general_api(image_base64)

        return self._parse_vat_result(result)

    async def _call_general_api(self, image_base64: str) -> Dict[str, Any]:
        """降级调用百度通用文字识别API"""
        token = await self._get_access_token()

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {"image": image_base64, "language_type": "CHN_ENG"}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.general_url}?access_token={token}",
                headers=headers,
                data=data,
            )
            resp.raise_for_status()
            result = resp.json()

        # 从通用OCR结果中提取文本
        words_result = result.get("words_result", [])
        full_text = "\n".join([item.get("words", "") for item in words_result])

        return {
            "success": True,
            "full_text": full_text,
            "source": "baidu_general",
            "structured": {},  # 通用OCR不返回结构化数据
        }

    def _parse_vat_result(self, result: Dict) -> Dict[str, Any]:
        """解析百度增值税发票API返回的结构化数据"""
        words = result.get("words_result", [])

        # 将百度返回的字段映射到统一格式
        field_mapping = {
            "InvoiceNumber": "invoice_number",
            "InvoiceCode": "invoice_code",
            "InvoiceDate": "invoice_date",
            "InvoiceType": "invoice_type",
            "PurchaserName": "buyer_name",
            "PurchaserRegisterNum": "buyer_tax_number",
            "SellerName": "seller_name",
            "SellerRegisterNum": "seller_tax_number",
            "TotalAmount": "total_amount",
            "TotalTax": "tax_amount",
            "AmountInFiguers": "amount",
            "CheckCode": "check_code",
        }

        structured = {}
        full_text_parts = []

        for field_name, field_data in words.items():
            value = field_data.get("word", "") if isinstance(field_data, dict) else str(field_data)
            full_text_parts.append(f"{field_name}: {value}")

            mapped_key = field_mapping.get(field_name)
            if mapped_key:
                structured[mapped_key] = value

        # 处理金额字段（去除逗号）
        for amount_key in ["total_amount", "amount", "tax_amount"]:
            if amount_key in structured:
                try:
                    structured[amount_key] = float(str(structured[amount_key]).replace(",", "").replace("¥", "").replace("￥", ""))
                except (ValueError, TypeError):
                    pass

        return {
            "success": True,
            "full_text": "\n".join(full_text_parts),
            "structured": structured,
            "source": "baidu_vat",
        }


class TencentOCREngine(CloudOCRProvider):
    """
    腾讯云OCR引擎
    使用腾讯云的增值税发票识别API
    API文档: https://cloud.tencent.com/document/product/866/36213
    """

    def __init__(self):
        self.secret_id = settings.TENCENT_OCR_SECRET_ID
        self.secret_key = settings.TENCENT_OCR_SECRET_KEY
        self.region = settings.TENCENT_OCR_REGION
        self.endpoint = settings.TENCENT_OCR_VAT_INVOICE_URL

    def _sign(self, key: str, msg: str) -> bytes:
        """HMAC-SHA256签名"""
        return hmac.new(key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).digest()

    async def recognize_invoice(self, image_path: str) -> Dict[str, Any]:
        """使用腾讯云增值税发票API识别"""
        try:
            with open(image_path, "rb") as f:
                image_base64 = base64.b64encode(f.read()).decode("utf-8")

            return await self._call_vat_api(image_base64)
        except Exception as e:
            logger.error(f"腾讯云OCR识别失败: {e}", exc_info=True)
            return {"success": False, "error": f"腾讯云OCR识别失败: {str(e)}", "source": "tencent"}

    async def recognize_invoice_from_bytes(self, image_bytes: bytes) -> Dict[str, Any]:
        """从字节数据识别"""
        try:
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")
            return await self._call_vat_api(image_base64)
        except Exception as e:
            logger.error(f"腾讯云OCR识别失败: {e}", exc_info=True)
            return {"success": False, "error": f"腾讯云OCR识别失败: {str(e)}", "source": "tencent"}

    async def _call_vat_api(self, image_base64: str) -> Dict[str, Any]:
        """调用腾讯云增值税发票识别API"""
        import json

        timestamp = int(time.time())
        payload = {
            "ImageBase64": image_base64,
            "InvoiceType": "VAT_SPECIAL" if True else "VAT_GENERAL",
        }

        # 构建请求参数（简化版，实际生产环境应使用腾讯云SDK的签名方法）
        headers = {
            "Content-Type": "application/json",
            "Host": "ocr.tencentcloudapi.com",
            "X-TC-Action": "RecognizeVATInvoice",
            "X-TC-Version": "2018-11-19",
            "X-TC-Region": self.region,
            "X-TC-Timestamp": str(timestamp),
        }

        # 使用httpx直接调用
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self.endpoint,
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            result = resp.json()

        if "Response" in result and "Error" in result["Response"]:
            error = result["Response"]["Error"]
            logger.warning(f"腾讯云OCR返回错误: {error.get('Message', '未知错误')}")
            return {"success": False, "error": error.get("Message", "未知错误"), "source": "tencent"}

        return self._parse_vat_result(result.get("Response", {}))

    def _parse_vat_result(self, response: Dict) -> Dict[str, Any]:
        """解析腾讯云增值税发票API返回的结构化数据"""
        # 腾讯云返回的字段映射
        field_mapping = {
            "InvoiceNumber": "invoice_number",
            "InvoiceCode": "invoice_code",
            "InvoiceDate": "invoice_date",
            "Title": "invoice_type",
            "PurchaserName": "buyer_name",
            "PurchaserRegisterNum": "buyer_tax_number",
            "SellerName": "seller_name",
            "SellerRegisterNum": "seller_tax_number",
            "TotalAmount": "total_amount",
            "TotalTax": "tax_amount",
            "AmountInFiguers": "amount",
            "CheckCode": "check_code",
        }

        structured = {}
        full_text_parts = []

        for key, value in response.items():
            if isinstance(value, str):
                full_text_parts.append(f"{key}: {value}")
                mapped_key = field_mapping.get(key)
                if mapped_key:
                    structured[mapped_key] = value

        # 处理金额
        for amount_key in ["total_amount", "amount", "tax_amount"]:
            if amount_key in structured:
                try:
                    structured[amount_key] = float(str(structured[amount_key]).replace(",", ""))
                except (ValueError, TypeError):
                    pass

        return {
            "success": True,
            "full_text": "\n".join(full_text_parts),
            "structured": structured,
            "source": "tencent_vat",
        }


class CloudOCRFactory:
    """云OCR工厂类，根据配置创建对应的OCR引擎"""

    _engines: Dict[str, CloudOCRProvider] = {}

    @classmethod
    def get_engine(cls) -> CloudOCRProvider:
        """根据配置获取OCR引擎实例"""
        engine_type = settings.OCR_ENGINE

        if engine_type == "baidu":
            if "baidu" not in cls._engines:
                if not settings.BAIDU_OCR_API_KEY or not settings.BAIDU_OCR_SECRET_KEY:
                    logger.warning("百度云OCR未配置API密钥，将使用本地OCR")
                    from ocr.engine import ocr_engine as fallback
                    return fallback
                cls._engines["baidu"] = BaiduOCREngine()
            return cls._engines["baidu"]

        elif engine_type == "tencent":
            if "tencent" not in cls._engines:
                if not settings.TENCENT_OCR_SECRET_ID or not settings.TENCENT_OCR_SECRET_KEY:
                    logger.warning("腾讯云OCR未配置密钥，将使用本地OCR")
                    from ocr.engine import ocr_engine as fallback
                    return fallback
                cls._engines["tencent"] = TencentOCREngine()
            return cls._engines["tencent"]

        else:
            # 默认使用本地PaddleOCR
            from ocr.engine import ocr_engine
            return ocr_engine


# 全局云OCR实例（通过工厂获取）
cloud_ocr = CloudOCRFactory()

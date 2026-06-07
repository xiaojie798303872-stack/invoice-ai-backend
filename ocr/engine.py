# -*- coding: utf-8 -*-
"""
OCR引擎封装模块
支持多种OCR引擎：本地PaddleOCR / 百度云OCR / 腾讯云OCR
自动降级：PaddleOCR不可用时自动切换到云OCR
"""

import os
import base64
import logging
from typing import List, Dict, Any, Optional

from config import settings

logger = logging.getLogger(__name__)


class OCRResult:
    """OCR识别结果"""

    def __init__(self, text: str, confidence: float, position: List[List[int]]):
        self.text = text
        self.confidence = confidence
        self.position = position

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "position": self.position,
        }


class InvoiceOCR:
    """
    发票OCR识别引擎
    支持多种引擎，自动降级
    """

    def __init__(self):
        self._ocr = None
        self._initialized = False
        self._engine_type = None  # 'local' / 'baidu' / 'tencent'

    def _init_engine(self) -> None:
        """初始化OCR引擎，自动选择可用的引擎"""
        if self._initialized:
            return

        # 1. 尝试本地PaddleOCR
        try:
            from paddleocr import PaddleOCR
            logger.info("正在初始化PaddleOCR引擎...")
            self._ocr = PaddleOCR(
                use_angle_cls=True,
                lang=getattr(settings, "OCR_LANG", "ch"),
                use_gpu=getattr(settings, "OCR_USE_GPU", False),
                show_log=False,
            )
            self._initialized = True
            self._engine_type = "local"
            logger.info("PaddleOCR引擎初始化完成")
            return
        except ImportError:
            logger.warning("PaddleOCR未安装，尝试云OCR...")
        except Exception as e:
            logger.warning(f"PaddleOCR初始化失败({e})，尝试云OCR...")

        # 2. 尝试百度云OCR
        if getattr(settings, "BAIDU_OCR_API_KEY", "") and getattr(settings, "BAIDU_OCR_SECRET_KEY", ""):
            logger.info("使用百度云OCR引擎")
            self._engine_type = "baidu"
            self._initialized = True
            return

        # 3. 尝试腾讯云OCR
        if getattr(settings, "TENCENT_OCR_SECRET_ID", "") and getattr(settings, "TENCENT_OCR_SECRET_KEY", ""):
            logger.info("使用腾讯云OCR引擎")
            self._engine_type = "tencent"
            self._initialized = True
            return

        # 4. 都不可用，使用模拟模式（让上传功能不报错）
        logger.warning("所有OCR引擎都不可用，使用模拟模式（仅保存文件，不进行OCR识别）")
        self._engine_type = "mock"
        self._initialized = True

    def _recognize_with_baidu(self, image_path: str) -> Dict[str, Any]:
        """使用百度云OCR识别"""
        import httpx

        try:
            # 获取access_token
            token_url = "https://aip.baidubce.com/oauth/2.0/token"
            token_params = {
                "grant_type": "client_credentials",
                "client_id": settings.BAIDU_OCR_API_KEY,
                "client_secret": settings.BAIDU_OCR_SECRET_KEY,
            }

            with httpx.Client(timeout=30) as client:
                token_resp = client.post(token_url, params=token_params)
                token_data = token_resp.json()
                access_token = token_data.get("access_token")

                if not access_token:
                    return {"success": False, "error": f"百度云获取token失败: {token_data}"}

                # 调用增值税发票识别API
                with open(image_path, "rb") as f:
                    image_base64 = base64.b64encode(f.read()).decode("utf-8")

                # 先尝试增值税发票专用API
                vat_url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/vat_invoice?access_token={access_token}"
                headers = {"Content-Type": "application/x-www-form-urlencoded"}
                data = {"image": image_base64, "pdf_file_size": "0"}

                resp = client.post(vat_url, headers=headers, data=data)
                result = resp.json()

                if "error_code" not in result or result.get("error_code") == 0:
                    # 增值税发票识别成功
                    words = result.get("words_result", [])
                    text_lines = []
                    for key, val in words.items():
                        if isinstance(val, dict):
                            text_lines.append(f"{key}: {val.get('word', '')}")
                        else:
                            text_lines.append(f"{key}: {val}")

                    return {
                        "success": True,
                        "full_text": "\n".join(text_lines),
                        "results": [{"text": t, "confidence": 1.0, "position": []} for t in text_lines],
                        "structured": self._parse_baidu_vat_result(words),
                    }

                # 降级到通用文字识别
                general_url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic?access_token={access_token}"
                resp = client.post(general_url, headers=headers, data=data)
                result = resp.json()

                words_result = result.get("words_result", [])
                text_lines = [item.get("words", "") for item in words_result]

                return {
                    "success": True,
                    "full_text": "\n".join(text_lines),
                    "results": [{"text": t, "confidence": 1.0, "position": []} for t in text_lines],
                }

        except Exception as e:
            return {"success": False, "error": f"百度云OCR失败: {str(e)}"}

    def _parse_baidu_vat_result(self, words: dict) -> dict:
        """解析百度增值税发票结构化结果"""
        mapping = {
            "InvoiceNumber": "invoice_number",
            "InvoiceCode": "invoice_code",
            "InvoiceDate": "invoice_date",
            "PurchaserName": "buyer_name",
            "SellerName": "seller_name",
            "TotalAmount": "total_amount",
            "TotalTax": "tax_amount",
            "AmountInFiguers": "amount",
            "CheckCode": "check_code",
        }
        structured = {}
        for key, val in words.items():
            if isinstance(val, dict):
                mapped = mapping.get(key)
                if mapped:
                    structured[mapped] = val.get("word", "")
        return structured

    def _recognize_with_tencent(self, image_path: str) -> Dict[str, Any]:
        """使用腾讯云OCR识别"""
        import httpx

        try:
            with open(image_path, "rb") as f:
                image_base64 = base64.b64encode(f.read()).decode("utf-8")

            payload = {
                "ImageBase64": image_base64,
            }
            headers = {
                "Content-Type": "application/json",
                "Host": "ocr.tencentcloudapi.com",
                "X-TC-Action": "RecognizeVATInvoice",
                "X-TC-Version": "2018-11-19",
                "X-TC-Region": getattr(settings, "TENCENT_OCR_REGION", "ap-guangzhou"),
                "X-TC-Timestamp": str(int(__import__('time').time())),
            }

            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    "https://ocr.tencentcloudapi.com",
                    json=payload,
                    headers=headers,
                )
                result = resp.json()

            if "Response" in result:
                response = result["Response"]
                if "Error" not in response:
                    text_parts = [f"{k}: {v}" for k, v in response.items() if isinstance(v, str)]
                    return {
                        "success": True,
                        "full_text": "\n".join(text_parts),
                        "results": [{"text": t, "confidence": 1.0, "position": []} for t in text_parts],
                    }
                else:
                    return {"success": False, "error": response["Error"].get("Message", "未知错误")}

            return {"success": False, "error": "腾讯云OCR返回异常"}

        except Exception as e:
            return {"success": False, "error": f"腾讯云OCR失败: {str(e)}"}

    def recognize(self, image_path: str) -> Dict[str, Any]:
        """
        识别发票图片中的文字（自动选择引擎）
        """
        result = {
            "full_text": "",
            "results": [],
            "success": False,
            "error": None,
            "structured": {},
        }

        try:
            self._init_engine()

            if self._engine_type == "local":
                # 使用PaddleOCR
                ocr_results = self._ocr.ocr(image_path, cls=True)

                if not ocr_results or not ocr_results[0]:
                    result["error"] = "未识别到任何文字"
                    return result

                text_lines = []
                parsed_results = []

                for line in ocr_results[0]:
                    position = line[0]
                    text = line[1][0]
                    confidence = line[1][1]

                    if confidence >= settings.OCR_CONFIDENCE_THRESHOLD:
                        text_lines.append(text)
                        parsed_results.append({
                            "text": text,
                            "confidence": round(confidence, 4),
                            "position": [[int(p[0]), int(p[1])] for p in position],
                        })

                result["full_text"] = "\n".join(text_lines)
                result["results"] = parsed_results
                result["success"] = True

            elif self._engine_type == "baidu":
                baidu_result = self._recognize_with_baidu(image_path)
                if baidu_result["success"]:
                    result["full_text"] = baidu_result["full_text"]
                    result["results"] = baidu_result.get("results", [])
                    result["success"] = True
                    result["structured"] = baidu_result.get("structured", {})
                else:
                    result["error"] = baidu_result.get("error", "百度云OCR失败")

            elif self._engine_type == "tencent":
                tencent_result = self._recognize_with_tencent(image_path)
                if tencent_result["success"]:
                    result["full_text"] = tencent_result["full_text"]
                    result["results"] = tencent_result.get("results", [])
                    result["success"] = True
                else:
                    result["error"] = tencent_result.get("error", "腾讯云OCR失败")

            elif self._engine_type == "mock":
                # 模拟模式：不进行OCR，返回成功但文本为空
                result["success"] = True
                result["full_text"] = ""
                result["results"] = []
                result["error"] = None
                logger.info("模拟模式：文件已保存，跳过OCR识别")

        except FileNotFoundError:
            result["error"] = f"图片文件不存在: {image_path}"
            logger.error(result["error"])
        except Exception as e:
            result["error"] = f"OCR识别失败: {str(e)}"
            logger.error(result["error"], exc_info=True)

        return result

    def recognize_from_bytes(self, image_bytes: bytes) -> Dict[str, Any]:
        """从字节数据识别"""
        # 保存到临时文件再识别
        import tempfile
        suffix = ".jpg"
        fd, path = tempfile.mkstemp(suffix=suffix)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(image_bytes)
            return self.recognize(path)
        finally:
            if os.path.exists(path):
                os.remove(path)


# 全局OCR引擎实例（单例模式）
ocr_engine = InvoiceOCR()

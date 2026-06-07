# -*- coding: utf-8 -*-
"""
发票信息提取器模块
使用正则表达式从OCR文本中提取发票各字段的结构化数据
"""

import re
import logging
from typing import Dict, Any, Optional

from utils.helpers import format_date, format_amount, clean_text

logger = logging.getLogger(__name__)


class InvoiceExtractor:
    """
    发票信息提取器
    从OCR识别的原始文本中，通过正则表达式提取发票各关键字段
    """

    def extract(self, ocr_text: str) -> Dict[str, Any]:
        """
        从OCR文本中提取发票结构化信息

        Args:
            ocr_text: OCR识别的完整文本

        Returns:
            Dict[str, Any]: 提取的发票字段字典，包含以下字段:
                - invoice_number: 发票号码
                - invoice_code: 发票代码
                - invoice_type: 发票类型
                - invoice_date: 开票日期
                - amount: 金额
                - tax_amount: 税额
                - total_amount: 价税合计
                - seller_name: 销方名称
                - seller_tax_number: 销方税号
                - buyer_name: 购方名称
                - buyer_tax_number: 购方税号
                - check_code: 校验码
        """
        if not ocr_text:
            return {}

        # 清理文本
        text = clean_text(ocr_text)

        result: Dict[str, Any] = {}

        # 依次提取各字段
        result["invoice_number"] = self._extract_invoice_number(text)
        result["invoice_code"] = self._extract_invoice_code(text)
        result["invoice_date"] = self._extract_invoice_date(text)
        result["amount"] = self._extract_amount(text)
        result["tax_amount"] = self._extract_tax_amount(text)
        result["total_amount"] = self._extract_total_amount(text)
        result["seller_name"] = self._extract_seller_name(text)
        result["seller_tax_number"] = self._extract_seller_tax_number(text)
        result["buyer_name"] = self._extract_buyer_name(text)
        result["buyer_tax_number"] = self._extract_buyer_tax_number(text)
        result["check_code"] = self._extract_check_code(text)

        # 过滤掉None值
        result = {k: v for k, v in result.items() if v is not None}

        logger.info(f"发票信息提取完成，提取到 {len(result)} 个字段")
        return result

    def _extract_invoice_number(self, text: str) -> Optional[str]:
        """提取发票号码"""
        patterns = [
            r"(?:发票号码|No|号码)[：:\s]*(\d{8,20})",
            r"(\d{8,20})",
        ]
        return self._match_first(patterns, text)

    def _extract_invoice_code(self, text: str) -> Optional[str]:
        """提取发票代码"""
        patterns = [
            r"(?:发票代码|代码)[：:\s]*(\d{10,12})",
        ]
        return self._match_first(patterns, text)

    def _extract_invoice_date(self, text: str) -> Optional[str]:
        """提取开票日期"""
        patterns = [
            r"(?:开票日期|日期|开票时间)[：:\s]*(\d{4}年\d{1,2}月\d{1,2}日)",
            r"(?:开票日期|日期|开票时间)[：:\s]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})",
            r"(\d{4}年\d{1,2}月\d{1,2}日)",
            r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})",
        ]
        match = self._match_first(patterns, text)
        if match:
            return format_date(match)
        return None

    def _extract_amount(self, text: str) -> Optional[float]:
        """提取金额（不含税）"""
        patterns = [
            r"(?:金额|不含税金额|合计)[：:\s]*[¥￥]?\s*(\d+[\.,]?\d*)",
            r"(?:金额)[：:\s]*(\d+[\.,]?\d*)",
        ]
        match = self._match_first(patterns, text)
        if match:
            return format_amount(match)
        return None

    def _extract_tax_amount(self, text: str) -> Optional[float]:
        """提取税额"""
        patterns = [
            r"(?:税额|税率|税)[：:\s]*[¥￥]?\s*(\d+[\.,]?\d*)",
        ]
        match = self._match_first(patterns, text)
        if match:
            return format_amount(match)
        return None

    def _extract_total_amount(self, text: str) -> Optional[float]:
        """提取价税合计"""
        patterns = [
            r"(?:价税合计|合计金额|总金额|总计)[（(]大写[)）]?[：:\s]*[¥￥]?\s*(\d+[\.,]?\d*)",
            r"(?:价税合计|合计金额|总金额|总计)[：:\s]*[¥￥]?\s*(\d+[\.,]?\d*)",
            r"(?:价税合计|合计金额|总金额|总计)[（(]小写[)）]?[：:\s]*[¥￥]?\s*(\d+[\.,]?\d*)",
        ]
        match = self._match_first(patterns, text)
        if match:
            return format_amount(match)
        return None

    def _extract_seller_name(self, text: str) -> Optional[str]:
        """提取销方名称"""
        patterns = [
            r"(?:销方名称|销售方名称|卖方|收款方)[：:\s]*([^\n\s]{2,50})",
            r"(?:名称)[：:\s]*([^\n\s]{2,50})(?:\s*(?:纳税人|税号))",
        ]
        return self._match_first(patterns, text)

    def _extract_seller_tax_number(self, text: str) -> Optional[str]:
        """提取销方税号"""
        patterns = [
            r"(?:销方[纳税人识别号|税号|识别号])[：:\s]*([A-Z0-9]{15,20})",
            r"(?:纳税人识别号)[：:\s]*([A-Z0-9]{15,20})",
        ]
        return self._match_first(patterns, text)

    def _extract_buyer_name(self, text: str) -> Optional[str]:
        """提取购方名称"""
        patterns = [
            r"(?:购方名称|购买方名称|买方|付款方)[：:\s]*([^\n\s]{2,50})",
        ]
        return self._match_first(patterns, text)

    def _extract_buyer_tax_number(self, text: str) -> Optional[str]:
        """提取购方税号"""
        patterns = [
            r"(?:购方[纳税人识别号|税号|识别号])[：:\s]*([A-Z0-9]{15,20})",
        ]
        return self._match_first(patterns, text)

    def _extract_check_code(self, text: str) -> Optional[str]:
        """提取校验码"""
        patterns = [
            r"(?:校验码|密码区|密码)[：:\s]*([A-Za-z0-9]{4,30})",
        ]
        return self._match_first(patterns, text)

    def _match_first(self, patterns: list, text: str) -> Optional[str]:
        """
        尝试用多个正则模式匹配文本，返回第一个匹配结果

        Args:
            patterns: 正则表达式列表
            text: 待匹配文本

        Returns:
            Optional[str]: 第一个匹配到的结果，无匹配返回None
        """
        for pattern in patterns:
            try:
                match = re.search(pattern, text)
                if match:
                    return match.group(1).strip()
            except re.error:
                continue
        return None


# 全局提取器实例
invoice_extractor = InvoiceExtractor()

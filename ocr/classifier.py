# -*- coding: utf-8 -*-
"""
发票分类器模块
基于关键词匹配对发票进行自动分类
"""

import re
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class InvoiceClassifier:
    """
    发票自动分类器
    根据OCR识别文本中的关键词，将发票自动归类到对应分类
    """

    # 分类关键词映射表
    CATEGORY_KEYWORDS: Dict[str, List[str]] = {
        "餐饮": [
            "餐饮", "食品", "饭店", "酒店", "餐厅", "食堂", "外卖",
            "小吃", "饮品", "咖啡", "茶", "火锅", "烧烤", "快餐",
            "美食", "菜", "饭", "面", "酒", "饮料", "蛋糕", "甜品",
            "肯德基", "麦当劳", "星巴克", "海底捞", "美团", "饿了么",
            "食品加工", "农副产品", "粮油", "肉类", "蔬菜", "水果",
        ],
        "交通": [
            "火车", "铁路", "高铁", "动车", "机票", "航空", "飞机",
            "客运", "公交", "地铁", "出租车", "网约车", "滴滴",
            "加油", "石油", "石化", "高速", "过路费", "停车",
            "汽车", "车辆", "运输", "物流", "快递", "邮政",
            "船票", "船运", "港口",
        ],
        "办公": [
            "办公", "文具", "打印", "复印", "纸张", "耗材",
            "电脑", "电子", "设备", "器材", "软件", "技术服务",
            "咨询", "服务费", "广告", "设计", "印刷", "包装",
            "通讯", "电信", "联通", "移动", "网络", "宽带",
            "维修", "维护", "租赁", "物业", "保洁",
        ],
        "住宿": [
            "住宿", "宾馆", "旅馆", "旅店", "民宿", "公寓",
            "会议", "培训", "场地", "会展",
        ],
    }

    # 发票类型关键词映射
    INVOICE_TYPE_KEYWORDS: Dict[str, List[str]] = {
        "增值税专票": [
            "增值税专用发票", "专用发票",
        ],
        "增值税普票": [
            "增值税普通发票", "普通发票",
        ],
        "电子发票": [
            "电子发票", "增值税电子普通发票", "增值税电子专用发票",
        ],
        "火车票": [
            "火车票", "铁路客运", "车票",
        ],
        "机票": [
            "机票", "航空运输", "客票", "行程单",
        ],
    }

    def classify(self, ocr_text: str) -> str:
        """
        根据OCR文本对发票进行自动分类

        Args:
            ocr_text: OCR识别的完整文本

        Returns:
            str: 分类名称（餐饮/交通/办公/住宿/其他）
        """
        if not ocr_text:
            return "其他"

        # 统计各分类的匹配分数
        scores: Dict[str, int] = {}
        text = ocr_text.lower()

        for category, keywords in self.CATEGORY_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                # 计算关键词在文本中出现的次数
                count = len(re.findall(keyword, text))
                score += count
            if score > 0:
                scores[category] = score

        # 返回得分最高的分类
        if scores:
            best_category = max(scores, key=scores.get)
            logger.debug(f"分类结果: {best_category} (得分: {scores[best_category]})")
            return best_category

        return "其他"

    def classify_invoice_type(self, ocr_text: str) -> Optional[str]:
        """
        根据OCR文本识别发票类型

        Args:
            ocr_text: OCR识别的完整文本

        Returns:
            Optional[str]: 发票类型名称，无法识别返回None
        """
        if not ocr_text:
            return None

        text = ocr_text.lower()

        for invoice_type, keywords in self.INVOICE_TYPE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    logger.debug(f"识别发票类型: {invoice_type}")
                    return invoice_type

        # 默认根据文本特征判断
        if "发票" in text:
            return "增值税普票"

        return None

    def classify_with_jieba(self, ocr_text: str) -> str:
        """
        使用jieba分词进行辅助分类（增强分类准确度）

        Args:
            ocr_text: OCR识别的完整文本

        Returns:
            str: 分类名称
        """
        try:
            import jieba

            words = jieba.lcut(ocr_text)
            word_set = set(words)

            scores: Dict[str, int] = {}
            for category, keywords in self.CATEGORY_KEYWORDS.items():
                score = 0
                for keyword in keywords:
                    if keyword in word_set:
                        score += 2  # 精确匹配权重更高
                    elif any(keyword in w for w in words):
                        score += 1
                if score > 0:
                    scores[category] = score

            if scores:
                return max(scores, key=scores.get)

        except ImportError:
            logger.warning("jieba未安装，使用基础关键词匹配")
        except Exception as e:
            logger.warning(f"jieba分词分类失败: {e}")

        # 降级到基础分类
        return self.classify(ocr_text)


# 全局分类器实例
invoice_classifier = InvoiceClassifier()

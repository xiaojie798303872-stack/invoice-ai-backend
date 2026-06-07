# -*- coding: utf-8 -*-
"""
发票打印排版服务
支持A5尺寸PDF输出，每页1~2张发票，按日期排序
"""

import os
import io
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from models import Invoice
from config import settings

logger = logging.getLogger(__name__)


class PrintService:
    """发票打印排版服务"""

    # A5尺寸（毫米）
    A5_WIDTH_MM = 148.0
    A5_HEIGHT_MM = 210.0

    # A5尺寸（点，1mm ≈ 2.835点）
    A5_WIDTH_PT = A5_WIDTH_MM * 2.835
    A5_HEIGHT_PT = A5_HEIGHT_MM * 2.835

    # 页面边距（点）
    MARGIN = 25

    # 每页发票数量
    INVOICES_PER_PAGE_OPTIONS = [1, 2]

    async def generate_print_pdf(
        self,
        db: AsyncSession,
        invoice_ids: Optional[List[int]] = None,
        invoices_per_page: int = 2,
        sort_by_date: str = "asc",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        invoice_type: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        output_path: Optional[str] = None,
        title: Optional[str] = None,
    ) -> str:
        """
        生成可打印的A5尺寸PDF

        Args:
            db: 数据库会话
            invoice_ids: 指定发票ID列表
            invoices_per_page: 每页发票数量（1或2）
            sort_by_date: 按日期排序方向 asc/desc
            start_date: 起始日期筛选
            end_date: 截止日期筛选
            invoice_type: 发票类型筛选
            category: 分类筛选
            status: 状态筛选
            output_path: 输出文件路径
            title: 文档标题

        Returns:
            str: 生成的PDF文件路径
        """
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A5
            from reportlab.lib.units import mm, cm
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph,
                Spacer, Image, PageBreak, KeepTogether, Frame, PageTemplate
            )
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        except ImportError:
            raise ImportError("reportlab未安装，请执行: pip install reportlab")

        # 获取发票数据
        invoices = await self._get_invoices_for_print(
            db, invoice_ids, sort_by_date, start_date, end_date,
            invoice_type, category, status,
        )

        if not invoices:
            raise ValueError("没有符合条件的发票可打印")

        # 生成输出路径
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
            output_path = os.path.join(
                settings.UPLOAD_DIR, f"print_{timestamp}.pdf"
            )

        # 注册中文字体
        chinese_font = self._register_chinese_font()

        # 创建PDF文档（A5尺寸）
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A5,
            leftMargin=15 * mm,
            rightMargin=15 * mm,
            topMargin=12 * mm,
            bottomMargin=12 * mm,
            title=title or "发票打印",
            author="发票AI管理系统",
        )

        # 准备样式
        styles = self._create_styles(chinese_font)

        # 构建PDF内容
        elements = []

        # 添加文档标题（仅首页）
        doc_title = title or f"发票打印 - {datetime.now().strftime('%Y年%m月%d日')}"
        title_para = Paragraph(doc_title, styles["doc_title"])
        elements.append(title_para)
        elements.append(Spacer(1, 3 * mm))

        # 添加统计信息
        total_amount = sum(inv.total_amount or 0 for inv in invoices)
        stats_text = f"共 {len(invoices)} 张发票，合计金额：¥{total_amount:,.2f}"
        stats_para = Paragraph(stats_text, styles["stats_text"])
        elements.append(stats_para)
        elements.append(Spacer(1, 5 * mm))

        # 分页排版发票
        page_invoices = []
        for i, invoice in enumerate(invoices):
            page_invoices.append(invoice)

            if len(page_invoices) == invoices_per_page or i == len(invoices) - 1:
                # 生成当前页的发票内容
                page_elements = self._render_invoice_page(
                    page_invoices, styles, chinese_font, invoices_per_page
                )
                elements.extend(page_elements)

                # 如果不是最后一页，添加分页符
                if i < len(invoices) - 1:
                    elements.append(PageBreak())

                page_invoices = []

        # 添加页脚
        def add_page_number(canvas, doc):
            """添加页码"""
            canvas.saveState()
            page_num = canvas.getPageNumber()
            text = f"第 {page_num} 页 / 共 {doc.page} 页"
            canvas.setFont(chinese_font, 7)
            canvas.drawCentredString(A5[0] / 2, 8 * mm, text)
            # 添加打印日期
            date_text = f"打印时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"
            canvas.drawRightString(A5[0] - 15 * mm, 8 * mm, date_text)
            canvas.restoreState()

        # 构建PDF
        doc.build(elements, onFirstPage=add_page_number, onLaterPages=add_page_number)

        logger.info(
            f"打印PDF生成完成: {output_path}，"
            f"共 {len(invoices)} 张发票，每页 {invoices_per_page} 张"
        )

        return output_path

    async def _get_invoices_for_print(
        self,
        db: AsyncSession,
        invoice_ids: Optional[List[int]] = None,
        sort_by_date: str = "asc",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        invoice_type: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Invoice]:
        """获取待打印的发票列表"""
        query = select(Invoice).where(Invoice.status.isnot(None))

        if invoice_ids:
            query = query.where(Invoice.id.in_(invoice_ids))
        if start_date:
            query = query.where(Invoice.invoice_date >= start_date)
        if end_date:
            query = query.where(Invoice.invoice_date <= end_date)
        if invoice_type:
            query = query.where(Invoice.invoice_type == invoice_type)
        if category:
            query = query.where(Invoice.category == category)
        if status:
            query = query.where(Invoice.status == status)

        # 按开票日期排序
        if sort_by_date == "asc":
            query = query.order_by(Invoice.invoice_date.asc())
        else:
            query = query.order_by(Invoice.invoice_date.desc())

        result = await db.execute(query)
        return list(result.scalars().all())

    def _register_chinese_font(self) -> str:
        """注册中文字体"""
        try:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont

            font_paths = [
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/STHeiti Light.ttc",
                "C:/Windows/Fonts/simhei.ttf",
                "C:/Windows/Fonts/msyh.ttc",
                "C:/Windows/Fonts/simsun.ttc",
            ]

            for fp in font_paths:
                if os.path.exists(fp):
                    pdfmetrics.registerFont(TTFont("ChineseFont", fp))
                    logger.info(f"注册中文字体: {fp}")
                    return "ChineseFont"

            logger.warning("未找到中文字体，使用Helvetica（中文可能无法显示）")
            return "Helvetica"
        except Exception as e:
            logger.warning(f"注册中文字体失败: {e}")
            return "Helvetica"

    def _create_styles(self, font: str) -> Dict:
        """创建PDF样式"""
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.colors import HexColor

        styles = {}

        styles["doc_title"] = ParagraphStyle(
            "DocTitle",
            fontName=font,
            fontSize=12,
            leading=16,
            alignment=TA_CENTER,
            textColor=HexColor("#333333"),
            spaceAfter=2,
        )

        styles["stats_text"] = ParagraphStyle(
            "StatsText",
            fontName=font,
            fontSize=8,
            leading=12,
            alignment=TA_CENTER,
            textColor=HexColor("#666666"),
        )

        styles["invoice_title"] = ParagraphStyle(
            "InvoiceTitle",
            fontName=font,
            fontSize=9,
            leading=13,
            alignment=TA_LEFT,
            textColor=HexColor("#1a73e8"),
            spaceAfter=3,
        )

        styles["field_label"] = ParagraphStyle(
            "FieldLabel",
            fontName=font,
            fontSize=7,
            leading=10,
            textColor=HexColor("#888888"),
        )

        styles["field_value"] = ParagraphStyle(
            "FieldValue",
            fontName=font,
            fontSize=7,
            leading=10,
            textColor=HexColor("#333333"),
        )

        styles["amount_large"] = ParagraphStyle(
            "AmountLarge",
            fontName=font,
            fontSize=14,
            leading=18,
            alignment=TA_CENTER,
            textColor=HexColor("#d32f2f"),
            spaceBefore=2,
            spaceAfter=2,
        )

        styles["category_tag"] = ParagraphStyle(
            "CategoryTag",
            fontName=font,
            fontSize=6,
            leading=8,
            alignment=TA_CENTER,
            textColor=colors.white,
        )

        styles["separator"] = ParagraphStyle(
            "Separator",
            fontName=font,
            fontSize=1,
            leading=2,
        )

        return styles

    def _render_invoice_page(
        self,
        invoices: List[Invoice],
        styles: Dict,
        font: str,
        invoices_per_page: int,
    ) -> List:
        """渲染一页的发票内容"""
        from reportlab.platypus import (
            Table, TableStyle, Paragraph, Spacer, KeepTogether
        )
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.lib.colors import HexColor

        elements = []

        for idx, invoice in enumerate(invoices):
            if idx > 0 and invoices_per_page > 1:
                # 多发票时添加分隔线
                elements.append(Spacer(1, 3 * mm))

            # 发票标题行
            type_label = invoice.invoice_type or "发票"
            number_label = invoice.invoice_number or ""
            title_text = f"【{type_label}】 {number_label}"
            title_para = Paragraph(title_text, styles["invoice_title"])
            elements.append(title_para)

            # 构建发票信息表格
            table_data = self._build_invoice_table_data(invoice, styles)

            # 计算列宽（A5宽度减去边距）
            available_width = self.A5_WIDTH_PT - 2 * self.MARGIN
            col_widths = [available_width * 0.3, available_width * 0.7]

            table = Table(table_data, colWidths=col_widths)

            # 设置表格样式
            table_style_commands = [
                # 全局样式
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                # 标签列样式
                ("BACKGROUND", (0, 0), (0, -1), HexColor("#f5f5f5")),
                # 网格线
                ("GRID", (0, 0), (-1, -1), 0.3, HexColor("#e0e0e0")),
                # 金额行特殊样式
                ("BACKGROUND", (0, -1), (-1, -1), HexColor("#fff8e1")),
                ("SPAN", (0, -1), (0, -1)),
            ]

            table.setStyle(TableStyle(table_style_commands))
            elements.append(table)

            # 金额突出显示
            if invoice.total_amount:
                amount_text = f"¥ {invoice.total_amount:,.2f}"
                amount_para = Paragraph(amount_text, styles["amount_large"])
                elements.append(Spacer(1, 2 * mm))
                elements.append(amount_para)

            # 分类和状态标签
            tags = []
            if invoice.category:
                tags.append(invoice.category)
            if invoice.status:
                status_map = {"pending": "待审核", "reviewed": "已审核", "exported": "已导出"}
                tags.append(status_map.get(invoice.status, invoice.status))

            if tags:
                tag_text = " | ".join(tags)
                tag_para = Paragraph(
                    f"<font color='#666666' size='6'>{tag_text}</font>",
                    styles["category_tag"],
                )
                elements.append(Spacer(1, 1 * mm))
                elements.append(tag_para)

        return elements

    def _build_invoice_table_data(self, invoice: Invoice, styles: Dict) -> List[List]:
        """构建发票信息表格数据"""
        from reportlab.platypus import Paragraph

        rows = []

        fields = [
            ("发票号码", invoice.invoice_number or "-"),
            ("发票代码", invoice.invoice_code or "-"),
            ("开票日期", invoice.invoice_date or "-"),
            ("发票类型", invoice.invoice_type or "-"),
            ("金    额", f"¥{invoice.amount:,.2f}" if invoice.amount else "-"),
            ("税    额", f"¥{invoice.tax_amount:,.2f}" if invoice.tax_amount else "-"),
            ("价税合计", f"¥{invoice.total_amount:,.2f}" if invoice.total_amount else "-"),
            ("销方名称", (invoice.seller_name or "-")[:25]),
            ("购方名称", (invoice.buyer_name or "-")[:25]),
        ]

        for label, value in fields:
            label_para = Paragraph(
                f"<font size='7' color='#666666'>{label}</font>",
                styles["field_label"],
            )
            value_para = Paragraph(
                f"<font size='7'>{value}</font>",
                styles["field_value"],
            )
            rows.append([label_para, value_para])

        return rows


# 全局打印服务实例
print_service = PrintService()

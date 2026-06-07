# -*- coding: utf-8 -*-
"""
Pydantic数据模型
用于API请求/响应的数据验证与序列化
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ==================== 发票相关Schema ====================

class InvoiceCreate(BaseModel):
    """创建发票（手动创建，非OCR场景）"""
    invoice_number: Optional[str] = Field(None, max_length=50, description="发票号码")
    invoice_code: Optional[str] = Field(None, max_length=50, description="发票代码")
    invoice_type: Optional[str] = Field(None, max_length=20, description="发票类型")
    invoice_date: Optional[str] = Field(None, max_length=20, description="开票日期")
    amount: Optional[float] = Field(None, ge=0, description="金额")
    tax_amount: Optional[float] = Field(None, ge=0, description="税额")
    total_amount: Optional[float] = Field(None, ge=0, description="价税合计")
    seller_name: Optional[str] = Field(None, max_length=200, description="销方名称")
    seller_tax_number: Optional[str] = Field(None, max_length=50, description="销方税号")
    buyer_name: Optional[str] = Field(None, max_length=200, description="购方名称")
    buyer_tax_number: Optional[str] = Field(None, max_length=50, description="购方税号")
    check_code: Optional[str] = Field(None, max_length=50, description="校验码")
    category: Optional[str] = Field(None, max_length=20, description="自动分类")
    status: Optional[str] = Field("pending", max_length=20, description="状态")
    file_path: Optional[str] = Field(None, max_length=500, description="文件路径")
    ocr_raw_text: Optional[str] = Field(None, description="OCR原始文本")


class InvoiceUpdate(BaseModel):
    """更新发票信息"""
    invoice_number: Optional[str] = Field(None, max_length=50, description="发票号码")
    invoice_code: Optional[str] = Field(None, max_length=50, description="发票代码")
    invoice_type: Optional[str] = Field(None, max_length=20, description="发票类型")
    invoice_date: Optional[str] = Field(None, max_length=20, description="开票日期")
    amount: Optional[float] = Field(None, ge=0, description="金额")
    tax_amount: Optional[float] = Field(None, ge=0, description="税额")
    total_amount: Optional[float] = Field(None, ge=0, description="价税合计")
    seller_name: Optional[str] = Field(None, max_length=200, description="销方名称")
    seller_tax_number: Optional[str] = Field(None, max_length=50, description="销方税号")
    buyer_name: Optional[str] = Field(None, max_length=200, description="购方名称")
    buyer_tax_number: Optional[str] = Field(None, max_length=50, description="购方税号")
    check_code: Optional[str] = Field(None, max_length=50, description="校验码")
    category: Optional[str] = Field(None, max_length=20, description="自动分类")
    status: Optional[str] = Field(None, max_length=20, description="状态")


class InvoiceResponse(BaseModel):
    """发票响应模型"""
    id: int
    invoice_number: Optional[str] = None
    invoice_code: Optional[str] = None
    invoice_type: Optional[str] = None
    invoice_date: Optional[str] = None
    amount: Optional[float] = None
    tax_amount: Optional[float] = None
    total_amount: Optional[float] = None
    seller_name: Optional[str] = None
    seller_tax_number: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_tax_number: Optional[str] = None
    check_code: Optional[str] = None
    category: Optional[str] = None
    status: str
    file_path: Optional[str] = None
    ocr_raw_text: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class InvoiceListResponse(BaseModel):
    """发票列表响应（含分页信息）"""
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    items: List[InvoiceResponse] = Field(..., description="发票列表")


# ==================== 批量操作Schema ====================

class BatchDeleteRequest(BaseModel):
    """批量删除请求"""
    ids: List[int] = Field(..., min_length=1, description="要删除的发票ID列表")


# ==================== 统计相关Schema ====================

class TypeDistribution(BaseModel):
    """发票类型分布"""
    type_name: str = Field(..., description="类型名称")
    count: int = Field(..., description="数量")
    total_amount: Optional[float] = Field(None, description="总金额")


class CategoryDistribution(BaseModel):
    """分类分布"""
    category_name: str = Field(..., description="分类名称")
    count: int = Field(..., description="数量")
    total_amount: Optional[float] = Field(None, description="总金额")


class MonthlyStats(BaseModel):
    """月度统计"""
    month: str = Field(..., description="月份（格式：YYYY-MM）")
    count: int = Field(..., description="数量")
    total_amount: Optional[float] = Field(None, description="总金额")


class StatsOverview(BaseModel):
    """统计总览"""
    total_count: int = Field(..., description="发票总数")
    total_amount: float = Field(..., description="总金额")
    total_tax: float = Field(..., description="总税额")
    pending_count: int = Field(..., description="待审核数量")
    reviewed_count: int = Field(..., description="已审核数量")
    exported_count: int = Field(..., description="已导出数量")
    type_distribution: List[TypeDistribution] = Field([], description="按类型分布")
    category_distribution: List[CategoryDistribution] = Field([], description="按分类分布")


class StatsResponse(BaseModel):
    """统计响应"""
    code: int = Field(200, description="状态码")
    message: str = Field("success", description="消息")
    data: StatsOverview = Field(..., description="统计数据")


# ==================== 导出相关Schema ====================

class ExportRequest(BaseModel):
    """导出请求"""
    format: str = Field("excel", description="导出格式: excel / pdf")
    invoice_ids: Optional[List[int]] = Field(None, description="指定导出的发票ID列表，为空则导出全部")
    invoice_type: Optional[str] = Field(None, description="按发票类型筛选")
    category: Optional[str] = Field(None, description="按分类筛选")
    status: Optional[str] = Field(None, description="按状态筛选")
    start_date: Optional[str] = Field(None, description="起始日期")
    end_date: Optional[str] = Field(None, description="截止日期")


# ==================== 通用响应Schema ====================

class ApiResponse(BaseModel):
    """通用API响应"""
    code: int = Field(200, description="状态码")
    message: str = Field("success", description="消息")
    data: Optional[dict] = Field(None, description="响应数据")


class UploadResponse(BaseModel):
    """上传响应"""
    code: int = Field(200, description="状态码")
    message: str = Field("success", description="消息")
    data: Optional[List[InvoiceResponse]] = Field(None, description="识别后的发票列表")


# ==================== 用户认证相关Schema ====================

class UserRegister(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    email: Optional[str] = Field(None, max_length=100, description="邮箱")
    full_name: Optional[str] = Field(None, max_length=100, description="姓名")


class UserLogin(BaseModel):
    """用户登录请求"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")


class TokenResponse(BaseModel):
    """令牌响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(7200, description="access_token过期时间(秒)")


class RefreshTokenRequest(BaseModel):
    """刷新令牌请求"""
    refresh_token: str


class UserResponse(BaseModel):
    """用户信息响应"""
    id: int
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ==================== 打印排版相关Schema ====================

class PrintRequest(BaseModel):
    """打印请求"""
    invoice_ids: Optional[List[int]] = Field(None, description="指定打印的发票ID列表")
    invoices_per_page: int = Field(2, ge=1, le=2, description="每页发票数量（1或2）")
    sort_by_date: str = Field("asc", description="按日期排序方向: asc/desc")
    start_date: Optional[str] = Field(None, description="起始日期筛选")
    end_date: Optional[str] = Field(None, description="截止日期筛选")
    invoice_type: Optional[str] = Field(None, description="发票类型筛选")
    category: Optional[str] = Field(None, description="分类筛选")
    status: Optional[str] = Field(None, description="状态筛选")
    title: Optional[str] = Field(None, description="文档标题")

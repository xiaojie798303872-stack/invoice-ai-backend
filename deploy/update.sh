#!/bin/bash
# 发票AI系统 - 更新脚本
# 用法: sudo bash deploy/update.sh
# 此脚本用于更新应用代码、依赖并重启服务

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

APP_DIR="/opt/invoice-ai"
APP_USER="invoice-ai"
BACKUP_BEFORE_UPDATE=true

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  发票AI系统 - 更新脚本${NC}"
echo -e "${GREEN}========================================${NC}"

# 检查root权限
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请使用 root 权限运行此脚本${NC}"
    exit 1
fi

# 检查应用目录
if [ ! -d "$APP_DIR" ]; then
    echo -e "${RED}错误: 应用目录 $APP_DIR 不存在${NC}"
    echo -e "${YELLOW}请先运行 install.sh 进行安装${NC}"
    exit 1
fi

# 更新前备份（可选）
if [ "$BACKUP_BEFORE_UPDATE" = true ]; then
    echo -e "${YELLOW}[1/6] 创建更新前备份...${NC}"
    BACKUP_DIR="$APP_DIR/backups/pre-update-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    cp "$APP_DIR/invoice_ai.db" "$BACKUP_DIR/" 2>/dev/null || true
    cp "$APP_DIR/.env" "$BACKUP_DIR/" 2>/dev/null || true
    echo -e "${GREEN}备份已保存到: $BACKUP_DIR${NC}"
fi

# 拉取最新代码（如果使用git）
echo -e "${YELLOW}[2/6] 更新代码...${NC}"
if [ -d "$APP_DIR/.git" ]; then
    cd "$APP_DIR"
    git pull origin main || git pull origin master || echo -e "${YELLOW}Git拉取失败，使用本地代码${NC}"
else
    echo -e "${YELLOW}未检测到Git仓库，跳过代码拉取${NC}"
    echo -e "${YELLOW}如需从Git更新，请先在 $APP_DIR 目录初始化Git仓库${NC}"
fi

# 保存当前上传的文件（防止被覆盖）
echo -e "${YELLOW}[3/6] 保护用户数据...${NC}"
if [ -d "$APP_DIR/uploads" ]; then
    TEMP_UPLOADS="/tmp/invoice-ai-uploads-$(date +%s)"
    cp -r "$APP_DIR/uploads" "$TEMP_UPLOADS"
    echo -e "${GREEN}上传文件已临时保存${NC}"
fi

# 更新依赖
echo -e "${YELLOW}[4/6] 更新Python依赖...${NC}"
cd "$APP_DIR"
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

# 恢复上传的文件
if [ -d "$TEMP_UPLOADS" ]; then
    cp -r "$TEMP_UPLOADS"/* "$APP_DIR/uploads/" 2>/dev/null || true
    rm -rf "$TEMP_UPLOADS"
    echo -e "${GREEN}上传文件已恢复${NC}"
fi

# 数据库迁移（如果有）
echo -e "${YELLOW}[5/6] 检查数据库更新...${NC}"
cd "$APP_DIR"
python3 -c "
import asyncio
from database import init_db
asyncio.run(init_db())
" 2>/dev/null || echo -e "${YELLOW}数据库检查跳过${NC}"

# 修复文件权限
echo -e "${YELLOW}[6/6] 修复文件权限...${NC}"
chown -R $APP_USER:$APP_USER "$APP_DIR"
chmod 600 "$APP_DIR/.env" 2>/dev/null || true

# 重启服务
echo -e "${YELLOW}重启服务...${NC}"
systemctl restart invoice-ai
sleep 2

# 检查服务状态
if systemctl is-active --quiet invoice-ai; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  更新成功！${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${YELLOW}服务状态:${NC}"
    systemctl status invoice-ai --no-pager
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}  服务启动失败！${NC}"
    echo -e "${RED}========================================${NC}"
    echo -e "${YELLOW}查看日志以排查问题:${NC}"
    echo -e "${BLUE}  journalctl -u invoice-ai -n 50${NC}"
    exit 1
fi

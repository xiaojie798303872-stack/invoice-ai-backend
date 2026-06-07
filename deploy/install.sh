#!/bin/bash
# 发票AI系统 - 生产环境自动化安装脚本
# 支持 Ubuntu 20.04+/Debian 11+/CentOS 8+
# 使用方法: sudo bash deploy/install.sh

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  发票AI自动排序整理系统 - 安装脚本${NC}"
echo -e "${GREEN}========================================${NC}"

# 检查root权限
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请使用 root 权限运行此脚本${NC}"
    exit 1
fi

# 检测操作系统
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
    OS_VERSION=$VERSION_ID
else
    echo -e "${RED}无法检测操作系统${NC}"
    exit 1
fi

echo -e "${YELLOW}检测到操作系统: $OS $OS_VERSION${NC}"

# 安装基础依赖
echo -e "${YELLOW}[1/9] 安装基础依赖...${NC}"
if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
    apt-get update -qq
    apt-get install -y -qq python3 python3-pip python3-venv nginx git curl wget unzip
    # 图像处理相关库（OpenCV等需要）
    apt-get install -y -qq libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev
    # 中文字体支持
    apt-get install -y -qq ttf-wqy-zenhei fonts-wqy-microhei
    # 工具
    apt-get install -y -qq sqlite3 logrotate
elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Rocky"* ]] || [[ "$OS" == *"AlmaLinux"* ]]; then
    yum update -y -q
    yum install -y -q python3 python3-pip nginx git curl wget unzip
    # 图像处理相关库
    yum install -y -q mesa-libGL glib2 libSM libXext libXrender
    # 中文字体支持
    yum install -y -q wqy-zenhei-fonts wqy-microhei-fonts
    # 工具
    yum install -y -q sqlite logrotate
else
    echo -e "${RED}不支持的操作系统: $OS${NC}"
    exit 1
fi

# 创建应用目录
APP_DIR="/opt/invoice-ai"
APP_USER="invoice-ai"

echo -e "${YELLOW}[2/9] 创建应用目录和用户...${NC}"
useradd -r -s /bin/false $APP_USER 2>/dev/null || true
mkdir -p $APP_DIR
mkdir -p $APP_DIR/uploads
mkdir -p $APP_DIR/backups
mkdir -p $APP_DIR/logs
chown -R $APP_USER:$APP_USER $APP_DIR

# 复制项目文件（假设脚本在项目根目录运行）
echo -e "${YELLOW}[3/9] 复制项目文件...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 检查项目文件是否存在
if [ ! -f "$PROJECT_DIR/main.py" ]; then
    echo -e "${RED}错误: 未找到项目文件。请确保脚本位于项目根目录的 deploy/ 文件夹中。${NC}"
    echo -e "${YELLOW}当前检测到的项目目录: $PROJECT_DIR${NC}"
    exit 1
fi

cp -r "$PROJECT_DIR"/* $APP_DIR/
chown -R $APP_USER:$APP_USER $APP_DIR

# 创建Python虚拟环境
echo -e "${YELLOW}[4/9] 创建Python虚拟环境...${NC}"
cd $APP_DIR
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

# 创建环境配置文件
echo -e "${YELLOW}[5/9] 创建环境配置文件...${NC}"
JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))")

cat > $APP_DIR/.env << EOF
# 发票AI系统 - 生产环境配置
# 请根据实际情况修改以下配置

# ===== 基础配置 =====
JWT_SECRET_KEY=$JWT_SECRET
API_VERSION=2.0.0

# ===== 数据库配置 =====
# 使用SQLite数据库，无需额外配置
DB_ENGINE=sqlite
DATABASE_URL=sqlite+aiosqlite:///./invoice_ai.db

# ===== OCR配置 =====
OCR_ENGINE=local
OCR_CONFIDENCE_THRESHOLD=0.5
OCR_USE_GPU=false

# ===== 存储配置 =====
STORAGE_TYPE=local
UPLOAD_DIR=/opt/invoice-ai/uploads

# ===== 邮件配置（可选，用于通知功能） =====
# SMTP_HOST=smtp.qq.com
# SMTP_PORT=465
# SMTP_USER=your-email@qq.com
# SMTP_PASSWORD=your-smtp-password

# ===== 备份配置 =====
BACKUP_RETENTION_DAYS=30
BACKUP_MAX_COUNT=50

# ===== 云OCR配置（可选） =====
# BAIDU_OCR_API_KEY=your-baidu-key
# BAIDU_OCR_SECRET_KEY=your-baidu-secret
# TENCENT_OCR_SECRET_ID=your-tencent-id
# TENCENT_OCR_SECRET_KEY=your-tencent-secret
EOF

chown $APP_USER:$APP_USER $APP_DIR/.env
chmod 600 $APP_DIR/.env

# 初始化数据库
echo -e "${YELLOW}[6/9] 初始化数据库...${NC}"
cd $APP_DIR
python3 -c "
import asyncio
from database import init_db
asyncio.run(init_db())
" || echo -e "${YELLOW}数据库初始化跳过（将在首次启动时自动创建）${NC}"

# 配置Nginx
echo -e "${YELLOW}[7/9] 配置Nginx...${NC}"
if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
    mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled
    cp $APP_DIR/deploy/nginx.conf /etc/nginx/sites-available/invoice-ai
    ln -sf /etc/nginx/sites-available/invoice-ai /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Rocky"* ]] || [[ "$OS" == *"AlmaLinux"* ]]; then
    cp $APP_DIR/deploy/nginx.conf /etc/nginx/conf.d/invoice-ai.conf
fi

# 测试Nginx配置
nginx -t && systemctl restart nginx

# 配置Systemd服务
echo -e "${YELLOW}[8/9] 配置Systemd服务...${NC}"
cp $APP_DIR/deploy/invoice-ai.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable invoice-ai

# 配置防火墙
echo -e "${YELLOW}[9/9] 配置防火墙...${NC}"
if command -v ufw &> /dev/null; then
    ufw allow 'Nginx Full' >/dev/null 2>&1 || true
    ufw allow 22/tcp >/dev/null 2>&1 || true
    ufw --force enable >/dev/null 2>&1 || true
    echo -e "${GREEN}已配置 UFW 防火墙${NC}"
elif command -v firewall-cmd &> /dev/null; then
    firewall-cmd --permanent --add-service=http >/dev/null 2>&1 || true
    firewall-cmd --permanent --add-service=https >/dev/null 2>&1 || true
    firewall-cmd --reload >/dev/null 2>&1 || true
    echo -e "${GREEN}已配置 firewalld 防火墙${NC}"
else
    echo -e "${YELLOW}未检测到支持的防火墙工具，请手动配置防火墙规则${NC}"
fi

# 配置日志轮转
cat > /etc/logrotate.d/invoice-ai << 'EOF'
/opt/invoice-ai/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 invoice-ai invoice-ai
    sharedscripts
    postrotate
        systemctl reload invoice-ai >/dev/null 2>&1 || true
    endscript
}
EOF

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  安装完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}接下来请执行以下操作：${NC}"
echo ""
echo -e "${BLUE}1. 编辑配置文件:${NC}"
echo "   nano $APP_DIR/.env"
echo ""
echo -e "${BLUE}2. 配置域名DNS指向本服务器IP${NC}"
echo ""
echo -e "${BLUE}3. 申请SSL证书:${NC}"
echo "   bash $APP_DIR/deploy/ssl-setup.sh your-domain.com"
echo ""
echo -e "${BLUE}4. 启动服务:${NC}"
echo "   systemctl start invoice-ai"
echo ""
echo -e "${BLUE}5. 查看服务状态:${NC}"
echo "   systemctl status invoice-ai --no-pager"
echo ""
echo -e "${BLUE}6. 查看实时日志:${NC}"
echo "   journalctl -u invoice-ai -f"
echo ""
echo -e "${BLUE}7. 配置自动备份:${NC}"
echo "   bash $APP_DIR/deploy/backup-cron.sh"
echo ""
echo -e "${YELLOW}API文档地址: http://your-domain.com/docs${NC}"
echo -e "${YELLOW}默认管理员账号: admin / admin123${NC}"
echo ""
echo -e "${GREEN}========================================${NC}"

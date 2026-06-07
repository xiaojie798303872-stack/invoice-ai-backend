#!/bin/bash
# SSL证书申请脚本（使用Let's Encrypt + Certbot）
# 用法: sudo bash deploy/ssl-setup.sh your-domain.com
# 注意: 运行前请确保域名DNS已解析到本服务器

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

DOMAIN=$1
EMAIL=$2

# 检查参数
if [ -z "$DOMAIN" ]; then
    echo -e "${RED}用法: $0 your-domain.com [admin-email@example.com]${NC}"
    echo -e "${YELLOW}示例: $0 invoice.example.com admin@example.com${NC}"
    exit 1
fi

# 默认邮箱
if [ -z "$EMAIL" ]; then
    EMAIL="admin@$DOMAIN"
    echo -e "${YELLOW}未提供邮箱，使用默认邮箱: $EMAIL${NC}"
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  SSL证书申请脚本${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "${YELLOW}域名: $DOMAIN${NC}"
echo -e "${YELLOW}邮箱: $EMAIL${NC}"

# 检查root权限
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请使用 root 权限运行此脚本${NC}"
    exit 1
fi

# 检测操作系统
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
else
    echo -e "${RED}无法检测操作系统${NC}"
    exit 1
fi

# 安装Certbot
echo -e "${YELLOW}[1/4] 安装Certbot...${NC}"
if command -v apt-get &> /dev/null; then
    apt-get update -qq
    apt-get install -y -qq certbot python3-certbot-nginx
elif command -v yum &> /dev/null; then
    yum install -y -q certbot python3-certbot-nginx
elif command -v dnf &> /dev/null; then
    dnf install -y -q certbot python3-certbot-nginx
else
    echo -e "${RED}不支持的包管理器${NC}"
    exit 1
fi

# 创建webroot目录（用于HTTP验证）
echo -e "${YELLOW}[2/4] 创建验证目录...${NC}"
mkdir -p /var/www/certbot

# 检查Nginx配置中是否包含该域名
echo -e "${YELLOW}[3/4] 检查Nginx配置...${NC}"
if ! grep -q "$DOMAIN" /etc/nginx/sites-available/invoice-ai 2>/dev/null && ! grep -q "$DOMAIN" /etc/nginx/conf.d/invoice-ai.conf 2>/dev/null; then
    echo -e "${YELLOW}警告: Nginx配置中未找到域名 $DOMAIN${NC}"
    echo -e "${YELLOW}请先更新 nginx.conf 中的 server_name 为您的实际域名${NC}"
    echo -e "${YELLOW}然后重新运行此脚本${NC}"
    exit 1
fi

# 申请证书
echo -e "${YELLOW}[4/4] 申请SSL证书...${NC}"
certbot --nginx \
    -d "$DOMAIN" \
    -d "www.$DOMAIN" \
    --non-interactive \
    --agree-tos \
    --email "$EMAIL" \
    --redirect \
    --hsts \
    --staple-ocsp

# 设置自动续期
echo -e "${YELLOW}配置自动续期...${NC}"
if [ -d /etc/cron.d ]; then
    cat > /etc/cron.d/certbot-renew << EOF
# Let's Encrypt SSL证书自动续期
# 每天凌晨0点和中午12点检查证书是否需要续期
0 0,12 * * * root certbot renew --quiet --deploy-hook "systemctl reload nginx" >/dev/null 2>&1
EOF
    chmod 644 /etc/cron.d/certbot-renew
    echo -e "${GREEN}已配置自动续期定时任务（/etc/cron.d/certbot-renew）${NC}"
fi

# 验证证书
echo -e "${YELLOW}验证证书...${NC}"
if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    echo -e "${GREEN}证书申请成功！${NC}"
    echo -e "${GREEN}证书路径: /etc/letsencrypt/live/$DOMAIN/${NC}"
    echo -e "${GREEN}到期时间: $(openssl x509 -in /etc/letsencrypt/live/$DOMAIN/fullchain.pem -noout -dates | grep notAfter | cut -d= -f2)${NC}"
else
    echo -e "${RED}证书申请可能失败，请检查Certbot日志${NC}"
    exit 1
fi

# 测试Nginx配置并重启
echo -e "${YELLOW}重启Nginx...${NC}"
nginx -t && systemctl restart nginx

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  SSL证书配置完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}您的网站现在可以通过HTTPS访问:${NC}"
echo -e "${BLUE}  https://$DOMAIN${NC}"
echo -e "${BLUE}  https://www.$DOMAIN${NC}"
echo ""
echo -e "${YELLOW}证书将自动续期，无需手动干预。${NC}"
echo -e "${YELLOW}如需手动测试续期，请运行: certbot renew --dry-run${NC}"

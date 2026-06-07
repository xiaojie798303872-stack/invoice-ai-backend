#!/bin/bash
# 发票AI系统 - 自动备份定时任务配置脚本
# 用法: sudo bash deploy/backup-cron.sh
# 此脚本配置每天凌晨2点自动执行数据备份

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

APP_DIR="/opt/invoice-ai"
CRON_FILE="/etc/cron.d/invoice-ai-backup"
BACKUP_TIME="0 2"  # 每天凌晨2点

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  发票AI系统 - 自动备份配置${NC}"
echo -e "${GREEN}========================================${NC}"

# 检查root权限
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请使用 root 权限运行此脚本${NC}"
    exit 1
fi

# 检查应用目录
if [ ! -d "$APP_DIR" ]; then
    echo -e "${RED}错误: 应用目录 $APP_DIR 不存在${NC}"
    exit 1
fi

# 创建日志目录
mkdir -p "$APP_DIR/logs"
mkdir -p "$APP_DIR/backups"

# 创建备份脚本
echo -e "${YELLOW}[1/3] 创建备份执行脚本...${NC}"
cat > "$APP_DIR/backup.sh" << 'EOF'
#!/bin/bash
# 发票AI系统 - 备份执行脚本
# 此脚本由定时任务调用，也可手动执行

set -e

APP_DIR="/opt/invoice-ai"
BACKUP_DIR="$APP_DIR/backups"
LOG_FILE="$APP_DIR/logs/backup.log"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="invoice_ai_backup_$TIMESTAMP"

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 记录开始时间
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始备份..." >> "$LOG_FILE"

# 备份SQLite数据库
if [ -f "$APP_DIR/invoice_ai.db" ]; then
    cp "$APP_DIR/invoice_ai.db" "$BACKUP_DIR/${BACKUP_NAME}.db"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 数据库备份完成: ${BACKUP_NAME}.db" >> "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 警告: 数据库文件不存在" >> "$LOG_FILE"
fi

# 备份配置文件
cp "$APP_DIR/.env" "$BACKUP_DIR/${BACKUP_NAME}.env" 2>/dev/null || true

# 备份上传文件（可选，如果文件较大可注释掉）
# tar -czf "$BACKUP_DIR/${BACKUP_NAME}_uploads.tar.gz" -C "$APP_DIR" uploads/ 2>/dev/null || true

# 清理旧备份（保留最近30天的备份）
find "$BACKUP_DIR" -name "invoice_ai_backup_*.db" -type f -mtime +30 -delete 2>/dev/null || true
find "$BACKUP_DIR" -name "invoice_ai_backup_*.env" -type f -mtime +30 -delete 2>/dev/null || true

# 统计备份数量
BACKUP_COUNT=$(find "$BACKUP_DIR" -name "invoice_ai_backup_*.db" -type f | wc -l)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 备份完成。当前共有 $BACKUP_COUNT 个数据库备份。" >> "$LOG_FILE"
EOF

chmod +x "$APP_DIR/backup.sh"
chown invoice-ai:invoice-ai "$APP_DIR/backup.sh"

# 创建定时任务
echo -e "${YELLOW}[2/3] 配置定时任务...${NC}"
cat > "$CRON_FILE" << EOF
# 发票AI系统 - 自动备份定时任务
# 每天凌晨2点执行完整备份
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

# 数据库和配置备份
$BACKUP_TIME * * * root $APP_DIR/backup.sh

# 每周日清理超过30天的日志
0 3 * * 0 root find $APP_DIR/logs -name "*.log" -type f -mtime +30 -delete 2>/dev/null || true
EOF

chmod 644 "$CRON_FILE"

# 验证定时任务
echo -e "${YELLOW}[3/3] 验证配置...${NC}"
if [ -f "$CRON_FILE" ]; then
    echo -e "${GREEN}定时任务已配置: $CRON_FILE${NC}"
    echo -e "${YELLOW}备份时间: 每天凌晨 2:00${NC}"
    echo -e "${YELLOW}备份目录: $APP_DIR/backups/${NC}"
    echo -e "${YELLOW}日志文件: $APP_DIR/logs/backup.log${NC}"
else
    echo -e "${RED}定时任务配置失败${NC}"
    exit 1
fi

# 立即执行一次备份测试
echo -e "${YELLOW}正在执行首次备份测试...${NC}"
bash "$APP_DIR/backup.sh"

if [ -f "$APP_DIR/logs/backup.log" ]; then
    echo -e "${GREEN}备份日志:${NC}"
    tail -n 5 "$APP_DIR/logs/backup.log"
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  自动备份配置完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}管理命令:${NC}"
echo -e "${BLUE}  手动执行备份: bash $APP_DIR/backup.sh${NC}"
echo -e "${BLUE}  查看备份日志: tail -f $APP_DIR/logs/backup.log${NC}"
echo -e "${BLUE}  查看备份文件: ls -la $APP_DIR/backups/${NC}"
echo -e "${BLUE}  恢复数据库: cp $APP_DIR/backups/xxx.db $APP_DIR/invoice_ai.db${NC}"

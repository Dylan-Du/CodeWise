#!/bin/bash
# Codex助手 部署脚本
set -e

echo "[1/6] 安装 Node.js 18..."
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt-get install -y nodejs

echo "[2/6] 安装 PM2..."
npm install -g pm2

echo "[3/6] 创建项目目录..."
mkdir -p /opt/codex-admin
cd /opt/codex-admin

echo "[4/6] 解压代码..."
if [ -f /tmp/admin-deploy.tar.gz ]; then
    tar xzf /tmp/admin-deploy.tar.gz --strip-components=1 -C /opt/codex-admin/
else
    echo "未找到 /tmp/admin-deploy.tar.gz，请先上传"
    exit 1
fi

echo "[5/6] 安装依赖并构建..."
npm install
npm run build

echo "[6/6] 启动服务..."
cat > /opt/codex-admin/.env << 'EOF'
ADMIN_TOKEN=codex-admin-2024-secure
PORT=3000
EOF

pm2 delete codex-admin 2>/dev/null || true
pm2 start "npm run start" --name codex-admin
pm2 save
pm2 startup systemd -u root --hp /root 2>/dev/null || true

echo ""
echo "=== 部署完成 ==="
echo "后台地址: http://43.160.233.155:3000"
echo "登录密钥: codex-admin-2024-secure"

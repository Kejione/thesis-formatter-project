# 毕业论文排版 Agent - 部署指南

## 📋 目录

1. [快速开始](#快速开始)
2. [开发环境部署](#开发环境部署)
3. [生产环境部署](#生产环境部署)
4. [CI/CD 配置](#cicd-配置)
5. [运维监控](#运维监控)
6. [故障排查](#故障排查)

---

## 快速开始

### 使用 Docker Compose 一键启动（推荐）

```bash
# 1. 克隆项目
git clone <repository-url>
cd thesis-formatter

# 2. 复制环境变量模板
cp .env.example .env

# 3. 编辑 .env 文件，配置必要的参数
# 特别是：
# - 数据库密码
# - MinIO 密钥
# - AI 模型 API Key

# 4. 启动开发环境
docker-compose up -d

# 5. 初始化数据库
docker-compose exec api alembic upgrade head

# 6. 访问应用
# 前端: http://localhost:5173
# API: http://localhost:8000
# API 文档: http://localhost:8000/docs
```

---

## 开发环境部署

### 方式一：Docker Compose（推荐）

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f api

# 重启服务
docker-compose restart api

# 停止所有服务
docker-compose down

# 完全重置（删除数据卷）
docker-compose down -v
```

### 方式二：本地开发

#### 后端

```bash
cd thesis-formatter-api

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -e ".[dev]"

# 复制环境变量
cp .env.example .env
# 编辑 .env 配置本地数据库连接

# 初始化数据库
alembic upgrade head

# 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 前端

```bash
cd thesis-formatter-web

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

#### 启动 Celery Worker

```bash
cd thesis-formatter-api
source venv/bin/activate

celery -A app.tasks.celery_app worker --loglevel=info
```

---

## 生产环境部署

### 前置要求

- Docker & Docker Compose
- 域名（用于 HTTPS）
- SSL 证书（或使用 Let's Encrypt）
- 至少 2GB RAM，2 核 CPU

### 部署步骤

#### 1. 准备服务器

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh

# 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

#### 2. 配置环境变量

```bash
mkdir -p /opt/thesis-formatter
cd /opt/thesis-formatter

# 创建环境变量文件
cat > .env << 'EOF'
# ─── Application ───
APP_NAME=Thesis Formatter
DEBUG=false
ENVIRONMENT=production

# ─── Database ───
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_STRONG_PASSWORD@postgres:5432/thesis_formatter

# ─── Redis ───
REDIS_URL=redis://redis:6379/0

# ─── MinIO ───
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=YOUR_ACCESS_KEY
MINIO_SECRET_KEY=YOUR_SECRET_KEY
MINIO_BUCKET=thesis-formatter

# ─── AI Model (DeepSeek recommended) ───
OPENAI_API_KEY=sk-your-api-key
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat

# ─── Security ───
SECRET_KEY=your-random-secret-key-at-least-32-chars
EOF
```

#### 3. 配置 SSL 证书

**方式一：使用现有证书**

```bash
mkdir -p nginx/ssl
cp your-cert.pem nginx/ssl/cert.pem
cp your-key.pem nginx/ssl/key.pem
```

**方式二：使用 Let's Encrypt**

```bash
# 安装 certbot
sudo apt-get install certbot

# 获取证书
sudo certbot certonly --standalone -d your-domain.com

# 复制证书
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem nginx/ssl/key.pem
```

#### 4. 启动生产环境

```bash
# 拉取最新镜像
docker-compose -f docker-compose.prod.yml pull

# 运行数据库迁移
docker-compose -f docker-compose.prod.yml run --rm api alembic upgrade head

# 启动所有服务
docker-compose -f docker-compose.prod.yml up -d

# 检查服务状态
docker-compose -f docker-compose.prod.yml ps
```

#### 5. 配置自动更新证书（Let's Encrypt）

```bash
# 创建更新脚本
cat > /opt/renew-ssl.sh << 'EOF'
#!/bin/bash
certbot renew --quiet
cp /etc/letsencrypt/live/your-domain.com/fullchain.pem /opt/thesis-formatter/nginx/ssl/cert.pem
cp /etc/letsencrypt/live/your-domain.com/privkey.pem /opt/thesis-formatter/nginx/ssl/key.pem
docker-compose -f /opt/thesis-formatter/docker-compose.prod.yml restart nginx
EOF

chmod +x /opt/renew-ssl.sh

# 添加定时任务（每月 1 号执行）
echo "0 0 1 * * /opt/renew-ssl.sh" | sudo crontab -
```

---

## CI/CD 配置

### GitHub Actions 工作流

项目已配置 `.github/workflows/ci.yml`，自动执行：

1. **测试阶段**
   - 后端单元测试（pytest）
   - 前端构建测试
   - 代码覆盖率报告

2. **构建阶段**
   - 构建 Docker 镜像
   - 推送到 GitHub Container Registry

3. **部署阶段**
   - SSH 到生产服务器
   - 拉取最新镜像
   - 执行数据库迁移
   - 重启服务

### 配置 Secrets

在 GitHub 仓库设置中添加以下 Secrets：

| Secret | 说明 |
|--------|------|
| `DEPLOY_HOST` | 生产服务器 IP 或域名 |
| `DEPLOY_USER` | SSH 用户名 |
| `DEPLOY_KEY` | SSH 私钥 |
| `GITHUB_TOKEN` | 自动提供，无需手动设置 |

### 手动触发部署

```bash
# 本地构建并推送镜像
docker build -t ghcr.io/your-username/thesis-formatter-api:latest \
  -f thesis-formatter-api/Dockerfile.prod ./thesis-formatter-api
docker push ghcr.io/your-username/thesis-formatter-api:latest
```

---

## 运维监控

### 查看日志

```bash
# 所有服务日志
docker-compose -f docker-compose.prod.yml logs -f

# 特定服务
docker-compose -f docker-compose.prod.yml logs -f api
docker-compose -f docker-compose.prod.yml logs -f worker

# 最近 100 行
docker-compose -f docker-compose.prod.yml logs --tail=100 api
```

### 监控资源使用

```bash
# Docker 容器资源使用
docker stats

# 系统资源
df -h  # 磁盘
free -h  # 内存
top  # CPU
```

### 备份数据

```bash
# 备份数据库
docker-compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U postgres thesis_formatter > backup_$(date +%Y%m%d).sql

# 备份 MinIO 数据
docker-compose -f docker-compose.prod.yml exec minio \
  mc mirror /data /backup/minio

# 自动备份脚本（添加到 crontab）
# 0 2 * * * /opt/thesis-formatter/backup.sh
```

### 健康检查

```bash
# API 健康检查
curl https://your-domain.com/health

# 数据库连接
docker-compose -f docker-compose.prod.yml exec postgres \
  pg_isready -U postgres

# Redis 连接
docker-compose -f docker-compose.prod.yml exec redis \
  redis-cli ping
```

---

## 故障排查

### 常见问题

#### 1. 服务无法启动

```bash
# 检查端口占用
sudo netstat -tlnp | grep :80
sudo netstat -tlnp | grep :443

# 检查日志
docker-compose logs api
```

#### 2. 数据库连接失败

```bash
# 检查数据库状态
docker-compose ps postgres

# 进入数据库容器
docker-compose exec postgres psql -U postgres -d thesis_formatter

# 重置数据库（谨慎操作！）
docker-compose down -v
docker-compose up -d postgres
docker-compose run --rm api alembic upgrade head
```

#### 3. Celery 任务不执行

```bash
# 检查 Worker 状态
docker-compose logs worker

# 重启 Worker
docker-compose restart worker

# 检查 Redis
docker-compose exec redis redis-cli llen celery
```

#### 4. 文件上传失败

```bash
# 检查 MinIO 状态
docker-compose logs minio

# 检查存储桶
docker-compose exec minio mc ls local/

# 重新创建存储桶
docker-compose exec minio mc mb local/thesis-formatter
```

#### 5. AI 模型调用失败

```bash
# 测试模型连接
curl -X POST https://your-domain.com/api/v1/models/{model_id}/test

# 检查 API Key
docker-compose logs api | grep -i "llm\|openai\|deepseek"
```

### 性能优化

#### 增加 Worker 数量

编辑 `docker-compose.prod.yml`：

```yaml
worker:
  deploy:
    replicas: 4  # 增加 Worker 数量
```

#### 调整数据库连接池

在 `.env` 中设置：

```env
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40
```

#### 启用 CDN（生产环境）

在 Nginx 配置中添加：

```nginx
location /static/ {
    proxy_pass http://web_backend/static/;
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

---

## 更新部署

### 滚动更新（零停机）

```bash
cd /opt/thesis-formatter

# 1. 拉取最新代码
git pull origin main

# 2. 拉取最新镜像
docker-compose -f docker-compose.prod.yml pull

# 3. 运行数据库迁移
docker-compose -f docker-compose.prod.yml run --rm api alembic upgrade head

# 4. 滚动更新服务
docker-compose -f docker-compose.prod.yml up -d --no-deps --scale api=2 api
docker-compose -f docker-compose.prod.yml up -d --scale api=1 api

# 5. 重启其他服务
docker-compose -f docker-compose.prod.yml up -d

# 6. 清理旧镜像
docker image prune -f
```

### 回滚部署

```bash
# 查看历史版本
docker images | grep thesis-formatter

# 回滚到指定版本
docker-compose -f docker-compose.prod.yml up -d api=ghcr.io/...:previous-tag
```

---

## 安全建议

1. **定期更新依赖**
   ```bash
   pip list --outdated
   npm outdated
   ```

2. **启用防火墙**
   ```bash
   sudo ufw enable
   sudo ufw allow 22
   sudo ufw allow 80
   sudo ufw allow 443
   ```

3. **定期备份**
   - 数据库：每日自动备份
   - 文件存储：每周备份
   - 配置文件：版本控制

4. **监控告警**
   - 设置磁盘空间告警（>80%）
   - 设置内存使用告警（>90%）
   - 设置服务健康检查告警

---

## 获取帮助

- **GitHub Issues**: [提交问题](https://github.com/your-repo/issues)
- **API 文档**: https://your-domain.com/docs
- **日志查看**: `docker-compose logs -f`

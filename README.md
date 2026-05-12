# 毕业论文 Word 排版 Agent

自动解析学校格式规范、检查论文格式问题、生成修复文档的智能工具。

## 🚀 快速开始

### 环境要求

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose（推荐）

### 使用 Docker Compose 启动（推荐）

```bash
# 克隆项目
cd /workspace

# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 初始化数据库
docker-compose exec api alembic upgrade head
```

服务启动后：
- 前端：http://localhost:5173
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs
- MinIO 控制台：http://localhost:9001（用户名/密码：minioadmin/minioadmin）

### 本地开发

#### 后端

```bash
cd thesis-formatter-api

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate  # Windows

# 安装依赖
pip install -e ".[dev]"

# 复制环境变量
cp .env.example .env
# 编辑 .env 填入配置

# 初始化数据库
alembic upgrade head

# 启动开发服务器
uvicorn app.main:app --reload
```

#### 前端

```bash
cd thesis-formatter-web

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

## 📁 项目结构

```
/workspace
├── docker-compose.yml          # Docker Compose 配置
├── thesis-formatter-api/       # 后端项目
│   ├── app/
│   │   ├── api/v1/            # API 路由
│   │   │   └── endpoints/     # 各模块端点
│   │   ├── core/              # 核心配置
│   │   ├── models/            # 数据库模型
│   │   ├── schemas/           # Pydantic 模型
│   │   ├── services/          # 业务逻辑
│   │   │   ├── docx/          # 文档处理
│   │   │   └── ai/            # AI 模块
│   │   ├── tasks/             # Celery 任务
│   │   └── main.py            # 应用入口
│   ├── alembic/               # 数据库迁移
│   ├── tests/                 # 测试
│   ├── pyproject.toml         # 项目配置
│   └── Dockerfile
│
└── thesis-formatter-web/       # 前端项目
    ├── src/
    │   ├── pages/             # 页面组件
    │   ├── components/        # 通用组件
    │   ├── services/          # API 调用
    │   ├── types/             # TypeScript 类型
    │   └── main.tsx           # 入口
    ├── package.json
    └── Dockerfile
```

## 🔧 核心功能

### 已实现（脚手架）

- ✅ FastAPI 后端框架
- ✅ SQLAlchemy ORM + Alembic 迁移
- ✅ Celery 异步任务队列
- ✅ React + TypeScript 前端
- ✅ Ant Design 5 UI 组件
- ✅ Docker Compose 开发环境
- ✅ API 路由骨架（11 个端点）
- ✅ 数据库模型（6 张表）
- ✅ 文档解析器（DocxParser）
- ✅ 格式检查器（FormatChecker）
- ✅ AI Provider 模块
- ✅ 规范解析器（SpecParser）

### 待开发

- 🔲 MinIO 文件上传/下载
- 🔲 完整的格式修复器
- 🔲 AI 规范解析集成
- 🔲 文档在线预览
- 🔲 单元测试和集成测试

## 📚 API 文档

启动后端后访问 http://localhost:8000/docs 查看 Swagger UI 文档。

### 主要接口

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | /api/v1/tasks | 创建格式检查任务 |
| GET | /api/v1/tasks/{taskId} | 获取任务状态 |
| GET | /api/v1/tasks/{taskId}/report | 获取检查报告 |
| POST | /api/v1/tasks/{taskId}/fix | 执行格式修复 |
| GET | /api/v1/tasks/{taskId}/download | 下载修复文档 |
| POST | /api/v1/rules/parse | AI 解析格式规范 |
| GET | /api/v1/templates | 获取学校模板列表 |
| POST | /api/v1/models/config | 配置 AI 模型 |

## 🤖 AI 模型配置

系统支持多种 OpenAI 兼容的 AI 模型：

| Provider | Base URL | 特点 |
|----------|----------|------|
| DeepSeek | https://api.deepseek.com/v1 | 性价比最高 |
| OpenAI | https://api.openai.com/v1 | 综合能力强 |
| 通义千问 | https://dashscope.aliyuncs.com/compatible-mode/v1 | 中文优化 |
| Ollama | http://localhost:11434/v1 | 完全离线 |

配置方式：
1. 通过 API：`POST /api/v1/models/config`
2. 通过环境变量：设置 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`

## 🧪 测试

```bash
# 后端测试
cd thesis-formatter-api
pytest

# 前端测试
cd thesis-formatter-web
npm run test
```

## 📄 License

MIT

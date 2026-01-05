## Reader - 后端 API 服务

基于 FastAPI 的异步后端服务，为 Reader 前端提供 RESTful API 支持。

## 📦 技术栈

- **Python 3.11+**
- **FastAPI** - 现代异步 Web 框架
- **SQLAlchemy 2.0** - 异步 ORM
- **PostgreSQL** - 主数据库
- **Redis** - 缓存与会话
- **MinIO** - 对象存储（S3 兼容）

## 📁 项目结构

```
src/
├── config/          # 配置模块（数据库、Redis、设置）
├── models/          # SQLAlchemy 数据库模型
├── repositories/    # 数据访问层（Repository Pattern）
├── services/        # 业务逻辑层
├── controllers/     # API 路由控制器
├── middlewares/     # 中间件（认证、错误处理）
├── utils/           # 工具函数
├── types/           # Pydantic Schemas
├── main.py          # 应用入口
├── run.sh           # 启动脚本
└── requirements.txt # Python 依赖
```

## 🚀 快速开始

### 1. 启动基础服务

```bash
cd ../docker
docker-compose up -d
```

这将启动：
- PostgreSQL (端口 5433)
- Redis (端口6380)
- MinIO (端口 8999, 控制台 9002)

### 2. 启动后端服务

```bash
cd ../src
./run.sh
```

或手动启动：
```bash
cd src
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

API 服务将运行在：http://localhost:13000

- **API 文档**：http://localhost:13000/api/docs
- **ReDoc**：http://localhost:13000/api/redoc

## ✅ 已实现功能

### 用户认证
- ✅ POST `/api/auth/login` - 用户登录
- ✅ POST `/api/auth/register` - 用户注册
- ✅ GET `/api/auth/me` - 获取当前用户

### 笔记管理
- ✅ GET `/api/notes` - 列表（分页、搜索、筛选）
- ✅ GET `/api/notes/{noteId}` - 获取详情
- ✅ POST `/api/notes` - 创建笔记
- ✅ PATCH `/api/notes/{noteId}` - 更新笔记
- ✅ DELETE `/api/notes/{noteId}` - 删除笔记
- ✅ POST `/api/notes:batchDelete` - 批量删除
- ✅ POST `/api/notes/{noteId}:polish` - AI 润色
- ✅ GET `/api/notes/folders` - 文件夹列表

### 收藏管理
- ✅ GET `/api/favorites` - 列表（类型筛选）
- ✅ POST `/api/favorites` - 添加收藏
- ✅ POST `/api/favorites:toggle` - 一键切换
- ✅ PATCH `/api/favorites/{favoriteId}` - 更新标签
- ✅ DELETE `/api/favorites/{favoriteId}` - 删除收藏

### 其他
- ✅ GET `/api/health` - 健康检查

## 🚧 TODO（待实现）

### 知识库功能（已标记 TODO）
所有知识库相关接口已创建框架，在代码中用 `TODO` 标记待实现：

- [ ] 知识库 CRUD 操作
- [ ] 文档上传至 MinIO
- [ ] 文档解析（PDF, DOCX, Markdown 等）
- [ ] 向量化与存储（需集成 pgvector 或 Milvus）
- [ ] RAG 问答（需集成 LLM API）
- [ ] 文档状态追踪

### 论文广场（已标记 TODO）
- [ ] Hub 模型与 CRUD
- [ ] 帖子管理
- [ ] 订阅关系
- [ ] 搜索与推荐

## 🏗️ 架构设计

### 分层架构
```
Controller → Service → Repository → Model
```

- **Controller**: 处理 HTTP 请求/响应
- **Service**: 业务逻辑实现
- **Repository**: 数据库操作
- **Model**: 数据库模型定义

### 依赖注入
使用 FastAPI 的 `Depends` 机制实现依赖注入。

### 错误处理
统一错误响应格式，参考 `types/schemas.py` 中的 `ErrorResponse`。

## 📚 相关文档

- `../API_SPEC.md` - 完整的 API 接口设计
- `../DB_SCHEMA.md` - PostgreSQL 数据库设计
- `../docker/README.md` - Docker 服务说明

## 🧪 测试

```bash
pytest
pytest --cov=. --cov-report=html
```

## 📝 开发规范

### 代码格式化
```bash
black .
flake8 .
mypy .
```

### Git 提交规范
- feat: 新功能
- fix: 修复
- docs: 文档
- refactor: 重构
- test: 测试

## 🔒 安全注意事项

⚠️ **生产环境部署前必须修改**：
1. `SECRET_KEY` - 使用强随机字符串
2. 所有数据库密码
3. MinIO 访问密钥
4. 启用 HTTPS
5. 配置防火墙规则

## 📄 License

MIT


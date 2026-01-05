# iReader - 智能文档阅读与知识管理系统

iReader 是一个基于 RAG（检索增强生成）技术的智能文档阅读与知识管理平台，帮助用户高效管理、检索和理解文档内容。

## 核心功能

-  **React+PIPELINE的混合智能体** - 基于文献的文献总结，文献对比，文献问答
-  **无视文献数量** -基于任意数量的文献，输出文献综述
-  **MCP** -MCP功能集成，支持MCP服务热插拔
-  **知识库管理** - 创建和管理个人/团队知识库，支持多种文档格式
-  **笔记系统** - 阅读时随手记录，知识沉淀更便捷
-  **收藏功能** - 收藏重要内容，快速回顾
-  **团队协作** - 组织管理与知识共享，支持多人协同
-  **文档预览** - 在线预览 PDF、Word、Markdown 等格式

## 在线体验

🌐 **官网地址**: [https://www.ireader.online](https://www.ireader.online)

## 演示视频

https://github.com/user-attachments/assets/8e33f6db-93df-439e-8b09-3f3bfc0ce8e3

<video src="video.mp4" controls width="100%"></video>

## 快速启动

1. 克隆项目并进入目录
```bash
git clone https://github.com/your-repo/iReader.git
cd iReader
```

2. 配置环境变量
```bash
cp src/.env.template src/.env
cp agent_system/.env.template agent_system/.env
# 编辑 .env 文件，填入必要的 API Key 和配置
```

3. 启动服务
```bash
cd docker
docker-compose up -d
```

4. 访问系统
- 前端: http://localhost
- API 文档: http://localhost:13000/api/docs

## 联系方式

📧 Email: ht20201031@163.com

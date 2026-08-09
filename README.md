# Chaoxing Sign Assistant

一个基于 Vue 3、Flask、MySQL 和 Redis Stream 的课程签到协作原型。

## Architecture

- `frontend/`: Vue 3 + Vite + Element Plus
- `backend/`: Flask API、SQLAlchemy 数据模型和自动签到守护线程
- `Redis`: 按课程隔离生产者心跳与动态 `enc` 消息
- `MySQL`: 用户、课程、成员关系与签到日志

## Local development

1. 从 `backend/.env.example` 创建 `backend/.env`，替换所有示例密钥和密码。
2. 使用 `backend/init.sql` 初始化数据库并安装 `backend/requirements.txt`。
3. 启动 MySQL、Redis 和 Flask 后端。
4. 从 `frontend/.env.example` 创建可选的前端环境配置，然后执行：

```powershell
cd frontend
npm install
npm run dev
```

本地 HTTPS 默认关闭。如需摄像头在非 localhost 地址工作，请通过前端环境变量引用仓库外的证书和私钥，或在反向代理处终止 TLS。

## Security

不要提交 `.env`、TLS 私钥、浏览器抓包、数据库导出或真实学习通 Cookie。生产部署前还需要完成统一 JWT 鉴权、凭据加密、签到幂等和独立 worker 改造。

本项目仅应用于已获授权的学习、研究和系统集成场景，请遵守平台规则和适用法律。

# Chaoxing Sign Assistant

一个基于 Vue 3、Flask、MySQL 和 Redis Stream 的课程签到协作原型。

## Architecture

- `frontend/`: Vue 3 + Vite + Element Plus
- `backend/`: Flask API、SQLAlchemy 数据模型和自动签到守护线程
- `Redis`: 按课程隔离生产者心跳与动态 `enc` 消息
- `MySQL`: 用户、课程、成员关系与签到日志

## Local development

1. 从 `backend/.env.example` 创建 `backend/.env`，替换所有示例密钥和密码。
2. 安装 `backend/requirements.txt`，启动 MySQL/Redis 后在 `backend` 中运行 `alembic upgrade head` 初始化或升级数据库。
3. 启动 Flask v1 兼容层、FastAPI v2、Dispatcher 和至少一个 Worker。
4. 从 `frontend/.env.example` 创建可选的前端环境配置，然后执行：

```powershell
cd frontend
npm install
npm run dev
```

本地 HTTPS 默认关闭。Compose 的 Nginx 在 443 端口终止 TLS；生产证书与私钥必须保存在仓库外，并通过根目录 `.env` 中的 `TLS_CERT_PATH` 和 `TLS_KEY_PATH` 引用。

## Production stack

生产部署使用 `docker-compose.yml`：Nginx、Flask v1 兼容层、两个 FastAPI v2 实例、两个签名 Worker、Outbox Dispatcher、MySQL、Redis AOF、Prometheus/Grafana、Loki/Promtail 和每日异机加密备份。

部署前从 `backend/.env.example` 创建仓库根目录 `.env`，补充 `MYSQL_ROOT_PASSWORD`、`GRAFANA_ADMIN_PASSWORD`、`BACKUP_ENCRYPTION_KEY` 和 `BACKUP_REMOTE`，并从 `deploy/backup/rclone.conf.example` 创建不入库的 `deploy/backup/rclone.conf`。启动顺序：

```bash
docker compose build
docker compose run --rm api-v2-1 alembic upgrade head
docker compose run --rm api-v2-1 python -m v2.migrate_credentials
docker compose up -d
# 配置 rclone.conf 后启用异机备份 profile
docker compose --profile backup up -d backup
```

可用性边界为单机可恢复：容器故障自动拉起；每日备份对应 RPO 24 小时，主机损坏目标 RTO 2 小时。若云平台已经提供 TLS，也可以让独立边缘反向代理替代 Compose Nginx 的证书终止职责。

## Security

不要提交 `.env`、TLS 私钥、浏览器抓包、数据库导出或真实学习通 Cookie。旧数据库首次升级后，应执行凭据迁移命令，并确认所有 Cookie 已转换为 `enc:v1:` 密文再切换生产流量。

本项目仅应用于已获授权的学习、研究和系统集成场景，请遵守平台规则和适用法律。

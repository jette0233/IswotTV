# 恢复演练手册

目标：在一台全新的 Linux 主机上于 2 小时内恢复服务；可接受最多 24 小时数据损失。

1. 安装 Docker Engine、Compose 插件和 Git，克隆仓库固定 release tag。
2. 从密码管理器恢复根目录 `.env`，从安全存储恢复 `deploy/backup/rclone.conf`。
3. 执行 `docker compose up -d mysql redis`，等待健康检查通过。
4. 从对象存储下载最近一个日备份，运行：

```bash
docker compose --profile backup run --rm backup /usr/local/bin/restore.sh /backup/latest.sql.gz.enc
```

5. 执行 `docker compose run --rm api-v2-1 alembic upgrade head`。
6. 执行 `docker compose up -d`，确认 `/health/live` 和 `/health/ready` 返回成功。
7. 检查 Grafana、Worker 心跳、Redis Stream pending 数和最近签到任务。
8. 记录开始时间、恢复完成时间、备份时间点、数据缺口和发现的问题。

每月在隔离主机或临时云主机演练一次，禁止直接覆盖生产数据库。

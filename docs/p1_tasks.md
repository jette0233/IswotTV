# P1 开发任务清单 —— 课堂自动签到助手

---

## 一、整体架构

```
┌─────────────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│  生产者 (教室现场)    │     │  服务端 (轻量云服务器)   │     │  消费者 (远程同学)    │
│                     │     │                      │     │                     │
│  手机/电脑 → 摄像头   │     │  Flask API            │     │  后台守护进程         │
│  对准大屏            │────▶│  MySQL (课程/用户/签到) │◀────│  轮询 → enc → 签到   │
│  解码enc → POST enc  │     │  MQ (按课程隔离)       │     │  全自动，无需人工      │
│  带心跳              │     │  选举 / 20min TTL     │     │                     │
└─────────────────────┘     └──────────────────────┘     └─────────────────────┘
```

---

## 二、P1 功能范围（不做的事）

| 不做 | 原因 |
|------|------|
| ❌ 防作弊滑块验证 | P2处理 |
| ❌ 微信小程序端 | P2处理 |
| ❌ 排行榜/激励/广告 | P1只做功能，产品运营后续 |
| ❌ 批量导入现有课程 | 未知数据源，暂时手动输入 |
| ❌ 多生产者并发 | 选举制，一次只有1个生产者 |

---

## 三、P1 开发阶段

### Phase A：基础设施（2天）

#### A-1 项目骨架搭建
- [ ] 建 Flask 项目结构（app.py, models.py, routes/, services/）
- [ ] 建 Vue 前端项目（Vite + Vue3 + Element Plus 或 Naive UI）
- [ ] 配置 conda chaoxing 环境的 requirements.txt
- [ ] 建 MySQL 数据库，写建表 SQL

#### A-2 数据库模型设计
- [ ] `users` 表：id, nickname, phone, password_encrypted, cookie_manual, cookie_expire_at, created_at
- [ ] `courses` 表：id, course_id(学习通真实courseid), course_name, creator_user_id, is_active, created_at
- [ ] `course_members` 表：id, user_id, course_id, role(producer/consumer), joined_at
- [ ] `sign_logs` 表：id, user_id, course_id, active_id, enc, status(success/fail/expired), message, created_at

#### A-3 基础API
- [ ] `POST /api/auth/register` — 注册（存加密密码）
- [ ] `POST /api/auth/login` — 登录（返回token）
- [ ] `POST /api/auth/login/chaoxing` — 提交学习通Cookie验证（方案2：手动抓Cookie用户）
- [ ] `GET /api/user/cookie/status` — 查看Cookie是否即将过期
- [ ] `POST /api/user/cookie/refresh` — 方案1用户：自动重新登录刷新Cookie

---

### Phase B：核心签到链路（3天）

#### B-1 签到活动生命周期管理
- [ ] `POST /api/course/create` — 创建一个课程签到组
- [ ] `POST /api/course/join` — 加入一个课程
- [ ] `GET /api/course/list` — 查看我的课程列表
- [ ] 服务端MQ管理器（用Redis Stream实现）：
  - [ ] 按 `course_id` 隔离MQ
  - [ ] MQ 创建时设置20min TTL（Redis EXPIRE）
  - [ ] MQ 到期自动删除
  - [ ] 一个course同时只允许一个MQ存活

#### B-2 生产者端（选举制 + 心跳）
- [ ] `POST /api/producer/claim` — 生产者竞选（谁能先推送有效enc，谁当选）
- [ ] `POST /api/producer/heartbeat` — 生产者心跳（每5秒一次，超时15秒自动让出）
- [ ] `POST /api/producer/push-enc` — 推送enc到MQ（只有当前当选生产者能推）
  - 参数：course_id, enc, active_id（解析自二维码）
  - 验证：active_id是否匹配该course_id
- [ ] `GET /api/producer/status` — 查看当前生产者是谁

#### B-3 生产者客户端（Python脚本，教室电脑运行）
- [ ] 摄像头帧采集（OpenCV）
- [ ] 每3秒截一帧（不是每帧解码，降低CPU）
- [ ] pyzbar 解码二维码 → 提取 enc + activeId + courseId
- [ ] 验证courseId匹配目标课程
- [ ] POST 到 `/api/producer/claim` 竞选生产者
- [ ] 当选后：每5秒推enc + 同时发心跳
- [ ] 生产者断开后：自动重新选举

#### B-4 消费者端（全自动签到）
- [ ] 后台守护进程：
  - [ ] 定时（每3秒）轮询 `GET /api/consumer/check-sign?course_id=xxx`
  - [ ] 如果有活跃MQ且有新enc → 取出最新enc
  - [ ] 用自己存的Cookie调用 `stuSignajax` 签到
  - [ ] 记录签到结果到 `sign_logs`
- [ ] 签到失败处理：
  - [ ] "已签到" → 记录但不报错
  - [ ] "enc过期" → 等待下一个enc
  - [ ] "请登录" → Cookie失效，方案1自动重登，方案2推送提醒
  - [ ] 网络错误 → 3秒后重试，最多3次

#### B-5 服务端签到调度API
- [ ] `GET /api/consumer/course-queue?user_id=xxx` — 返回该用户加入的所有课程中，哪些课程当前有活跃MQ
- [ ] `GET /api/consumer/latest-enc?course_id=xxx` — 取出MQ中最新的enc（Redis Stream read）
- [ ] `POST /api/consumer/sign-report` — 汇报签到结果

---

### Phase C：前端界面（2天）

#### C-1 用户端
- [ ] 注册/登录页
- [ ] 课程管理页（创建课程、加入课程、查看已加入课程）
- [ ] 生产者页面：
  - [ ] 启动摄像头按钮
  - [ ] 实时显示当前解码的enc
  - [ ] 显示竞选状态（是否当选生产者）
  - [ ] 心跳状态灯
- [ ] 消费者页面：
  - [ ] 已加入课程列表 + 每个课程的签到状态（未签到/已签到/签到失败）
  - [ ] Cookie管理入口（手动抓Cookie页 / 自动登录提示）
  - [ ] Cookie有效期倒计时

#### C-2 签到历史
- [ ] 签到记录页（按课程分组）
- [ ] 显示签到时间、enc、状态

---

## 四、技术选型备忘

| 组件 | 选择 | 理由 |
|------|------|------|
| 后端框架 | Flask | 轻量，够用，跟用户现有知识栈一致 |
| 前端框架 | Vue3 + Vite | 用户提的 |
| 数据库 | MySQL | 用户提的 |
| 消息队列 | Redis Stream | 天然TTL支持，轻量，不需要额外部署Kafka |
| 生产者脚本 | Python（conda chaoxing） | OpenCV + pyzbar 都在这个环境 |
| 部署 | 轻量云服务器（¥50/月） | Redis + MySQL + Flask 一台够用 |

---

## 五、开发顺序建议

```
第一优先级 ─── Phase A + Phase B-1（基础设施+MQLifecycle）
                ↓
第二优先级 ─── Phase B-2 + B-3（生产者端：选举+推送）
                ↓
第三优先级 ─── Phase B-4 + B-5（消费者端：自动签到）
                ↓
第四优先级 ─── Phase C（前端界面）
```

从后端核心链路开始，所有API先用 Postman/curl 验证，再写页面。**先跑通一条完整链路（1个生产者→MQ→1个消费者签到成功），再往上加花哨功能。**

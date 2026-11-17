# 传感器校准偏差复核

Bootstrap 区间估计的真实业务分析小型项目。完整模拟客户、痛点、上下游、算法公式与一天工作剧本见 [BUSINESS.md](BUSINESS.md)。

## 模块与业务流程
预约调度（两类设备成组占用、清洗与稳定计入占用、停用改期、读数接报、封卷建批）→ 数据接入（JSON/CSV、字段验证、批次指纹）→ 参数化分析（异步 Python worker）→ 结果复核（指标、图形、明细、解释、批准）→ 定时分发（本地收件箱、CSV/JSON、SHA256）；另有业务总览和审计轨迹。
贯穿全栈的实体：Equipment 设备、Booking 校准预约单、Downtime 设备停用、Reading 预约读数、AnalysisBatch 分析批次、Dataset 数据批次、Job 分析任务、Report 分发计划；辅助 User、Audit、Delivery。

### 校准预约调度
- 实验室共用恒温槽（bath）与标准仪（standard），每单**成组占用**两类设备，杜绝分别预约把同一时段排给两批。
- 清洗与稳定时间计入占用：占用区间 = 测量窗口向前顺延清洗+稳定分钟数。
- 预约与既有预约/停用冲突时拒单并返回具体原因（设备、时段、冲突对象）。
- 设备停用撞上未开工预约时整组改期（保持时长与缓冲，14 天内搜索共同空档）；无共同空档转为待重排，可手动重排；已开工的预约留到结束。
- 并发安全：预约、改期、停用按设备行锁（按 id 升序）串行；开工/封卷/接报按预约单行锁互斥；事务中断回滚恢复原单。
- 幂等：预约与停用携带 request_key，重试返回原单不新增占用；唯一约束兜底并发同键落库。
- 读数绑定预约：未开工或设备不符拒收；封卷后晚到读数不改旧卷；封卷与接报并发按先落定者裁决。
- 封卷生成唯一分析批次（batch_no 含预约号，booking_id 唯一约束），同时落成可分析的数据批次；建批中断恢复后重试不重复建批。

## 快速启动
```bash
cp .env.example .env
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```
访问 http://localhost:18206；后端文档 http://localhost:19206/docs；数据库宿主端口 17706。
`SEED_DEMO=true` 自动幂等 seed；不覆盖用户修改。手动 seed 命令可重复执行。

## 演示账号与权限
|账号|密码|真实权限|
|---|---|---|
|admin@demo.local|Demo123!|接入、执行、批准、分发、暂停、读取与下载|
|analyst@demo.local|Demo123!|接入、执行、读取与下载；不能批准或安排分发|
|viewer@demo.local|Demo123!|只读与下载|

## 技术与本地开发
Python 3.12 / FastAPI / SQLAlchemy / NumPy / SciPy / scikit-learn；PostgreSQL 16；Redis 7；Nginx；原生 HTML CSS JavaScript ES modules（用户指定）。后端所有校验、持久化和算法在服务端。无前端打包步骤。
后端：安装 backend/requirements.txt，设置 DATABASE_URL、REDIS_URL、JWT_SECRET、ARTIFACT_DIR 后在 backend/ 执行 `python -m migrations.initial`、`python -m scripts.seed_demo`、`uvicorn src.main:app`，另开 `python -m src.worker`。前端使用带 /api 反向代理的 Nginx，直接打开 index.html 不支持 API。

## 目录与工程约定
backend/src/{models,schemas,services,routes,controllers,middlewares,constants,config,utils}；backend/scripts/seed_demo.py；backend/migrations/initial.py。
frontend/src/{api,stores,types,components/common,hooks,pages,router,utils,constants}。
Role 枚举：admin/analyst/viewer；JobStatus：queued/running/completed/failed；BookingStatus：booked/in_progress/sealed/pending_reschedule；EquipmentKind：bath/standard。后端 backend/src/constants/enums.py，前端 frontend/src/constants/enums.js；路由权限在 middlewares/auth.py；页面按相同角色控制操作入口。

## 环境变量与 Docker
COMPOSE_PROJECT_NAME=sensor-bootstrap；FRONTEND_PORT=18206；BACKEND_PORT=19206；DB_PORT=17706；DB_PASSWORD、JWT_SECRET 见 .env.example；SEED_DEMO 默认 true。共享命名产物卷供后端下载与 worker 写入，数据库/Redis 各持久卷。
恰好五服务均有健康检查。Redis 队列加 SQL 排队状态兜底；worker 按 next_run 生成本地收件箱文件。周期 60 秒至 30 天。分发结果为批准分析的固定快照；若需新数据重新计算并建立新计划。当前不连接邮件或企业聊天。
错误响应、请求编号、Redis 每 IP 每分钟 240 次限流、JWT 和数据库操作审计。演示密钥与密码仅供本机模拟；生产部署前配置独立密钥与账号。

## 数据与验收
所有数据为固定随机种子生成的模拟业务数据，不能作为实际生产决策证据。项目独立算法、输入边界及业务局限详见 BUSINESS.md。测试与截图统一存放 ../../test-artifacts/gb-1007/，源码不含日志/截图/测试报告。
清理本项目演示数据：`docker compose down -v --remove-orphans`（会删除本项目命名卷）。

## License
MIT，见 LICENSE。

# MySQL 算法资源迁移说明

当前迁移会覆盖主要持久业务数据：

- `run:*`：评测运行记录
- `dataset:*`：数据集记录，自动排除扫描缓存与版本辅助键
- `algorithm:*`：平台算法、社区算法、用户算法副本、接入算法副本
- `preset:*`：参数方案
- `metric:*`：自定义指标
- `algorithm_submission:*`：用户算法接入申请与审核状态
- `user:*`：本地用户账号记录
- `comment:*:*:*`：社区评论
- `notice:*:*`：站内通知
- `report:*`：举报处理记录

暂不迁移 Celery 队列状态。Redis 仍继续作为 Celery Broker/Backend 使用，并在迁移期保留镜像与兜底能力。

## 1. 安装依赖

```powershell
pip install -r backend\requirements.txt
```

新增依赖：

- `SQLAlchemy`
- `PyMySQL`

## 2. 创建数据库

在 MySQL 中先创建数据库，字符集建议使用 `utf8mb4`：

```sql
CREATE DATABASE algo_benchmark CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

## 3. 配置连接串

PowerShell 示例：

```powershell
$env:ABP_SQL_STORE_URL="mysql+pymysql://root:password@127.0.0.1:3306/algo_benchmark?charset=utf8mb4"
```

也可以使用兼容变量：

```powershell
$env:ABP_MYSQL_URL="mysql+pymysql://root:password@127.0.0.1:3306/algo_benchmark?charset=utf8mb4"
```

迁移期默认允许 Redis 兜底：

```powershell
$env:ABP_SQL_FALLBACK_REDIS="1"
```

确认 SQL 数据完整后，可以关闭兜底，避免旧 Redis 数据再次影响算法列表：

```powershell
$env:ABP_SQL_FALLBACK_REDIS="0"
```

## 4. 从 Redis 迁移现有数据

先只看数量：

```powershell
python scripts\migrate_algorithms_to_sql.py --dry-run
```

正式写入 MySQL：

```powershell
python scripts\migrate_algorithms_to_sql.py
```

脚本会自动创建当前所需表：

- `abp_algorithms`
- `abp_algorithm_submissions`
- `abp_store_records`

## 5. 当前存储口径

- 算法与算法接入申请：使用专表优先读写 MySQL，同时镜像写入 Redis，迁移期可从 Redis 兜底读取。
- Run、数据集、参数方案、指标、用户、评论、通知、举报：使用 `abp_store_records` 优先读写 MySQL，同时镜像写入 Redis，迁移期可从 Redis 兜底读取。
- Celery 队列状态：继续使用 Redis。

## 6. 日常启动

`scripts\manual_up.ps1` 默认会启动 Redis 和 MySQL，并把 `ABP_SQL_STORE_URL` 注入后端与 Worker 窗口：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\manual_up.ps1
```

如需临时回到纯 Redis 口径：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\manual_up.ps1 -SkipMySQL
```

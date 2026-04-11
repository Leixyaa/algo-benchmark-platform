# MySQL 算法资源迁移说明

本次先迁移最容易出现同步问题的两类数据：

- `algorithm:*`：平台算法、社区算法、用户算法副本、接入算法副本
- `algorithm_submission:*`：用户算法接入申请与审核状态

暂不迁移 Run、日志、Celery 队列状态。Redis 仍继续作为 Celery Broker/Backend 和运行态缓存使用。

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

## 5. 当前存储口径

- 算法与算法接入申请：优先读写 MySQL，同时镜像写入 Redis，迁移期可从 Redis 兜底读取。
- 数据集、指标、Run、用户、日志：暂时仍按原 Redis 口径运行。
- 后续如果继续暴露同步问题，再按风险顺序迁移数据集、指标和用户表。

## 6. 日常启动

`scripts\manual_up.ps1` 默认会启动 Redis 和 MySQL，并把 `ABP_SQL_STORE_URL` 注入后端与 Worker 窗口：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\manual_up.ps1
```

如需临时回到纯 Redis 口径：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\manual_up.ps1 -SkipMySQL
```

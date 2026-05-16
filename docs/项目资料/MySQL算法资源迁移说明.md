# MySQL 资源迁移与存储说明

本项目支持 Redis 与 SQL 存储协同。Redis 继续承担 Celery Broker/Backend 职责；业务资源可写入 SQL，并在迁移期保留 Redis 兜底读取能力。

## 覆盖资源

迁移与持久化主要覆盖：

- `run:*`：评测任务记录
- `dataset:*`：数据集记录
- `algorithm:*`：平台算法、社区算法、用户算法副本
- `preset:*`：运行预设
- `metric:*`：指标记录
- `algorithm_submission:*`：算法接入申请与审核状态
- `user:*`：本地用户账号
- `comment:*:*:*`：社区评论
- `notice:*:*`：站内通知
- `report:*`：举报处理记录
- `feedback:*`：用户反馈记录

Celery 队列状态不迁移，仍由 Redis 管理。

## 依赖

```powershell
python -m pip install -r backend\requirements.txt
```

主要 SQL 相关依赖：

- `SQLAlchemy`
- `PyMySQL`

## MySQL 初始化

建议字符集使用 `utf8mb4`：

```sql
CREATE DATABASE algo_benchmark CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

连接串示例：

```powershell
$env:ABP_SQL_STORE_URL="mysql+pymysql://root:password@127.0.0.1:3306/algo_benchmark?charset=utf8mb4"
```

兼容变量：

```powershell
$env:ABP_MYSQL_URL="mysql+pymysql://root:password@127.0.0.1:3306/algo_benchmark?charset=utf8mb4"
```

迁移期允许 Redis 兜底：

```powershell
$env:ABP_SQL_FALLBACK_REDIS="1"
```

确认 SQL 数据完整后，可关闭兜底：

```powershell
$env:ABP_SQL_FALLBACK_REDIS="0"
```

## 迁移命令

先 dry-run 查看数量：

```powershell
python scripts\migrate_algorithms_to_sql.py --dry-run
```

正式写入：

```powershell
python scripts\migrate_algorithms_to_sql.py
```

脚本会按需创建当前业务表，包括算法、算法接入、任务、数据集、预设、指标、用户、评论、通知、举报、反馈和通用记录表。

## 启动口径

`scripts\manual_up.ps1` 会按当前配置拉起 Redis、后端、Worker 与 Web。若启用 MySQL，请确保连接串已配置，并确认 MySQL 服务可用。

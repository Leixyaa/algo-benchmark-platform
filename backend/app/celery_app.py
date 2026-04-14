from __future__ import annotations

from celery import Celery

CELERY_BROKER_URL = "redis://127.0.0.1:6379/0"
CELERY_RESULT_BACKEND = "redis://127.0.0.1:6379/0"

celery_app = Celery(
    "backend",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
    # Celery 6+ 将改变启动阶段 broker 重试行为；显式开启以保持与当前版本一致
    broker_connection_retry_on_startup=True,
)

# 关键：让 worker 启动时加载任务模块，否则 runs.execute 在 worker 里不会注册。
# 启动命令示例：python -m celery -A app.celery_app.celery_app worker ...
celery_app.conf.imports = ("app.tasks",)
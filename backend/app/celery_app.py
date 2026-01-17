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
)

# ? 关键：让 worker 启动时加载任务模块，否则 runs.execute 在 worker 里不注册
# 你启动命令是：python -m celery -A app.celery_app.celery_app worker ...
celery_app.conf.imports = ("app.tasks",)

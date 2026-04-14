# 项目部署指南

## 1. 环境准备

### 1.1 安装 Python
- 确保安装 Python 3.8 或更高版本
- 推荐使用 Python 3.10+ 以获得最佳性能

### 1.2 安装 Redis
- **Windows**: 使用 Docker 运行 Redis 容器
  - 安装 Docker Desktop
  - 运行命令：`docker run -d -p 6379:6379 --name redis redis:latest`
- **Linux/Mac**: 可直接安装 Redis 或使用 Docker

## 2. 项目部署

### 2.1 克隆代码仓库
```bash
git clone <仓库地址>
cd algo-benchmark-platform
```

### 2.2 安装后端依赖

#### 2.2.1 使用虚拟环境（推荐）
如果项目已经有虚拟环境（.venv目录）：
```bash
cd backend
# Windows
.\.venv\Scripts\pip.exe install -r requirements.txt

# Linux/Mac
source .venv/bin/activate
pip install -r requirements.txt
```

#### 2.2.2 直接安装（不使用虚拟环境）
```bash
cd backend
pip install -r requirements.txt
```

### 2.3 启动服务

#### 2.3.1 启动 Redis（如果未运行）
```bash
# Windows PowerShell
powershell -ExecutionPolicy Bypass -File .\scripts\start_docker_redis.ps1

# 或手动启动 Docker 容器
docker start redis
```

#### 2.3.2 启动后端服务

##### 使用虚拟环境启动
```bash
# Windows
# 启动 API 服务
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 启动 Celery Worker（在另一个终端）
# 单机开多个 worker 且任务偏 CPU 时，可加 --without-gossip --without-mingle，避免误报 missed heartbeat（见 4.5）
.\.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker --loglevel=info

# Linux/Mac
# 激活虚拟环境
source .venv/bin/activate
# 启动 API 服务
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 启动 Celery Worker（在另一个终端）
source .venv/bin/activate
python -m celery -A app.celery_app:celery_app worker --loglevel=info
```

##### 直接启动（不使用虚拟环境）
```bash
# 启动 API 服务
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 启动 Celery Worker（在另一个终端）
python -m celery -A app.celery_app:celery_app worker --loglevel=info
```

#### 2.3.3 启动前端服务
```bash
cd ../web
npm install
npm run dev
```

### 2.4 一键启动（Windows）
```bash
# 一键启动 Redis + 后端服务 + 前端服务
powershell -ExecutionPolicy Bypass -File .\scripts\manual_up.ps1

# 仅启动服务（跳过 Redis）
powershell -ExecutionPolicy Bypass -File .\scripts\manual_up.ps1 -SkipRedis
```

## 3. 验证部署

### 3.1 检查服务状态
- API 文档：`http://127.0.0.1:8000/docs`
- 前端页面：`http://localhost:5173/`

### 3.2 测试功能
1. 访问前端页面
2. 创建一个测试数据集
3. 尝试导入 ZIP 文件
4. 扫描数据集
5. 创建并运行一个算法评测任务

## 4. 常见问题与解决方案

### 4.1 依赖安装失败
- 确保网络连接正常
- 尝试使用国内镜像源：
  ```bash
  # 直接安装
  pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
  
  # 使用虚拟环境
  .\.venv\Scripts\pip.exe install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
  ```
- 确保在正确的环境中安装依赖（虚拟环境或全局环境）

### 4.2 Redis 连接失败
- 检查 Redis 服务是否运行
- 确保 Redis 端口 6379 未被占用
- 检查防火墙设置

### 4.3 端口冲突
- 如果端口 8000 被占用，可修改后端服务端口：
  ```bash
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
  ```
  同时修改前端 API 基础 URL：`web/src/api/http.js` 中的 `API_BASE`

### 4.4 扫描失败
- 确保数据目录结构正确（包含 `gt` 目录和相应的输入目录）
- 检查文件命名是否规范，确保输入文件与 GT 文件能够正确配对
- 查看后端日志以获取详细错误信息

### 4.5 Celery 日志里的 `missed heartbeat from workerX`（INFO）
- **含义**：这是 **Gossip** 机制下，一个 worker 在约定时间内没收到另一个 worker 通过 broker 发来的「同伴心跳」日志，级别多为 **INFO**，**不等于任务失败**。
- **为何在本项目里常见**：`runs.execute` 会做大量图像/算法计算；在 **Windows** 上 worker 常用 **solo** 进程，任务跑起来时主进程忙于 CPU 工作，**处理同伴事件的时机被推迟**，对端就会偶发打出 `missed heartbeat`。
- **何时需要处理**：若任务在平台侧仍正常完成，可忽略；若伴随 worker 崩溃、任务一直卡住再排查进程/内存。
- **开发环境减少误报**（可选）：每个 worker 启动时增加参数，关闭同伴同步（不影响从 Redis 取任务、执行任务）：
  ```bash
  python -m celery -A app.celery_app:celery_app worker --loglevel=info --without-gossip --without-mingle -n worker1@%h
  ```
  另一个终端把 `-n worker1@%h` 改成 `worker2@%h` 等即可。

## 5. 项目结构说明

```
algo-benchmark-platform/
├── backend/            # 后端代码
│   ├── app/            # 应用代码
│   │   ├── vision/     # 视觉算法实现
│   │   ├── main.py     # API 主入口
│   │   ├── tasks.py    # 异步任务
│   │   └── ...         # 其他模块
│   ├── data/           # 数据集存储
│   ├── requirements.txt # 依赖文件
│   └── DEPLOYMENT.md   # 部署文档
├── web/                # 前端代码
│   ├── src/            # 源代码
│   ├── package.json    # 前端依赖
│   └── ...             # 其他文件
├── scripts/            # 启动脚本
└── docs/               # 文档
```

## 6. 技术栈

### 后端
- Python 3.x
- FastAPI
- Celery + Redis
- OpenCV, scikit-image, NumPy, SciPy

### 前端
- Vue 3 + Vite
- Pinia
- Element Plus

## 7. 注意事项

- 确保 Redis 服务始终运行，否则无法创建和执行评测任务
- 数据集导入时，确保 ZIP 文件结构正确，包含 `gt` 目录和相应的输入目录
- 对于大型数据集，扫描和评测可能需要较长时间，请耐心等待
- 定期清理 `backend/data` 目录，避免占用过多磁盘空间

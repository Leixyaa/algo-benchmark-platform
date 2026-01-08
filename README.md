# 算法性能测试平台（图像/视频增强与复原）

## 功能闭环
数据集管理 → 算法库管理 → 发起评测（Run）→ 异步执行（Celery+Redis）→ 指标计算（PSNR/SSIM/NIQE）→ 结果对比/快速推荐 → 导出报告（CSV/Excel）

## 技术栈
- 前端：Vue3 + Vite + Element Plus + ECharts（目录：web/）
- 后端：FastAPI（目录：backend/）
- 异步任务：Celery + Redis（Redis 使用 Docker 容器）

## 本地启动（Windows）
### 1) 启动 Redis（Docker）
```bash
docker run -d --name algo-redis -p 6379:6379 redis:7
```

### 2) 启动后端（FastAPI）
```bash
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

### 3) 启动前端（Vite）
```bash
cd web
npm install
npm run dev
```

### 然后提交推送：
```powershell
git add README.md
git commit -m "文档：补充项目README与启动说明"
git push
```
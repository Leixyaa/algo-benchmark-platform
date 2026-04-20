## 可上传算法填写模板（对应本目录 6 个脚本）

### 1) alg_bm3d_2007_adapter.py
- 适用任务：去噪
- 版本号：v1
- 算法名称：BM3D_2007_Adapter
- 算法说明：基于 BM3D 论文思路的去噪适配算法。优先调用 bm3d 包；若环境缺失则自动回退到 OpenCV FastNLMeans，保证平台可运行与可复现。
- 依赖说明：Python 3.10+; numpy; opencv-python; (可选) bm3d
- 入口说明：单文件脚本入口。命令行: python alg_bm3d_2007_adapter.py --input <input> --output <output> [--sigma 25.0]。支持输入为单图或目录，输出保持同名结构。
- 代码包文件：alg_bm3d_2007_adapter.py

### 2) alg_dcp_2009_adapter.py
- 适用任务：去雾
- 版本号：v1
- 算法名称：DCP_2009_Adapter
- 算法说明：基于 Dark Channel Prior（CVPR 2009）的去雾适配实现，包含暗通道估计、大气光估计、透射率估计与引导滤波细化。
- 依赖说明：Python 3.10+; numpy; opencv-python
- 入口说明：命令行: python alg_dcp_2009_adapter.py --input <input> --output <output> [--patch 15 --omega 0.95 --t0 0.1]。支持单图或目录。
- 代码包文件：alg_dcp_2009_adapter.py

### 3) alg_dncnn_2016_adapter.py
- 适用任务：去噪
- 版本号：v1
- 算法名称：DnCNN_2016_Inspired_Adapter
- 算法说明：DnCNN 论文思路的轻量平台适配版（工程可运行基线），用于统一协议下评测与展示。非官方预训练权重复现版。
- 依赖说明：Python 3.10+; numpy; opencv-python
- 入口说明：命令行: python alg_dncnn_2016_adapter.py --input <input> --output <output> [--strength 0.12]。支持单图或目录。
- 代码包文件：alg_dncnn_2016_adapter.py

### 4) alg_srcnn_2015_adapter.py
- 适用任务：超分
- 版本号：v1
- 算法名称：SRCNN_2015_Inspired_Adapter
- 算法说明：SRCNN 论文思路的轻量平台适配版（双三次放大+锐化基线），用于平台流程联调与统一对比。非官方权重复现版。
- 依赖说明：Python 3.10+; numpy; opencv-python
- 入口说明：命令行: python alg_srcnn_2015_adapter.py --input <input> --output <output> [--scale 2.0 --sharpen 0.25]。支持单图或目录。
- 代码包文件：alg_srcnn_2015_adapter.py

### 5) alg_esrgan_2018_adapter.py
- 适用任务：超分
- 版本号：v1
- 算法名称：ESRGAN_2018_Inspired_Adapter
- 算法说明：ESRGAN 论文思路的轻量平台适配版（x4放大+对比增强+反锐化），用于展示与横向评测。非官方 GAN 权重复现版。
- 依赖说明：Python 3.10+; numpy; opencv-python
- 入口说明：命令行: python alg_esrgan_2018_adapter.py --input <input> --output <output> [--scale 4.0 --clip_limit 2.0]。支持单图或目录。
- 代码包文件：alg_esrgan_2018_adapter.py

### 6) alg_zerodce_2020_adapter.py
- 适用任务：低照增强
- 版本号：v1
- 算法名称：ZeroDCE_2020_Inspired_Adapter
- 算法说明：Zero-DCE 论文思路的轻量平台适配版，采用迭代曲线增强策略，适合低照图像增强演示与平台对比。
- 依赖说明：Python 3.10+; numpy; opencv-python
- 入口说明：命令行: python alg_zerodce_2020_adapter.py --input <input> --output <output> [--alpha 0.16 --iters 8]。支持单图或目录。
- 代码包文件：alg_zerodce_2020_adapter.py

---

说明：
- BM3D 与 DCP 为可直接运行版本（BM3D 无 bm3d 包时会自动回退）。
- DnCNN/SRCNN/ESRGAN/Zero-DCE 当前为论文思路轻量适配版，用于平台联调与展示。
- 若用于严格论文对比，建议替换为官方权重/官方复现版本，并在算法说明中记录权重来源。

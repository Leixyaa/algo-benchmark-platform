# 对比结论（2026-02-14-04-00-38）

- 任务类型：去模糊
- 数据集：ds_gopro_deblur_test
- 仅显示完成：是
- 权重：PSNR=3.5，SSIM=3.5，NIQE=2，耗时=1

## 推荐结论
推荐算法：UnsharpMask(基线) 原因：PSNR 第1，SSIM 第1，NIQE 第1（更低更好），耗时 第2；主要贡献：PSNR(35%) + SSIM(35%) 指标：PSNR=25.305，SSIM=0.7548，NIQE=0.579，耗时=2.605s

## Top 10 算法

| 排名 | 算法 | PSNR | SSIM | NIQE | 耗时 | 评分 | 原因 | RunID |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | UnsharpMask(基线) | 25.305 | 0.7548 | 0.579 | 2.605s | 0.9 | PSNR 第1，SSIM 第1，NIQE 第1（更低更好），耗时 第2；主要贡献：PSNR(35%) + SSIM(35%) | 7de016c856ee |
| 2 | LaplacianSharpen(基线) | 22.826 | 0.6807 | 0.819 | 2.471s | 0.1 | PSNR 第2，SSIM 第2，NIQE 第2，耗时 第1；主要贡献：PSNR(35%) + SSIM(35%) | 3d600f3ac300 |

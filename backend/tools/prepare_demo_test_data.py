import json
import urllib.request
import urllib.error
from pathlib import Path

import cv2
import numpy as np


BASE_URL = "http://127.0.0.1:8000"


def http_json(method: str, path: str, payload=None):
  url = f"{BASE_URL}{path}"
  data = None
  headers = {"Content-Type": "application/json"}
  if payload is not None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
  req = urllib.request.Request(url=url, method=method.upper(), data=data, headers=headers)
  try:
    with urllib.request.urlopen(req, timeout=12) as resp:
      raw = resp.read().decode("utf-8", errors="ignore")
      return resp.status, json.loads(raw) if raw else {}
  except urllib.error.HTTPError as e:
    raw = e.read().decode("utf-8", errors="ignore")
    try:
      body = json.loads(raw) if raw else {}
    except Exception:
      body = {"raw": raw}
    return e.code, body


def ensure_dataset_files(dataset_id: str, count: int = 6):
  root = Path(__file__).resolve().parents[1] / "data" / dataset_id
  gt = root / "gt"
  noisy = root / "noisy"
  hazy = root / "hazy"
  blur = root / "blur"
  dark = root / "dark"
  lr = root / "lr"
  for p in [gt, noisy, hazy, blur, dark, lr]:
    p.mkdir(parents=True, exist_ok=True)

  for i in range(count):
    rng = np.random.default_rng(20260330 + i)
    base = rng.integers(0, 255, size=(256, 256, 3), dtype=np.uint8)
    g = cv2.GaussianBlur(base, (0, 0), 0.8)
    n = np.clip(g.astype(np.int16) + rng.normal(0, 12, size=g.shape), 0, 255).astype(np.uint8)
    h = cv2.addWeighted(g, 0.65, np.full_like(g, 220), 0.35, 0)
    b = cv2.GaussianBlur(g, (0, 0), 1.8)
    d = np.clip(g.astype(np.float32) * 0.4, 0, 255).astype(np.uint8)
    l = cv2.resize(g, (128, 128), interpolation=cv2.INTER_AREA)
    name = f"{i:03d}.png"
    cv2.imwrite(str(gt / name), g)
    cv2.imwrite(str(noisy / name), n)
    cv2.imwrite(str(hazy / name), h)
    cv2.imwrite(str(blur / name), b)
    cv2.imwrite(str(dark / name), d)
    cv2.imwrite(str(lr / name), l)


def ensure_dataset(dataset_id: str, name: str):
  payload = {"dataset_id": dataset_id, "name": name, "type": "图像", "size": "6 张"}
  code, _ = http_json("POST", "/datasets", payload)
  if code not in (200, 201, 409):
    raise RuntimeError(f"创建数据集失败 {dataset_id}: {code}")
  scan_code, scan_body = http_json("POST", f"/datasets/{dataset_id}/scan")
  if scan_code not in (200, 201):
    raise RuntimeError(f"扫描数据集失败 {dataset_id}: {scan_code} {scan_body}")


def ensure_user_algorithm():
  list_code, list_body = http_json("GET", "/algorithms?limit=500")
  if list_code != 200:
    raise RuntimeError(f"读取算法列表失败: {list_code}")
  names = {str(x.get("name") or "") for x in (list_body or [])}
  target_name = "FastNLMeans(基线)（夜景）"
  if target_name in names:
    return
  payload = {
    "task": "去噪",
    "name": target_name,
    "impl": "OpenCV",
    "version": "v1-user",
    "default_params": {
      "nlm_h": 16,
      "nlm_hColor": 16,
      "nlm_templateWindowSize": 7,
      "nlm_searchWindowSize": 21
    }
  }
  code, body = http_json("POST", "/algorithms", payload)
  if code not in (200, 201, 409):
    raise RuntimeError(f"创建用户算法失败: {code} {body}")


def ensure_presets():
  code, presets = http_json("GET", "/presets?limit=500")
  if code != 200:
    raise RuntimeError(f"读取预设失败: {code}")
  exists = {(str(x.get("name") or ""), str(x.get("task_type") or "")) for x in (presets or [])}
  candidates = [
    {
      "name": "去噪-系统默认-演示",
      "task_type": "denoise",
      "dataset_id": "ds_demo_image",
      "algorithm_id": "alg_dn_cnn",
      "metrics": ["PSNR", "SSIM", "NIQE"],
      "params": {
        "nlm_h": 10,
        "nlm_hColor": 10,
        "nlm_templateWindowSize": 7,
        "nlm_searchWindowSize": 21,
        "param_scheme": "default"
      }
    },
    {
      "name": "去噪-夜景方案-演示",
      "task_type": "denoise",
      "dataset_id": "ds_demo_image",
      "algorithm_id": "alg_dn_cnn",
      "metrics": ["PSNR", "SSIM", "NIQE"],
      "params": {
        "nlm_h": 16,
        "nlm_hColor": 16,
        "nlm_templateWindowSize": 7,
        "nlm_searchWindowSize": 21,
        "param_scheme": "user:FastNLMeans(基线)（夜景）",
        "user_scheme_name": "FastNLMeans(基线)（夜景）"
      }
    }
  ]
  for p in candidates:
    key = (p["name"], p["task_type"])
    if key in exists:
      continue
    c, b = http_json("POST", "/presets", p)
    if c not in (200, 201, 409):
      raise RuntimeError(f"创建预设失败: {c} {b}")


def main():
  ensure_dataset_files("ds_demo_image")
  ensure_dataset("ds_demo_image", "演示图像数据集")
  ensure_user_algorithm()
  ensure_presets()
  print("OK: 已准备测试数据（数据集/算法库/预设）")


if __name__ == "__main__":
  main()

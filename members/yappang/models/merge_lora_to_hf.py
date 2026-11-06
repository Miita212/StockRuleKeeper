"""LoRA 어댑터를 Qwen3-8B 베이스에 합쳐 HF 모델 폴더로 저장한다 (yappang 버전).

병준의 finetune_train/merge_lora.py 와 같은 방식(가중치 파일을 하나씩 처리해 메모리를 아낌, W + (B@A)*alpha/r)이다.
다른 점: 베이스를 로컬 폴더(--base-dir)에서 읽고, 합친 층 수가 어댑터 층 수와 다르면 중단하며,
토크나이저·채팅 템플릿은 어댑터 폴더의 것(학습 때 저장한 것)으로 덮어쓴다.

사용 (members/yappang/models 에서):
  ../train_model/.venv/bin/python -I -X utf8 merge_lora_to_hf.py \
      --adapter haechan/qwen3-8b-v3-2ep-haechan --base-dir base/Qwen3-8B --out haechan/merged-v3-2ep
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import torch
from safetensors import safe_open
from safetensors.torch import load_file, save_file

ap = argparse.ArgumentParser()
ap.add_argument("--adapter", required=True)
ap.add_argument("--base-dir", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()

adapter_dir, base_dir, out_dir = Path(a.adapter), Path(a.base_dir), Path(a.out)
out_dir.mkdir(parents=True, exist_ok=True)

cfg = json.load(open(adapter_dir / "adapter_config.json", encoding="utf-8"))
if cfg["base_model_name_or_path"] != "Qwen/Qwen3-8B":
    sys.exit(f"[중단] 어댑터 베이스가 Qwen/Qwen3-8B 가 아니다: {cfg['base_model_name_or_path']}")
scale = cfg["lora_alpha"] / cfg["r"]
lora = load_file(adapter_dir / "adapter_model.safetensors")

# 어댑터 키: base_model.model.<층 이름>.lora_A.weight / lora_B.weight  ->  베이스 키: <층 이름>.weight
pairs = {}
for key in lora:
    if ".lora_A." in key:
        name = key.replace("base_model.model.", "").split(".lora_A.")[0]
        pairs[name + ".weight"] = (key, key.replace(".lora_A.", ".lora_B."))
print(f"어댑터 층 {len(pairs)}개, scale {scale}", flush=True)

dev = "cuda" if torch.cuda.is_available() else "cpu"
merged = 0
shards = sorted(base_dir.glob("*.safetensors"))
if not shards:
    sys.exit(f"[중단] 베이스 가중치가 없다: {base_dir}")
for shard in shards:
    tensors = {}
    with safe_open(shard, "pt") as f:
        for name in f.keys():
            w = f.get_tensor(name)
            if name in pairs:
                x, y = pairs[name]
                delta = lora[y].to(dev).float() @ lora[x].to(dev).float() * scale
                w = (w.to(dev).float() + delta).to(torch.bfloat16).cpu()
                merged += 1
            tensors[name] = w
    save_file(tensors, out_dir / shard.name, metadata={"format": "pt"})
    print(shard.name, "완료", flush=True)

if merged != len(pairs):
    sys.exit(f"[중단] 합친 층 {merged}개 != 어댑터 층 {len(pairs)}개 (키 이름이 베이스와 안 맞음)")
print(f"합친 층 {merged}개 / 어댑터 층 {len(pairs)}개 OK")

for f in base_dir.glob("*"):
    if f.is_file() and f.suffix in (".json", ".txt", ".jinja"):
        shutil.copy(f.resolve(), out_dir / f.name)
for name in ("tokenizer.json", "tokenizer_config.json", "chat_template.jinja"):  # 학습 때 저장한 것으로 덮어쓰기
    if (adapter_dir / name).exists():
        shutil.copy(adapter_dir / name, out_dir / name)
print("저장:", out_dir)

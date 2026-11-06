"""LoRA 어댑터를 베이스 모델(Qwen3-8B)에 합쳐 HF 모델 폴더로 저장한다 (메모리 절약: 가중치 파일 하나씩 처리).

사용:
    python merge_lora.py --adapter runs/v1 --out ~/llm_models/qwen3-8b-byungjun-merged
(adapter 폴더에는 adapter_model.safetensors 와 adapter_config.json 이 있어야 한다)
"""
import argparse
import json
import shutil
from pathlib import Path

import torch
from huggingface_hub import snapshot_download
from safetensors import safe_open
from safetensors.torch import load_file, save_file

ap = argparse.ArgumentParser()
ap.add_argument("--adapter", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--base", default="Qwen/Qwen3-8B")
args = ap.parse_args()

adapter_dir, out_dir = Path(args.adapter), Path(args.out)
base_dir = Path(snapshot_download(args.base, allow_patterns=["*.safetensors", "*.json", "*.txt", "*.jinja"]))
out_dir.mkdir(parents=True, exist_ok=True)

cfg = json.load(open(adapter_dir / "adapter_config.json"))
scale = cfg["lora_alpha"] / cfg["r"]
lora = load_file(adapter_dir / "adapter_model.safetensors")

# 어댑터 키: base_model.model.<층 이름>.lora_A.weight / lora_B.weight  →  베이스 키: <층 이름>.weight
pairs = {}
for key in lora:
    if ".lora_A." in key:
        name = key.replace("base_model.model.", "").split(".lora_A.")[0]
        pairs[name + ".weight"] = (key, key.replace(".lora_A.", ".lora_B."))

merged = 0
for shard in sorted(base_dir.glob("*.safetensors")):
    tensors = {}
    with safe_open(shard, "pt") as f:
        for name in f.keys():
            w = f.get_tensor(name)
            if name in pairs:
                a, b = pairs[name]
                delta = lora[b].to("cuda").float() @ lora[a].to("cuda").float() * scale
                w = (w.to("cuda").float() + delta).to(torch.bfloat16).cpu()
                merged += 1
            tensors[name] = w
    save_file(tensors, out_dir / shard.name, metadata={"format": "pt"})
    print(shard.name, "완료", flush=True)

print(f"합친 층 {merged}개 / 어댑터 층 {len(pairs)}개")
for f in base_dir.glob("*"):
    if f.suffix in (".json", ".txt", ".jinja"):
        shutil.copy(f.resolve(), out_dir / f.name)

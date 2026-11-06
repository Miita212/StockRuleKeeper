"""학습한 LoRA → 원본과 병합 → GGUF(Q4_K_M, Q8_0) + Ollama Modelfile.

사용법 (서버):
  python export.py --adapter outputs/run1/best
결과 (outputs/export/):
  qwen3-8b-stockrule-Q4_K_M.gguf  + Modelfile        ← 노트북으로 가져갈 것 (약 5GB)
  qwen3-8b-stockrule-Q8_0.gguf    + Modelfile.q8     ← 비교용 (약 9GB)
  merged/, *-bf16.gguf                               ← 중간 파일 (가져갈 필요 없음, 지워도 됨)

llama.cpp 는 tools/llama.cpp 에 처음 한 번 받고, 4비트 압축 도구(llama-quantize)만 CPU용으로 빌드한다.
"""
import argparse
import os
import subprocess
import sys

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

parser = argparse.ArgumentParser()
parser.add_argument("--base", default="models/Qwen3-8B")
parser.add_argument("--adapter", required=True)
parser.add_argument("--out", default="outputs/export")
parser.add_argument("--name", default="qwen3-8b-stockrule")
parser.add_argument("--llama_cpp", default="tools/llama.cpp")
args = parser.parse_args()

# common.py 의 학습 형식과 같다: 메시지마다 <|im_start|>역할\n내용<|im_end|>\n,
# 마지막에 assistant 시작 + 빈 think 블록(enable_thinking=False 와 같은 모양)
TEMPLATE = """{{- range .Messages }}<|im_start|>{{ .Role }}
{{ .Content }}<|im_end|>
{{ end }}<|im_start|>assistant
<think>

</think>

"""


def run(cmd, **kwargs):
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True, **kwargs)


os.makedirs(args.out, exist_ok=True)
merged_dir = f"{args.out}/merged"
bf16_gguf = f"{args.out}/{args.name}-bf16.gguf"

# 1) 병합 (GPU 를 학습에 쓰는 중이어도 되게 CPU 에서) -----------------------------
print("===== 1. LoRA 병합 =====")
model = AutoModelForCausalLM.from_pretrained(args.base, dtype=torch.bfloat16, device_map="cpu")
model = PeftModel.from_pretrained(model, args.adapter).merge_and_unload()
model.save_pretrained(merged_dir)
AutoTokenizer.from_pretrained(args.base).save_pretrained(merged_dir)
del model

# 2) llama.cpp 준비 -------------------------------------------------------------
print("===== 2. llama.cpp 준비 =====")
if not os.path.exists(args.llama_cpp):
    run(["git", "clone", "--depth", "1", "https://github.com/ggml-org/llama.cpp", args.llama_cpp])
quantize_bin = f"{args.llama_cpp}/build/bin/llama-quantize"
if not os.path.exists(quantize_bin):
    run(["cmake", "-B", "build", "-DGGML_CUDA=OFF", "-DLLAMA_CURL=OFF"], cwd=args.llama_cpp)
    run(["cmake", "--build", "build", "--target", "llama-quantize", "-j"], cwd=args.llama_cpp)

# 3) GGUF 변환 (bf16) → 압축 ------------------------------------------------------
print("===== 3. GGUF 변환·압축 =====")
env = {**os.environ, "PYTHONPATH": f"{args.llama_cpp}/gguf-py"}
run([sys.executable, f"{args.llama_cpp}/convert_hf_to_gguf.py", merged_dir,
     "--outtype", "bf16", "--outfile", bf16_gguf], env=env)
for quant in ["Q4_K_M", "Q8_0"]:
    run([quantize_bin, bf16_gguf, f"{args.out}/{args.name}-{quant}.gguf", quant])

# 4) Ollama Modelfile -----------------------------------------------------------
print("===== 4. Modelfile =====")
for filename, quant in [("Modelfile", "Q4_K_M"), ("Modelfile.q8", "Q8_0")]:
    with open(f"{args.out}/{filename}", "w", encoding="utf-8") as f:
        f.write(f"FROM ./{args.name}-{quant}.gguf\n")
        f.write(f'TEMPLATE """{TEMPLATE}"""\n')
        f.write('PARAMETER stop "<|im_end|>"\n')
        f.write("PARAMETER temperature 0\n")
        f.write("PARAMETER num_ctx 4096\n")

print(f"\n완료. 노트북으로 가져갈 것: {args.out}/{args.name}-Q4_K_M.gguf, {args.out}/Modelfile")

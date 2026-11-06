#!/bin/bash
# LoRA 어댑터를 Qwen3-8B에 합쳐 Ollama 모델로 등록한다 (어댑터 갈아끼우기).
# 순서: 합치기(merge_lora.py) → GGUF 변환 → Q4_K_M 압축 → ollama create → 중간 파일 삭제
#
# 사용:
#     bash swap_adapter.sh <어댑터 폴더> [Ollama 모델 이름]
#     bash swap_adapter.sh ~/adapters/teammate qwen3-8b-stockrule
# 어댑터 폴더에는 adapter_model.safetensors 와 adapter_config.json 이 있어야 한다.
# 어댑터는 Qwen/Qwen3-8B 기준으로 학습한 것이어야 한다.
# 같은 이름으로 다시 실행하면 그 이름의 Ollama 모델을 덮어쓴다. (qwen3:8b 원본은 건드리지 않는다)
set -e

ADAPTER=$(realpath "$1")
NAME=${2:-qwen3-8b-stockrule}
LLM=/home/ai/llm_models
PY=/home/ai/miniconda3/envs/llm-torch/bin/python
HERE=$(dirname "$(realpath "$0")")

$PY "$HERE/merge_lora.py" --adapter "$ADAPTER" --out "$LLM/merged_tmp"
$PY "$LLM/llama.cpp/convert_hf_to_gguf.py" "$LLM/merged_tmp" --outtype bf16 --outfile "$LLM/bf16_tmp.gguf"
"$LLM/llama.cpp/build/bin/llama-quantize" "$LLM/bf16_tmp.gguf" "$LLM/$NAME-Q4_K_M.gguf" Q4_K_M

ollama show qwen3:8b --modelfile | sed -E "s#^FROM .*#FROM $LLM/$NAME-Q4_K_M.gguf#" > "$LLM/Modelfile.$NAME"
ollama create "$NAME" -f "$LLM/Modelfile.$NAME"

rm -rf "$LLM/merged_tmp" "$LLM/bf16_tmp.gguf"
echo "완료: ollama 모델 '$NAME' 등록됨"

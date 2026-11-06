#!/usr/bin/env bash
# 서버(4090)에서 한 번만 실행: 환경 확인 → conda 환경 생성 → 설치 → Qwen3-8B 다운로드
# 사용법 (finetune 폴더 안에서):
#   bash setup.sh               # 전부
#   bash setup.sh --skip-model  # 모델 다운로드 생략 (models/Qwen3-8B 를 직접 옮겨 온 경우)
set -euo pipefail
cd "$(dirname "$0")"

ENV_NAME="srk-ft"
MODEL_ID="Qwen/Qwen3-8B"
MODEL_DIR="models/Qwen3-8B"
SKIP_MODEL=0
[[ "${1:-}" == "--skip-model" ]] && SKIP_MODEL=1

echo "===== [1/5] 서버 환경 확인 ====="
echo "- OS: $(grep PRETTY_NAME /etc/os-release 2>/dev/null | cut -d= -f2)"
echo "- 남은 디스크(이 폴더): $(df -h . | awk 'NR==2{print $4}')   (필요: 약 60GB = 원본 16 + 병합 16 + GGUF 5·9 + 체크포인트)"
if command -v nvidia-smi >/dev/null; then
  nvidia-smi --query-gpu=index,name,memory.used,memory.total,driver_version --format=csv
  echo "- 지금 GPU를 쓰는 프로세스:"; nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader || true
else
  echo "!! nvidia-smi 없음 — GPU 드라이버 확인 필요"; exit 1
fi
for t in git cmake gcc make tmux; do
  if command -v $t >/dev/null; then echo "- $t: 있음"; else echo "!! $t: 없음 (GGUF 변환에 git·cmake·gcc·make 필요, tmux 는 권장)"; fi
done
if curl -s -m 5 -o /dev/null -w "%{http_code}" https://huggingface.co | grep -q "200\|301\|302"; then
  echo "- 인터넷(huggingface.co): 됨"
else
  echo "!! huggingface.co 접속 안 됨 — GUIDE.md '인터넷이 안 될 때' 참고"
fi

echo "===== [2/5] conda 환경 '$ENV_NAME' ====="
if ! command -v conda >/dev/null; then
  for p in ~/miniforge3 ~/miniconda3 ~/anaconda3 /opt/conda; do [[ -f $p/etc/profile.d/conda.sh ]] && source $p/etc/profile.d/conda.sh && break; done
fi
command -v conda >/dev/null || { echo "!! conda 없음 — GUIDE.md 'conda가 없을 때' 참고"; exit 1; }
source "$(conda info --base)/etc/profile.d/conda.sh"
if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  echo "- 이미 있음, 그대로 사용"
else
  conda create -y -n "$ENV_NAME" python=3.11
fi
conda activate "$ENV_NAME"

echo "===== [3/5] 패키지 설치 (수 분 걸림) ====="
pip install --upgrade pip
# torch: 기본은 PyPI 최신(CUDA 13용). 드라이버가 오래돼 [4/5]에서 cuda_available: False 가 나오면
#   pip install torch --index-url https://download.pytorch.org/whl/cu128   처럼 드라이버에 맞는 버전으로 다시 설치
pip install torch
pip install -r requirements.txt

echo "===== [4/5] 설치 확인 ====="
mkdir -p outputs
python - <<'PY' | tee outputs/env_versions.txt
import importlib, torch
for m in ["torch","transformers","peft","bitsandbytes","accelerate","datasets"]:
    try: print(f"{m}=={importlib.import_module(m).__version__}")
    except Exception as e: print(f"{m}: 실패 {e}")
print("cuda_available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu:", torch.cuda.get_device_name(0), "| bf16:", torch.cuda.is_bf16_supported())
PY
pip freeze > outputs/pip_freeze.txt

echo "===== [5/5] 모델 다운로드: $MODEL_ID → $MODEL_DIR ====="
if [[ $SKIP_MODEL == 1 ]]; then
  echo "- 생략(--skip-model)"
elif [[ -f "$MODEL_DIR/config.json" ]] && ls "$MODEL_DIR"/*.safetensors >/dev/null 2>&1; then
  echo "- 이미 있음"
else
  hf download "$MODEL_ID" --local-dir "$MODEL_DIR"
fi
ls -lh "$MODEL_DIR" | head -20 || true

echo
echo "완료. 다음: conda activate $ENV_NAME && python preflight.py"

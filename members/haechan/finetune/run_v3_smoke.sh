#!/bin/bash
# 시험 학습: 새 병합본(S1·S2 포함)으로 100스텝, group_by_length 끔 → 평가셋 111건 평가
cd "$(dirname "$0")"
PY=~/ft-env/bin/python
OUT=runs/qwen3-8b-v3-smoke-haechan
mkdir -p "$OUT" runs/eval_v3_smoke-haechan
$PY -X utf8 -u train_qlora.py --out "$OUT" --epochs 1 --max-steps 100 --eval-steps 50 --batch 2 --accum 8 > "$OUT/train.log" 2>&1 || { echo "학습 실패"; exit 1; }
$PY -X utf8 -u eval_model.py --out runs/eval_v3_smoke-haechan --variants v3smoke-haechan=$OUT > runs/eval_v3_smoke-haechan/eval.log 2>&1 || { echo "평가 실패"; exit 1; }
echo "ALL_DONE"

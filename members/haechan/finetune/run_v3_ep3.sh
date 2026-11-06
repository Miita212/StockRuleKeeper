#!/bin/bash
# 3에폭 마무리: checkpoint-704 에서 1056 까지 이어서 학습 → checkpoint-1056 평가
cd "$(dirname "$0")"
FROM=704 ./run_v3_full.sh resume || exit 1
OUT=runs/qwen3-8b-v3-haechan
[ -d "$OUT/checkpoint-1056" ] || { echo "checkpoint-1056 없음"; ls "$OUT"; exit 1; }
mkdir -p runs/eval_v3-3ep-haechan
~/ft-env/bin/python -X utf8 -u eval_model.py --out runs/eval_v3-3ep-haechan --variants v3-3ep-haechan=$OUT/checkpoint-1056 > runs/eval_v3-3ep-haechan/eval.log 2>&1 || { echo "평가 실패"; exit 1; }
echo "ALL_DONE"

#!/bin/bash
# 1에폭 시험: data_v2 로 학습한 뒤, 만들어진 체크포인트를 평가셋 111건으로 평가한다 (기준선은 runs/eval/base.jsonl 재사용).
cd "$(dirname "$0")"
PY=~/ft-env/bin/python
OUT=runs/qwen3-8b-v2-1ep
mkdir -p "$OUT" runs/eval_v2
$PY -X utf8 -u train_qlora.py --train data_v2/train.jsonl --val data_v2/val.jsonl --out "$OUT" --epochs 1 --batch 2 --accum 8 > "$OUT/train.log" 2>&1 || { echo "학습 실패"; exit 1; }
VARS=""
for d in $(ls -d $OUT/checkpoint-* | sort -t- -k2 -n); do
  VARS="$VARS v2_$(basename $d | sed 's/checkpoint-//')=$d"
done
$PY -X utf8 -u eval_model.py --out runs/eval_v2 --variants $VARS > runs/eval_v2/eval.log 2>&1 || { echo "평가 실패"; exit 1; }
echo "ALL_DONE"

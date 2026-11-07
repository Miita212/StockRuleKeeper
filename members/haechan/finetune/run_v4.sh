#!/bin/bash
# v4: data_v5(data_v4 + 되살린 4행 + data_aug 보강)로 3에폭, 설정은 v3와 같음. 체크포인트 전부 남김.
# 끝나면 1·2·3에폭(362·724·1089스텝, 저장이 181스텝마다라 1·2에폭은 1스텝 전 체크포인트)을 공식 평가셋 111건과 시험 test_haechan 58건으로 평가.
cd "$(dirname "$0")"
PY=~/ft-env/bin/python
OUT=runs/qwen3-8b-v4-haechan
ARGS="--out $OUT --train data_v5/train.jsonl --val data_v5/val.jsonl --epochs 3 --batch 2 --accum 8 --keep-ckpts 10"
mkdir -p "$OUT"
if [ "$1" = "resume" ]; then
  $PY -X utf8 -u train_qlora.py $ARGS --resume "$OUT/checkpoint-$FROM" >> "$OUT/train.log" 2>&1 || { echo "학습 실패"; exit 1; }
else
  $PY -X utf8 -u train_qlora.py $ARGS > "$OUT/train.log" 2>&1 || { echo "학습 실패"; exit 1; }
fi
echo "학습 끝, 평가 시작"
V="v4-1ep-haechan=$OUT/checkpoint-362 v4-2ep-haechan=$OUT/checkpoint-724 v4-3ep-haechan=$OUT/checkpoint-1089"
mkdir -p runs/eval_v4-haechan test_haechan/eval_v4-haechan
$PY -X utf8 -u eval_model.py --out runs/eval_v4-haechan --variants $V > runs/eval_v4-haechan/eval.log 2>&1 || { echo "공식 평가 실패"; exit 1; }
$PY -X utf8 -u eval_model.py --data test_haechan/test_haechan.jsonl --out test_haechan/eval_v4-haechan --variants $V > test_haechan/eval_v4-haechan/eval.log 2>&1 || { echo "시험 평가 실패"; exit 1; }
echo "ALL_DONE"

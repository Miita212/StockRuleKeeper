#!/bin/bash
# v7: data_v7(data_v6 + aug7 보강 300행)으로 3에폭. 설정은 v5와 같음(group_by_length 끔).
# 에폭당 394스텝(학습 샘플 6,298 / 16) → 체크포인트 394·788·1182(=1·2·3에폭).
# 끝나면 공식 111·시험 58·시험 v5 31건·시험 v7(있으면)으로 평가하고, 비교용으로 v5 3에폭도 새 시험에 돌린다.
cd "$(dirname "$0")"
PY=~/ft-env/bin/python
OUT=runs/qwen3-8b-v7-haechan
ARGS="--out $OUT --train data_v7/train.jsonl --val data_v7/val.jsonl --epochs 3 --batch 2 --accum 8 --eval-steps 394 --keep-ckpts 10"
mkdir -p "$OUT"
if [ "$1" = "resume" ]; then
  $PY -X utf8 -u train_qlora.py $ARGS --resume "$OUT/checkpoint-$FROM" >> "$OUT/train.log" 2>&1 || { echo "학습 실패"; exit 1; }
else
  $PY -X utf8 -u train_qlora.py $ARGS > "$OUT/train.log" 2>&1 || { echo "학습 실패"; exit 1; }
fi
echo "학습 끝, 평가 시작"
V="v7-1ep-haechan=$OUT/checkpoint-394 v7-2ep-haechan=$OUT/checkpoint-788 v7-3ep-haechan=$OUT/checkpoint-1182"
B="v5-3ep-haechan=runs/qwen3-8b-v5-3ep-haechan"
mkdir -p runs/eval_v7-haechan test_haechan/eval_v7-haechan test_haechan/eval_v5_set-v7-haechan
$PY -X utf8 -u eval_model.py --out runs/eval_v7-haechan --variants $V > runs/eval_v7-haechan/eval.log 2>&1 || { echo "공식 평가 실패"; exit 1; }
$PY -X utf8 -u eval_model.py --data test_haechan/test_haechan.jsonl --out test_haechan/eval_v7-haechan --variants $V > test_haechan/eval_v7-haechan/eval.log 2>&1 || { echo "시험 평가 실패"; exit 1; }
$PY -X utf8 -u eval_model.py --data test_haechan/test_haechan_v5.jsonl --out test_haechan/eval_v5_set-v7-haechan --variants $V > test_haechan/eval_v5_set-v7-haechan/eval.log 2>&1 || { echo "시험 v5 평가 실패"; exit 1; }
if [ -f test_haechan/test_haechan_v7.jsonl ]; then
  mkdir -p test_haechan/eval_v7_set-haechan
  $PY -X utf8 -u eval_model.py --data test_haechan/test_haechan_v7.jsonl --out test_haechan/eval_v7_set-haechan --variants $V $B > test_haechan/eval_v7_set-haechan/eval.log 2>&1 || { echo "시험 v7 평가 실패"; exit 1; }
fi
echo "ALL_DONE"

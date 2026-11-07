#!/bin/bash
# v5: data_v6(data_v5 + 부등호 라벨 39행 + aug6 보강 247행)으로 3에폭. 설정은 v3·v4와 같음(group_by_length 끔).
# 에폭당 377스텝(학습 샘플 6,028 / 16) → 체크포인트 377·754·1131(=1·2·3에폭). 끝나면 공식 111·시험 58·시험 v5 31건으로 평가하고,
# 비교용으로 v4 3에폭도 시험 v5 31건에 돌린다.
cd "$(dirname "$0")"
PY=~/ft-env/bin/python
OUT=runs/qwen3-8b-v5-haechan
ARGS="--out $OUT --train data_v6/train.jsonl --val data_v6/val.jsonl --epochs 3 --batch 2 --accum 8 --eval-steps 377 --keep-ckpts 10"
mkdir -p "$OUT"
if [ "$1" = "resume" ]; then
  $PY -X utf8 -u train_qlora.py $ARGS --resume "$OUT/checkpoint-$FROM" >> "$OUT/train.log" 2>&1 || { echo "학습 실패"; exit 1; }
else
  $PY -X utf8 -u train_qlora.py $ARGS > "$OUT/train.log" 2>&1 || { echo "학습 실패"; exit 1; }
fi
echo "학습 끝, 평가 시작"
V="v5-1ep-haechan=$OUT/checkpoint-377 v5-2ep-haechan=$OUT/checkpoint-754 v5-3ep-haechan=$OUT/checkpoint-1131"
mkdir -p runs/eval_v5-haechan test_haechan/eval_v5-haechan test_haechan/eval_v5_set-haechan
$PY -X utf8 -u eval_model.py --out runs/eval_v5-haechan --variants $V > runs/eval_v5-haechan/eval.log 2>&1 || { echo "공식 평가 실패"; exit 1; }
$PY -X utf8 -u eval_model.py --data test_haechan/test_haechan.jsonl --out test_haechan/eval_v5-haechan --variants $V > test_haechan/eval_v5-haechan/eval.log 2>&1 || { echo "시험 평가 실패"; exit 1; }
$PY -X utf8 -u eval_model.py --data test_haechan/test_haechan_v5.jsonl --out test_haechan/eval_v5_set-haechan --variants $V v4-3ep-haechan=runs/qwen3-8b-v4-3ep-haechan > test_haechan/eval_v5_set-haechan/eval.log 2>&1 || { echo "시험 v5 평가 실패"; exit 1; }
echo "ALL_DONE"

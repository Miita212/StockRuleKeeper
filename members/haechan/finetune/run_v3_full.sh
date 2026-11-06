#!/bin/bash
# 본 학습: 새 병합본, 3에폭 일정으로 시작 → 1에폭 체크포인트(352스텝)가 저장되면 멈추고 평가.
# 이어서 학습: ./run_v3_full.sh resume   (같은 설정으로 checkpoint-352 부터 끝까지)
cd "$(dirname "$0")"
PY=~/ft-env/bin/python
OUT=runs/qwen3-8b-v3-haechan
STOP=352
ARGS="--out $OUT --epochs 3 --batch 2 --accum 8"
mkdir -p "$OUT" runs/eval_v3-haechan
if [ "$1" = "resume" ]; then
  $PY -X utf8 -u train_qlora.py $ARGS --resume "$OUT/checkpoint-$STOP" >> "$OUT/train.log" 2>&1 || { echo "학습 실패"; exit 1; }
  echo "ALL_DONE"; exit 0
fi
$PY -X utf8 -u train_qlora.py $ARGS > "$OUT/train.log" 2>&1 &
PID=$!
# 체크포인트 저장이 끝날 때까지(trainer_state.json 생성) 기다린 뒤 멈춘다
while kill -0 $PID 2>/dev/null; do
  [ -f "$OUT/checkpoint-$STOP/trainer_state.json" ] && { sleep 60; kill $PID; wait $PID; break; }
  sleep 30
done
[ -d "$OUT/checkpoint-$STOP" ] || { echo "체크포인트 $STOP 없음 (학습 실패?)"; tail -5 "$OUT/train.log"; exit 1; }
echo "1에폭에서 멈춤, 평가 시작"
$PY -X utf8 -u eval_model.py --out runs/eval_v3-haechan --variants v3-1ep-haechan=$OUT/checkpoint-$STOP > runs/eval_v3-haechan/eval.log 2>&1 || { echo "평가 실패"; exit 1; }
echo "ALL_DONE"

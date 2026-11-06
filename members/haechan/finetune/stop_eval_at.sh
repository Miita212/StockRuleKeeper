#!/bin/bash
# 학습 중인 runs/qwen3-8b-v3-haechan 에서 checkpoint-<STEP> 이 저장되면 학습을 멈추고 그 체크포인트를 평가한다.
# 사용: ./stop_eval_at.sh 704 v3-2ep-haechan     이어서 학습: FROM=704 ./run_v3_full.sh resume
cd "$(dirname "$0")"
STEP=$1; NAME=$2
PY=~/ft-env/bin/python
OUT=runs/qwen3-8b-v3-haechan
until [ -f "$OUT/checkpoint-$STEP/trainer_state.json" ]; do
  pgrep -f "^$HOME/ft-env/bin/python -X utf8 -u train_qlora.py --out $OUT" >/dev/null || { echo "학습 프로세스가 없음 (checkpoint-$STEP 전에 끝남?)"; exit 1; }
  sleep 30
done
sleep 60
PID=$(pgrep -f "^$HOME/ft-env/bin/python -X utf8 -u train_qlora.py --out $OUT")
[ -n "$PID" ] && kill $PID && while kill -0 $PID 2>/dev/null; do sleep 2; done
echo "checkpoint-$STEP 에서 멈춤, 평가 시작"
mkdir -p runs/eval_$NAME
$PY -X utf8 -u eval_model.py --out runs/eval_$NAME --variants $NAME=$OUT/checkpoint-$STEP > runs/eval_$NAME/eval.log 2>&1 || { echo "평가 실패"; exit 1; }
echo "ALL_DONE"

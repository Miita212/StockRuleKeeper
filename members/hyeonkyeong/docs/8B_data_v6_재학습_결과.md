# Qwen3-8B data_v6 재학습 결과 (hyeonkyeong, 2026-11-09)

해찬 `data_v6`로 Qwen3-8B를 처음부터 다시 학습했다. 해찬 v5(같은 데이터·같은 설정)를 직접 재현하는 것이 목적이었다.
결과: 공식 111문제 점수가 해찬 v5와 항목마다 1문제 안쪽으로 같다. **v5를 다시 만든 것으로 본다.**

## 1. 요약

| 항목 (공식 111문제, 3에폭) | 해찬 v5 | 이번 학습 | 차이 |
|---|---|---|---|
| JSON 유효율 | 100 | 100 | 같음 |
| 응답 유형 일치 (추출/되묻기/거절) | 99.1 | 98.2 | 1문제 |
| **추출 전체 일치 (67건)** | 97.0 | **95.5** | 1문제 |
| 추출 필드 정확도 | 99.9 | 99.9 | 같음 |
| 추출 사용자 지정 지표 정확도 | 97.5 | 96.2 | |
| 기본값이 바뀐 지표 수 (합) | 1 | 2 | |
| 되묻기 판단 (30건) | 100 | 100 | 같음 |
| 되묻기 사유 일치 | 86.7 | 83.3 | 1문제 |
| 되묻기 대상 지표 일치 | 83.3 | 80.0 | 1문제 |
| **거절 정확도 (14건)** | 92.9 | **85.7** | 1문제 |
| 불필요한 되묻기·거절 (추출 건 중) | 0 | 0 | 같음 |

- 차이는 모두 1문제씩이다. GPU 계산의 미세한 비결정성과 라이브러리 버전 차이로 생기는 범위로 본다. 거절은 14건뿐이라 1문제만 달라도 7%p가 움직인다.
- 같은 데이터·같은 설정이어도 가중치가 비트 단위로 같게 나오지는 않는다. 성능이 같은지는 위 점수와 val loss로 판단했다.

## 2. 에폭별 결과

val loss (1·2·3에폭):

| | 1에폭 | 2에폭 | 3에폭 |
|---|---|---|---|
| 해찬 v5 | 0.0168 | 0.0079 | 0.0067 |
| 이번 학습 | 0.0170 | 0.0079 | **0.0063** |

공식 111문제:

| 항목 | 1에폭 | 2에폭 | 3에폭 | (해찬 v5 3에폭) |
|---|---|---|---|---|
| 응답 유형 일치 | 91.0 | 97.3 | 98.2 | 99.1 |
| 추출 전체 일치 (67건) | 65.7 | 94.0 | 95.5 | 97.0 |
| 추출 필드 정확도 | 87.3 | 99.8 | 99.9 | 99.9 |
| 추출 사용자 지정 지표 정확도 | 71.2 | 95.0 | 96.2 | 97.5 |
| 기본값이 바뀐 지표 수 (합) | 8 | 3 | 2 | 1 |
| 되묻기 판단 (30건) | 96.7 | 96.7 | 100.0 | 100.0 |
| 되묻기 사유 일치 | 73.3 | 83.3 | 83.3 | 86.7 |
| 되묻기 대상 지표 일치 | 66.7 | 83.3 | 80.0 | 83.3 |
| 거절 정확도 (14건) | 92.9 | 85.7 | 85.7 | 92.9 |
| 불필요한 되묻기·거절 | 11.9 | 0.0 | 0.0 | 0.0 |

- 2에폭은 이번 학습이 해찬 v5 2에폭보다 좋았다(추출 전체 일치 94.0 vs 86.6). 둘 다 3에폭이 가장 좋아서 **쓸 모델은 3에폭**이다.

## 3. 어떻게 학습했나

### 데이터
`data_v6`의 jsonl은 저장소에 없어서(용량), 해찬 스크립트로 다시 만들었다. 순서:

```bash
# members/haechan/finetune 에서 (저장소 구조 그대로 필요)
python3 -X utf8 data_v5/build_v5.py      # data_v4 + byungjun/finetune_merged → data_v5
python3 -X utf8 data_aug/gen_aug_v6.py   # aug6 보강 247행 (hyeonkyeong/data/eval_*.jsonl 111건 필요)
python3 -X utf8 data_v6/build_v6.py      # → data_v6/train.jsonl, val.jsonl
```

- 결과 train 5,603 / val 319대화(학습 샘플 6,028), `EDIT_LOG_v6.csv`가 저장소의 것과 같다 → 해찬 v5와 같은 데이터.
- 필요한 입력: `haechan/finetune/data_v4/`, `byungjun/finetune_merged/`, `hyeonkyeong/data/eval_*.jsonl`.

### 학습 설정 (해찬 `run_v5.sh`와 같음)
- 코드: `members/haechan/finetune/train_qlora.py` (group_by_length 끔)
- `--epochs 3 --batch 2 --accum 8 --eval-steps 377 --keep-ckpts 10`, lr 1e-4, LoRA r32/α64, seed 42, 1,131스텝
- 처음에 `--batch 4 --accum 4`로 시도했으나 9스텝에서 CUDA OOM(24GB) → 2×8로 다시 함.
- `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` (메모리 배치만 바꾸고 계산에는 영향 없음)

### 환경
- 서버 ws6 (RTX 4090 24GB), 학습 2시간 5분, 스텝당 약 6.7초, VRAM 약 18GB
- conda env: Python 3.11, torch 2.11.0+cu128, **transformers 4.57.6**, peft 0.21.2, bitsandbytes 0.50.2, accelerate 1.15.0
  - 해찬 `train_qlora.py`는 `group_by_length` 인자를 `TrainingArguments`에 직접 넘겨서 transformers 5.x에서는 오류가 날 수 있다 → 4.x로 설치.

### 평가
- `members/haechan/finetune/eval_model.py` 기본 세트(공식 111문제 `hyeonkyeong/data/eval_*.jsonl`), 해찬 v5와 같은 채점.
- `eval_model.py`는 few-shot 기준선용으로 `byungjun/finetune_merged/train.jsonl`을 읽으므로 그 파일도 같이 있어야 한다.

## 4. 어댑터 위치

- ws6 `~/stock-rule-keeper/members/haechan/finetune/runs/qwen3-8b-v6data-hyeonkyeong/`
  - 폴더 맨 위 = 최종 어댑터(val loss 최저 = 3에폭)
  - `checkpoint-377`, `checkpoint-754`, `checkpoint-1131` = 1·2·3에폭
- 문제별 채점 결과: 같은 폴더의 `runs/eval_v6data-hyeonkyeong/` (`hk-1ep.jsonl`·`hk-2ep.jsonl`·`hk-3ep.jsonl`, `summary.json`)
- 가중치(약 349MB)는 git에 올리지 않는다. 필요하면 hyeonkyeong에게 요청.

## 5. 다음

- 이 3에폭 어댑터로 앱의 로컬 모델(지금은 해찬 v3 2에폭)을 바꿀 수 있다(GGUF Q4_K_M 변환 → Ollama `qwen3-8b-stockrule` 재등록).
- yappang 통합 데이터 fixed-4(8B·4B 공용)로 8B 학습 결과: [8B_fixed4_학습_결과.md](8B_fixed4_학습_결과.md) (추출은 이 3에폭이 앞섬 → 앱 모델 유지)

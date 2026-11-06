# Qwen3-8B 파인튜닝 자료 v1.0 (hyeonkyeong, 2026-11-06)

FR-01 "말 번역기"(자연어 원칙 → 지표 20개 JSON, 되묻기, 추천 거절, 용어 설명) QLoRA 학습 자료다.
4090 서버에서 실제로 돌린 코드·데이터·결과를 그대로 모았다. 실행 순서는 `GUIDE.md`를 본다.

## 들어 있는 것

| 경로 | 내용 |
|---|---|
| `GUIDE.md` | 실행 가이드 11단계 (서버 이동 → 학습 → 평가 → GGUF → Ollama) |
| `setup.sh`, `requirements.txt` | conda 환경 `srk-ft` + 패키지 + Qwen3-8B 다운로드 |
| `common.py`, `preflight.py`, `train.py`, `evaluate.py`, `export.py` | 샘플 만들기·점검·학습·평가·내보내기 |
| `data/` | train 2,090 / val 111 (병준 `finetune_merged`), eval 111 (현경 평가셋) |
| `results_8b/` | 서버 실행 결과 (아래) |

모델 가중치·체크포인트·LoRA 어댑터는 크기 때문에 넣지 않았다. 필요하면 현경에게 요청한다.

## 8B 실행 결과 (RTX 4090, 2026-11-05)

- 환경: torch 2.15.0+cu132, transformers 5.17.0, peft 0.21.2, bitsandbytes 0.50.2 (`results_8b/env_versions.txt`)
- 사전 점검: train 2,515샘플 / val 135샘플, 잘림 0건, 마스크 이상 0건 (`preflight.log`)
- 학습 전 점수 (`eval_base/summary.json`): json_valid 97.3%, 나머지(type·anchor·clarify·refusal) 모두 0%
- 본 학습 4에폭 632스텝: 54.7분, 스텝당 5.2초, 최대 VRAM 20.2GB (`run1.log`, `run1_log_history.json`)

| step | 에폭 | val loss |
|---|---|---|
| 79 | 0.5 | 0.379 |
| 158 | 1.0 | 0.145 |
| 316 | 2.0 | 0.043 |
| 474 | 3.0 | 0.029 |
| 553 | 3.5 | 0.026 |
| 632 | 4.0 | 0.0256 (best) |

학습 후 체크포인트 평가(GUIDE 8단계) 결과와 원인 분석은 `REVIEW.md`에 있다. 지표 변환 정확도가 0%라 v1으로는 GGUF를 만들지 않고, S1·S2 데이터를 더해 v2로 다시 학습한다.

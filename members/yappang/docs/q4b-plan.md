# Q4B 트랙 (Qwen3-4B 파인튜닝)

작성 기준: 2026-11-06. 작성: yappang. 팀 프로젝트(Qwen3-8B, 공동)와 **별개로** 진행하는 시연용 트랙이다(팀 합의). 약칭 "Q4B", 결과물 이름 `q4b-v1`.
경로는 `members/yappang/train_model_q4b/` 기준이다. 8B 절차는 `finetune-procedure.md`를 본다.

## 1. 상태 요약

| 항목 | 상태 |
|---|---|
| 환경(.venv), 학습·평가 스크립트 | 완료 (4060 노트북에서 동작 확인) |
| 데이터 | 원본은 병준 최종 병합본과 동일(train 5,202 / val 275 대화, sha256 일치 확인). **2026-11-08 부등호·조사 오류를 고친 수정본(train 5,175 / val 270)을 학습 기본값으로 지정**, 원본은 `train_model_q4b/data/backup/`. 파일·해시·변경 이력은 `train_model_q4b/data/DATA_VERSION.md` |
| 스모크 테스트(20스텝) | 통과. 8분, 스텝당 19초, VRAM 7.9/8.2GB, loss 0.74→0.36 |
| 학습 전 기준선(`--tag base`) | JSON 99.1%, 형태 0%, 필드 0/80, 은어 0/14, 완전일치 0% |
| **본 학습** | **완료(2026-11-08 기준). 다른 컴퓨터에서 학습했다** |
| 평가·GGUF 변환 | 완료. 산출물은 `train_model_q4b/deploy/q4b-v1/`(GGUF Q8_0, Modelfile, 시험판 README, SHA256SUMS). 평가 수치는 그 README에 있다 |
| Ollama 연동(`LLM_PROVIDER=local`) | 시험판 README 기준 백엔드와 실제로 연결해 호출한 적은 아직 없다 |

## 2. 목표와 평가 기준 (Q4B 자체 기준)

Q4B는 팀과 별개 트랙이라 **평가 기준을 직접 정해도 된다**는 합의가 있다. 평가 세트는 8B와 같은 `hyeonkyeong/data/eval_*.jsonl` 111문항이다(추출 67 / 되묻기 30 / 거절 14, 학습 데이터와 겹침 0건).

`scripts/eval_q4b.py`가 계산하는 지표 (greedy, `enable_thinking=False`, `max_new_tokens=900`)

| 지표 | 정의 | 목표 |
|---|---|---|
| JSON 유효율 | 출력이 JSON으로 파싱되는 비율 | 99% |
| 형태 일치율 | 최상위 키 집합이 정답과 같은 비율(변환·되묻기·거절 구분) | |
| 필드 정확도 | 정답의 `source=user` 지표에 대해 id·operator·value·unit 전부 일치한 비율 | 90% |
| 은어 변환율 | kind에 별칭·오타·구어가 든 문항의 완전일치율 | 90% |
| 완전일치율 | 파싱한 JSON이 정답과 완전히 같은 비율(병준 eval.py와 같은 기준) | |

- `max_new_tokens=900` 유지. 정답 최대 620토큰, 학습 답변 최대 687토큰이라 900이면 충분하다(2026-11-06 측정). 8B와 직접 비교할 때만 `--max-new 1200`으로 따로 돌린다.
- **8B 쪽 지표와 정의가 다르다.** 숫자를 나란히 놓을 때는 어느 정의인지 함께 적는다.

| 출처 | "필드 정확도"의 의미 |
|---|---|
| Q4B `eval_q4b.py` | 사용자가 말한 지표만, 4개 필드 전부 일치(엄격) |
| haechan `eval_model.py` | 정답의 모든 지표(default 포함)를 필드 단위로 비교 → 후하게 나옴(v3 시험 91.1%). 가장 가까운 지표는 "사용자 지정 지표 정확도"(v3 시험 16.2%, 병준 v1 35.0%) |
| hyeonkyeong `eval.py` | `anchor_exact`, `all20_exact`, `type_correct` 등 별도 정의 |

## 3. 학습 구성

`scripts/train_qlora.py` (haechan 스크립트를 복사해 4B·transformers 5.x용으로 수정)

| 항목 | 값 |
|---|---|
| 모델 | `Qwen/Qwen3-4B`, QLoRA(nf4 + double quant, bf16) |
| LoRA | r32, alpha 64, dropout 0.05, q/k/v/o/gate/up/down |
| 학습률 | 1e-4 코사인, warmup 5% |
| 배치 | 1 x 누적 16 (8GB 기준). VRAM이 더 큰 PC면 `--batch`·`--accum`을 조정(유효 배치 16 유지) |
| 길이 | `--max-len 1280`(데이터 최대 1,180토큰) |
| 에폭 | 기본 3. 줄이는 안은 4절 |
| 기타 | paged_adamw_8bit, gradient checkpointing, 시드 42, `group_by_length` 없음 |

- 학습 샘플은 assistant 턴마다 하나씩이라 원본 5,202대화 → 5,627샘플, 수정본 5,175대화 → 5,600샘플이다. 질문은 loss에서 제외하고 답 + `<|im_end|>`만 학습한다.
- `group_by_length`를 쓰지 않는다. haechan이 8B v1·v2의 한 유형 쏠림 원인으로 찾은 옵션이다(`haechan/finetune/results/RESULTS.md` 6절).
- 학습 중 다른 GPU 작업(Ollama 등)을 하지 않는다. 4060 8GB에서는 VRAM이 7.9/8.2GB로 빠듯했다.

## 4. 학습 시간과 줄이는 안

시간은 샘플 수가 아니라 **토큰 수**에 비례한다(4060 기준 샘플당 약 1.2초).

| 구성 | 시간(4060 기준) |
|---|---|
| 전체 데이터, 3에폭 | 약 5.6~6시간 (1,055스텝 x 19초 + 평가·저장) |
| **전체 데이터, 2에폭 (A)** | **약 3.8시간** (권장 기본) |
| 2에폭 + S4와 S1 되묻기를 절반으로 (D) | 약 3.0시간 |

- 2에폭이 3에폭보다 나은 근거는 8B 기록이다. 병준 v1은 eval_loss가 2에폭 0.041, 2.5에폭 0.032로 개선 폭이 작았고, haechan v3은 100스텝만으로 필드 정확도 91%였다.
- **에폭은 처음부터 `--epochs 2`로 지정한다.** 코사인 스케줄이 `--epochs` 기준이라, 3에폭 일정으로 돌리다 중간에 멈추면 학습률이 충분히 줄지 않는다.
- 유형별 토큰 비중: S1 36%, S2 17.5%, S3 17%, S4 20%, S5·S6·S7 합 6%, SEED 3%.
  - S4(수정 요청)는 입력에 현재 원칙 JSON 20개가 통째로 들어가 길지만 학습 대상인 답(`changes`)은 짧다. 줄이기 좋은 후보이나 평가셋에 없어 점수로 확인할 수 없다.
  - S3(다중 턴), S5·S6·S7은 줄이지 않는다(시간 절감이 작거나 기능 손실이 크다).
- 데이터 첫 답 유형이 되묻기(약 2,084)에 치우쳐 있어(지표 JSON 약 1,440, 거절 약 414) S1 되묻기를 줄이면 균형이 낫다. 다만 "되묻기 판단" 정확도가 떨어질 위험이 있다.
- 줄일 때는 유형별 층화 추출·시드 고정으로 `data/train_sub.jsonl`을 따로 만들고 원본은 보존한다.
- 최종 구성은 **A(전체 데이터, 2에폭)로 확정**했다(2026-11-06). 다른 컴퓨터에서 본 학습을 진행했고 완료됐다(2026-11-08 기준).

## 5. 다른 컴퓨터로 옮겨 학습할 때 (본 학습은 이 절차로 다른 컴퓨터에서 이미 완료됨, 재학습·재현용)

`members/yappang/.venv`, `outputs/`, `data/*.jsonl`은 gitignore라 저장소에 없다. 다른 PC에서는 다음을 준비한다.

1. 저장소를 받는다(`git pull`). 스크립트는 `train_model_q4b/scripts/`에 있다.
2. **데이터**: `members/byungjun/finetune_merged/train.jsonl`, `val.jsonl`이 `train_model_q4b/data/`와 같은 파일이다. `train_model_q4b/data/`에 복사하거나 `--train`·`--val`로 경로를 준다.
3. **환경**: 파이썬 3.12 가상환경에 `requirements.lock.txt`(검증된 버전: torch 2.11+cu128, transformers 5.22.1, peft 0.21.2, trl 1.17.1, bitsandbytes 0.50.2)를 설치한다. `torch==2.11.0+cu128`은 PyPI에 없으므로 `pip install --extra-index-url https://download.pytorch.org/whl/cu128 -r requirements.lock.txt`처럼 PyTorch 인덱스를 추가한다. 다른 CUDA 버전이면 torch 휠을 맞춘다. `requirements.txt`는 하한 버전만 적은 간이본이다.
4. **모델**: Hugging Face에서 `Qwen/Qwen3-4B`(약 8GB)를 자동으로 받는다.
5. **GPU에 맞게 조정**: 16GB 이상이면 `--batch 2 --accum 8` 등으로 속도를 올릴 수 있다(유효 배치 16 유지). 시간은 다시 잰다.
6. 먼저 `--dry-run`으로 샘플 수(수정본 기준 5,600, 원본 5,627)와 `<|im_end|>` 종료 샘플 전부 여부를 확인한 뒤, `--max-steps 20` 스모크로 스텝 시간·VRAM을 본다.
7. 본 학습 명령(에폭 2안): `python -I -X utf8 scripts/train_qlora.py --epochs 2 --out outputs/q4b-v1`
8. 학습 후: `python -I -X utf8 scripts/eval_q4b.py --adapter outputs/q4b-v1 --tag q4b-v1`
9. 어댑터(`adapter_model.safetensors`)와 결과는 **커밋하지 않는다**(팀 규칙: 대용량·모델 파일 제외). 노트북으로는 파일을 직접 옮긴다.

## 6. 학습 전 점검 결과 (2026-11-06)

- 환경: import와 CUDA 정상. 디스크 여유 766GB. Qwen3-4B 캐시 있음.
- 데이터: `train_model_q4b/data`가 `byungjun/finetune_merged/`와 sha256까지 동일. 평가 문장은 train·val과 겹치지 않음. system 프롬프트 2종, 평가는 그중 JSON 변환용 1종. train·val 사용자 문장이 19건 겹침(영향 작음).
- 비JSON 답변 630건은 S6(399)·S7(200)이라 정상이다.
- 8B 기록과 비교한 주의: 학습 후 **유형별 오답 분포**(정답 유형 → 모델이 고른 유형)를 반드시 확인한다. 8B v1·v2는 평균 loss가 낮아도 한 유형으로 쏠렸다.

## 7. 학습 후 할 일

학습·평가·GGUF 변환(Q8_0)은 끝났다(2026-11-08 기준). 남은 일은 다음과 같다.

1. 8B(병준 v1, haechan v3)와 정의를 명시해 비교한다.
2. Ollama 등록 → `LLM_PROVIDER=local`로 앱 연동. 시험판 README에 설치 절차가 있고, 백엔드와 실제 호출한 적은 아직 없다.
3. 선택: few-shot 기준선, H7 검수 반영.

## 8. 관련 파일

| 파일 | 내용 |
|---|---|
| `train_model_q4b/scripts/train_qlora.py` | 학습 |
| `train_model_q4b/scripts/eval_q4b.py` | 평가(위 2절 지표) |
| `train_model_q4b/scripts/token_stats.py` | 토큰 길이 분포 |
| `train_model_q4b/scripts/merge_train_sets.py` | 데이터 병합(byungjun 최종 병합 코드와 같은 규칙, `--compare`로 해시 비교. 병준 병합본과 완전히 같은 결과를 재현함을 확인) |
| `data/S-1_gen_s1_s2_pass.jsonl` | `gen_s1_s2_pass.jsonl`의 ID 이름 복사본(내용 동일). 원본은 byungjun 병합 코드가 읽으므로 유지. 복사본은 gitignore라 저장소에 없을 수 있어, `merge_train_sets.py`는 복사본이 없으면 원본을 읽고 둘이 다르면 중단함 |
| `train_model_q4b/scripts/merge_train_data.py` | 예전 복사본. S1·S2의 "기존과 첫 질문이 같으면 제외" 규칙이 없어 5,209/276이 나옴(병준 최종은 5,202/275). 쓰지 않음 |
| `train_model_q4b/requirements.lock.txt` | 검증된 라이브러리 버전 |
| `byungjun/finetune_merged/` | 학습 데이터 원본(최종 병합본) |
| `hyeonkyeong/data/eval_*.jsonl` | 평가 111문항 |
| `haechan/finetune/results/RESULTS.md` | 8B 결과, `group_by_length` 원인 |

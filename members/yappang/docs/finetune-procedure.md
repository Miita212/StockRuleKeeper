# 파인튜닝 절차

작성 기준: 2026-11-05 (같은 날 병준 명세 변경·팀 확정 사항 반영). 상태: **제안 + 진행 기록**. 학습은 아직 한 번도 돌리지 않았다.
경로는 별도 표시가 없으면 `members/` 기준이다. 다른 팀원 폴더의 파일은 읽기만 했다. 병준 = byungjun.
개발 완료 마감은 **2026-11-08(일)**, 11/09~10은 시연영상·결과물이다(병준 명세 12절).

## 1. 목적과 대상

- 기반 모델: `Qwen/Qwen3-8B` (Hugging Face), 방식은 QLoRA(4비트 nf4 + double quant, 계산 bf16).
- 모델이 하는 일은 사용자의 말을 **지표 20개 JSON으로 바꾸는 "말 번역기"**와 쉬운 설명(용어 답변, 설명 말풍선)이다. 종합 리포트 글쓰기는 Claude API가 하며 이 모델의 일이 아니다. (출처: `byungjun/finetune_merged/파인튜닝_설정값_명세.md`)
- 사고 모드는 끈다(`enable_thinking=False`). 학습과 추론에서 같은 방식으로 채팅 템플릿을 적용한다.

## 2. 먼저 알아둘 사실

1. **이 PC(RTX 4060 Laptop 8GB)에서는 학습할 수 없다.** 학습 스크립트(`haechan/finetune/`)는 4090(24GB) 또는 4080 Super(16GB)의 Windows PowerShell용이다. 이 PC는 데이터 생성과 추론용이다.
2. `yappang/data/S-4_gen_s6_s7.jsonl`(S6 420건, S7 210건)은 이미 병합본에 들어 있다. 건수가 병합본의 S6(399+21), S7(200+10)과 일치한다.
3. **병합본에는 S1·S2가 없다.** 병합본 README에 "S1·S2 학습 데이터(`gen_s1_s2.jsonl`)는 아직 없다"고 적혀 있다. 지금 "말 → 지표 JSON" 학습은 시드 195건에 의존한다.
   - 병준 명세는 S1·S2를 "사용자 확인으로 지금은 없어도 되는 것"으로 정했다. 다만 **은어 변환율 90% 성공 기준에는 이 데이터가 필요해 공백**이라고 적었다. 지금 생성 중인 S1·S2가 그 공백을 메운다.
4. Ollama의 `qwen3:8b`는 추론용 파일이라 학습에 쓸 수 없다. 학습에는 Hugging Face에서 가중치(약 16GB)를 새로 받는다.

## 3. 학습 데이터 구성

현재 병합본: `byungjun/finetune_merged/train.jsonl` 2,090건, `val.jsonl` 111건. 한 줄은 `{"messages": [system, user, assistant, ...]}`이다.

| type | 내용 | 담당·원본 | train | val |
|---|---|---|---|---|
| SEED | 시드 | haechan `seed_*.jsonl` | 195 | 12 |
| S3 | 되묻기(다중 턴) | hyeonkyeong `gen_s3.jsonl` | 340 | 18 |
| S4 | 기존 규칙 수정 | hyeonkyeong `gen_s4_s5.jsonl` | 665 | 35 |
| S5 | 거절 | hyeonkyeong `gen_s4_s5.jsonl` | 291 | 15 |
| S6 | 쉬운 설명 | `S-4_gen_s6_s7.jsonl` | 399 | 21 |
| S7 | 설명(확인 질문 답) | `S-4_gen_s6_s7.jsonl` | 200 | 10 |
| **S1·S2** | 원칙 해석 변형 / 복수 지표·모호 표현 | **yappang (생성 중, 4절 참고)** | 0 | 0 |

system 프롬프트는 2종(JSON 변환용 / 쉬운 설명용)이며 글자 그대로 쓴다. 평가 세트(`hyeonkyeong/data/eval_*.jsonl`)는 학습에 쓰지 않는다.

## 4. 단계별 절차

### 4-1. S1·S2 생성 (yappang, 이 PC)

입력은 `yappang/data/gen_prompts/out/`의 프롬프트다. S1 336개(seed 191, with_value 69, no_value 60, refusal_seed 16), S2 75개(multi_value 60, ambiguous 15)로 모두 411개다.

```
cd members/yappang/data/gen_prompts
python3 -I run_local_model.py --backend openai --base-url http://localhost:11434/v1 \
    --model qwen3:8b --out raw_outputs.jsonl          # 전체 생성 (끊겨도 같은 명령으로 이어서 실행)
python3 -I assemble_s1_s2.py --raw raw_outputs.jsonl --out ../gen_s1_s2.jsonl
python3 -I <haechan/data/validate_data.py> --master-dir <byungjun/data> --input ../gen_s1_s2.jsonl
python3 -I make_h7_review.py --input ../gen_s1_s2.jsonl --range 1-7 --out ../H7-a_review_1-7.csv   # 8-13, 14-20도 같음
```

- 팀 결정(D6)에 따라 학습 데이터 생성은 **로컬 모델로만** 한다. 외부 LLM(Claude 포함)은 쓰지 않는다. 실행기는 localhost가 아닌 주소를 거부한다.
- **모델 선택 기록 (시험 생성 10개)**

| 모델 | 속도 | 조립 결과 | 비고 |
|---|---|---|---|
| exaone3.5:2.4b | 프롬프트당 약 6.6초 | 통과 23, 거부 52, 파싱 불가 145줄 | 코드블록·여러 줄 JSON·잘못된 필드. 문장이 설명문 같고 같은 문장이 반복됨. 사용하지 않음 |
| **qwen3:8b** | 프롬프트당 약 27초 | **통과 99, 거부 19, 파싱 불가 2줄** | 문장 99개가 모두 서로 다름. 채택 |

- qwen3:8b 전체 생성은 프롬프트당 약 31초로 진행 중이다(64/411 시점에 33분 경과, 남은 예상 약 3시간). 총 약 3.5시간으로 본다. 시험(10개)에서 잰 27초보다 느리다. 일부 S2 문장이 "…만족해야 한다"처럼 딱딱하므로 H7 검수에서 표본을 확인한다.
- 출력(`raw_*.jsonl`, `gen_*.jsonl`)은 `members/*/data/`가 gitignore 대상이라 커밋되지 않는다.
- 알려진 제한: 후보 지표가 5개 이상인 모호 표현은 H3-0 정책상 2단계 되묻기 대화로 만들어야 해서 단발 샘플로는 버려진다. 거절 시드 변형(S5)은 hyeonkyeong의 S5 생성과 범위가 겹칠 수 있다.

### 4-2. 병합 (byungjun 담당)

- `byungjun/finetune_merged/merge_train_data.py`에 `gen_s1_s2.jsonl`을 추가해 다시 병합한다. byungjun 폴더는 yappang이 수정하지 않으므로 byungjun에게 요청한다.
- 병합 시 평가 세트와 겹치는 문장을 제외하고, 같은 시드의 변형은 학습과 평가 한쪽에만 둔다(V9).
- 병합본 검증은 `locked` 메타를 붙여서 한다(`train.jsonl`만 따로 넣으면 V5가 실패한다).

### 4-3. 학습 PC 환경 점검

학습 PC로 `finetune_merged/`(train, val)와 `haechan/finetune/`를 옮긴다. PowerShell에서:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup_check.ps1 -DataDir "C:\...\finetune_merged"
```

GPU, 파이썬 3.10~3.12, 디스크 여유 25GB 이상(모델 약 17GB + 결과 2GB)을 점검하고 `ft-env` 가상환경을 만든다. 결과는 `setup_log.txt`에 남는다.

### 4-4. 사전 점검 (학습 전 필수, GPU 불필요)

```powershell
python -X utf8 train_qlora.py --dry-run
```

- 토큰 길이 분포와 길이 초과로 버려지는 샘플 수를 확인한다(`--max-len` 기본 2048).
  - 병준 명세에서 `max_seq_len` 2,048은 **재검토 필요**로 바뀌었다(팀 메모는 512~1024). 잘리는 샘플이 1건이라도 있으면 JSON이 중간에 끊긴 채 학습되므로, 길이 분포를 보고 4,096으로 늘릴지 해당 샘플을 손볼지 정한다.
- 마스크 샘플 5건(S3 다중 턴 포함)을 출력해 assistant 답변만 학습되는지 눈으로 확인한다.
- 정답이 `<|im_end|>`로 끝나는 샘플이 전부인지 확인한다.

### 4-5. 스모크 테스트

```powershell
python -X utf8 train_qlora.py --max-steps 50 --out runs/smoke
```

스텝당 시간, 최대 VRAM, loss 하락을 본다. 전체 시간은 `스텝당 시간 × 총 스텝`으로 어림한다.

### 4-6. 본 학습

```powershell
.\run_train.ps1 -DataDir "C:\...\finetune_merged" -Name qwen3-8b-v1 -Epochs 3
```

| 항목 | 값 |
|---|---|
| 학습률 | 1e-4 (코사인). 불안정하면 5e-5, 느리면 2e-4 |
| LoRA | rank 32, alpha 64, dropout 0.05, 7개 층 전부 |
| 유효 배치 | 16 (VRAM 22GB 이상이면 4×누적4, 아니면 2×누적8을 스크립트가 자동 선택) |
| 에폭 | 목표 3, 최대 4 |
| 평가·저장 | 0.5에폭마다. `load_best_model_at_end`로 val loss 최저 체크포인트 선택 |
| 기타 | paged_adamw_8bit, gradient checkpointing 켬, packing 끔, 시드 42 |

- 학습 중 PC가 절전에 들어가거나 Windows에서 로그아웃하지 않아야 한다.
- 진행 확인: `Get-Content .\runs\qwen3-8b-v1\train.log -Tail 20 -Wait`
- 학습 샘플은 assistant 턴마다 하나씩 만들어지므로 에폭당 스텝 수는 명세의 131보다 많아질 수 있다.

### 4-7. 평가

- 평가 세트를 **모델이 직접 생성**하게 해서 JSON 유효율, 지표 정확도(id·부등호·값·단위·source), 되묻기 판단, 거절 정확도, 잠금(locked) 보존을 비교한다. 생성은 JSON은 temperature 0, 설명은 0.3~0.5.
- **비교 대상은 학습 전 Qwen3-8B의 few-shot**이다(기획 확정 방식. 이전 명세의 zero-shot에서 바뀜).
- **목표치(기획 확정)**: JSON 유효율 99%, 필드 정확도 90%, 은어 변환율 90%. 미달하면 few-shot으로 선회한다.
  - 은어 변환율은 S1·S2(은어 데이터)가 병합본에 없으면 충분히 측정·학습할 수 없다. S1·S2를 병합한 뒤에 평가해야 의미가 있다.
- **평가 환경(기획 확정)**: 노트북 4060에서 **GGUF 4비트 상태**로 평가한다. 따라서 GGUF 변환과 Ollama 등록(4-8)이 평가보다 먼저 필요하다.
- 설명(S6·S7)은 추천·예측·보장 표현이 없는지 사람이 표본으로 확인한다.
- 위 평가를 실행하는 스크립트는 확인한 범위에서 아직 없다.

### 4-8. 배포 (이 PC)

LoRA 병합 → GGUF 변환(Q4_K_M, 비교용 Q8_0) → Ollama 등록 → `backend/.env`에 `LLM_PROVIDER=local`, `LOCAL_LLM_MODEL=qwen3-8b-stockrule` 설정.

- 병합·변환 스크립트는 없다. 병준 명세도 "GGUF 변환과 Ollama 등록 단계는 haechan 학습 스크립트에 아직 없다(담당·스크립트 필요)"라고 적었다.
- Ollama의 템플릿과 system 문구가 학습 때와 글자 그대로 같아야 한다.
- 백엔드 쪽 연결은 hyeonkyeong의 로컬 Qwen3-8B 어댑터(커밋 `3b9f4c7`: `backend/llm/principle.py`, `llm/provider.py`의 `_local` 등)가 맡는다. 팀 학습 데이터와 같은 system 문구·입력 형식으로 호출하고, 학습 출력 형식(되묻기, 수정 `changes` 등)을 앱 형식으로 해석한다. 병합 데이터 2,020턴 재생 검증은 통과했지만 **실제 모델 호출은 아직 확인되지 않았다.**
- 현재 앱의 원칙 변환은 Claude Haiku로 대체해 동작 중이다(`LLM_PROVIDER=anthropic`). Ollama에 등록한 이름을 `backend/.env`의 `LOCAL_LLM_MODEL`(임시 `qwen3-8b-stockrule`)에 넣고 `LLM_PROVIDER=local`로 바꾼다.
- 이 PC(4060, 8GB)에서 4비트 8B 모델이 충분한 속도로 도는지는 측정이 필요하다.

## 5. 진행 현황 (2026-11-05)

| 단계 | 상태 |
|---|---|
| 병합본(S6·S7 포함) | 있음 (train 2,090 / val 111) |
| 4-1 S1·S2 생성 | **진행 중**. qwen3:8b로 411개 중 64개 완료(33분 경과 시점), 남은 예상 약 3시간 |
| 4-2 병합 | 대기 (byungjun) |
| 4-3~4-6 학습 | 대기. 학습 PC 정해지지 않음 |
| 4-7 평가, 4-8 배포 | 스크립트 미확인 |

## 6. 팀 확정 사항 (2026-11-05, 병준 명세 12절)

- **모델**: Qwen3-8B 단독 확정(로컬 파인튜닝). 4개 모델 비교 실험은 취소했다(시간이 남거나 기준 미달 시 재검토). 일반 대화 유지용 공개 데이터는 섞지 않는다.
- **성공 기준**: JSON 유효율 99%, 필드 정확도 90%, 은어 변환율 90%. 미달하면 few-shot으로 선회한다.
- **평가**: 학습 전 few-shot과 학습 후를 비교하고, 4060에서 GGUF 4비트 상태로 평가한다.
- **학습 스크립트**: `haechan/finetune/train_qlora.py`가 이미 있다(병합본 사용, `enable_thinking=False`, assistant 턴마다 샘플 생성, 길이 초과 샘플은 버림, `--dry-run` 지원).
- **출력 형식 불일치**: 학습 데이터와 백엔드의 형식 차이는 hyeonkyeong의 어댑터로 해결되었다(백엔드 쪽).
- **일정**: 개발 완료 2026-11-08(일), 11/09~10 시연영상·결과물.

## 7. 미정·확인 필요

- 학습에 쓸 PC(4090 또는 4080 Super)와 데이터를 옮기는 방법
- S1·S2를 포함한 병합본으로 학습할지, 현재 병합본(S1·S2 없음)으로 먼저 학습할지. 은어 변환율 90% 평가를 하려면 S1·S2가 필요하다.
- 학습 시간(스모크 테스트 결과로 추정). 마감(11/08)을 고려하면 S1·S2 생성(약 3.5시간)과 병합·학습 일정을 함께 잡아야 한다.
- 평가 스크립트, 병합·GGUF 변환·Ollama 등록 스크립트의 담당과 위치(현재 없음)
- `max_seq_len`(2,048 vs 팀 메모 512~1024) 재검토
- system 프롬프트 최종 문구(`assemble_s1_s2.py`의 `SYSTEM`은 임시, 팀 합의 필요)
- 병준 명세의 하이퍼파라미터는 한 번도 검증되지 않은 제안값이다. 첫 실행 결과로 조정한다.

## 8. 관련 파일

| 파일 | 내용 |
|---|---|
| `byungjun/finetune_merged/파인튜닝_설정값_명세.md` | 설정값 명세와 근거 |
| `byungjun/finetune_merged/README.md` | 병합본 구성과 주의사항 |
| `haechan/finetune/train_qlora.py`, `run_train.ps1`, `setup_check.ps1` | 학습, 실행, 환경 점검 |
| `haechan/data/validate_data.py` | 데이터 검증(V1~V10) |
| `yappang/data/gen_prompts/README.md` | S1·S2 생성 도구 설명 |
| `yappang/model-data-summary.md` | 모델·데이터 정리(요약본) |
| `hyeonkyeong/backend/llm/principle.py`, `llm/provider.py` | 로컬 Qwen3-8B 어댑터(백엔드 연결, 커밋 `3b9f4c7`) |

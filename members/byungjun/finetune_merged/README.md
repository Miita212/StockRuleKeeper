# finetune_merged

Qwen3-8B 파인튜닝(4090, QLoRA)에 쓰는 **최종 학습 데이터**를 팀원 폴더에서 읽어 합친 결과다. 원본은 수정하지 않았다. (2026-11-06 기준, S1·S2 포함)

## 파일
| 파일 | 내용 |
|---|---|
| `train.jsonl` | 학습용 5,202건. 한 줄 = `{"messages": [system, user, assistant, ...]}` |
| `val.jsonl` | 학습 중 loss 확인용 275건 (종류별 약 5%, 같은 첫 질문은 train 또는 val 한쪽에만 들어가게 입력 단위로 나눔) |
| `train_meta.jsonl`, `val_meta.jsonl` | 같은 순서의 부가 정보 (type, kind, indicator_ids, locked, seed_id, 원본 파일·줄 번호) |
| `merge_train_data.py` | 합치는 스크립트. `python3 -I merge_train_data.py` (시드 42 고정) |

학습 코드는 대화 한 건에서 assistant 답변마다 샘플 1개를 만든다(S3 다중 턴 340건 때문). 그래서 실제 학습 샘플은 train 5,627개, val 299개다.

## 구성 (train / val)
| type | 내용 | 원본 | train | val |
|---|---|---|---|---|
| SEED | 시드 | haechan `seed_*.jsonl` | 195 | 12 |
| S1 | 원칙 해석 변형(되묻기·변환 등) | yappang `gen_s1_s2_pass.jsonl` | 2,153 | 113 |
| S2 | 복수 지표·모호 표현 | yappang `gen_s1_s2_pass.jsonl` | 849 | 45 |
| S3 | 되묻기(다중 턴) | hyeonkyeong `gen_s3.jsonl` | 340 | 18 |
| S4 | 기존 규칙 수정 | hyeonkyeong `gen_s4_s5.jsonl` | 665 | 35 |
| S5 | 거절 | hyeonkyeong `gen_s4_s5.jsonl` 294 + yappang `gen_s1_s2_pass.jsonl` 107 | 401 | 21 |
| S6 | 쉬운 설명 | byungjun `S-4_gen_s6_s7.jsonl` | 399 | 21 |
| S7 | 설명(확인 질문 답) | byungjun `S-4_gen_s6_s7.jsonl` | 200 | 10 |
| 합계 | | | 5,202 | 275 |

yappang 파일에는 S1 2,273 / S2 895 / S5 116건(검증 통과분 3,284건)이 있다. 아래 제외분을 뺀 나머지를 합쳤다.

## 합치지 않은 것
- `eval_*.jsonl`: 평가용.
- `dev_set.jsonl`, `pilot_labels.jsonl`: 11/04 회의 전 구버전(Qwen2.5 기준).
- `prompts_s1/s2.jsonl`, `yappang/data/gen_prompts/`: 데이터를 만들 때 쓰는 프롬프트.
- **평가와 겹쳐 제외한 6건:** S3 중 첫 질문이 평가 H5b-024("배당 많이 주는 회사"), H5b-026("매출이 쑥쑥 크는 회사")와 같은 것 (각 3건). 원본 `gen_s3.jsonl` 에는 남아 있다. 생성 쪽(hyeonkyeong)에 알려야 한다.
- **기존 데이터와 첫 질문이 같아 제외한 8건(yappang S1·S2):** 같은 입력인데 정답이 달라지는 경우(`VALUE_MISSING` vs `AMBIGUOUS_INDICATOR`)가 있어서, 팀원이 검증한 기존 데이터를 남기고 yappang 쪽 행을 뺐다. 원본 `gen_s1_s2_pass.jsonl` 에는 남아 있다. (`EXTRA_FILES` 규칙: 앞선 파일과 같은 첫 질문이면 뒤 파일의 행을 뺌)

## 검증
- V-1(`haechan/data/validate_data.py`, 평가 세트 격리 V9 포함)로 합친 결과 5,477건(train 5,202 + val 275, 메타를 다시 붙임) 전부 통과, 실패 0.
- `train.jsonl`/`val.jsonl` 만 따로 검증기에 넣으면 `locked` 정보가 없어서 V5가 실패한다. 메타를 붙여서 검증해야 한다.
- train/val 첫 질문 겹침 0.
- 토큰 길이: 학습 코드(`finetune_train/train.py --dry-run`) 기준 최대 1,179토큰, 평균 447. `--max-len 2048` 에서 잘리거나 버려지는 샘플 없음.

## 학습할 때 주의
- system 프롬프트가 2종이다(JSON 변환용 / 쉬운 설명용). 그대로 둔다.
- Qwen3 채팅 템플릿은 `enable_thinking=False` 로 적용한다(정답에 `<think>` 가 없다). 학습 코드는 assistant 답변마다 샘플을 만들어 그 답변만 loss 에 넣는다(S3 다중 턴 포함).
- 시스템 문구는 팀 합의 전 임시일 수 있다(yappang README).
- 에폭당 스텝이 늘어났다(5,627샘플 ÷ 유효 배치 16 ≈ 351스텝). 이전 병합본(2,515샘플, 약 157스텝) 대비 학습 시간이 약 2.2배다. 이전 학습은 474스텝에 45분이었다.

## 알려진 사항 (2026-11-06)
- S7(원본 `S-4_gen_s6_s7.jsonl`)은 같은 입력(확정 규칙 JSON)이 3번씩 나오는 그룹이 60개 있다(답변 문구만 다름, 초과분 120건). 병합본에서는 지우지 않고 유지했다. 입력 단위로 나누므로 한 그룹은 train 또는 val 한쪽에만 들어간다.
- 분할은 첫 질문 기준이라 같은 시드(`seed_id`)에서 나온 S1·S2 변형이 train과 val 양쪽에 있다(69개 시드). 질문 문장은 겹치지 않지만, val loss 가 약간 낙관적일 수 있다.
- S6는 답변 문구가 같은 건이 많다(템플릿 생성).
- S1·S2는 로컬 모델(qwen3:8b)로 생성해 자동 검증만 통과한 데이터다. 사람 검수(H7) 표본 확인은 이 병합과 별개로 진행 중이다. 일부 S2 문장이 딱딱하다는 기록이 있다(yappang `finetune-procedure.md`).
- S5(거절)는 hyeonkyeong 생성분과 yappang 생성분의 범위가 겹칠 수 있다(yappang `finetune-procedure.md`).
- 이전 병합본(train 2,090 / val 111, S1·S2 없음)으로 학습한 어댑터 `finetune_train/runs/v1` 은 이 데이터와 다른 버전이다. 새 병합본으로 학습하면 `runs/v2` 처럼 새 이름으로 저장한다.

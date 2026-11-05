# finetune_merged

Qwen3-8B 파인튜닝(4090, QLoRA)에 쓰는 학습 데이터를 팀원 폴더에서 읽어 합친 결과다. 원본은 수정하지 않았다.

## 파일
| 파일 | 내용 |
|---|---|
| `train.jsonl` | 학습용 2,092건. 한 줄 = `{"messages": [system, user, assistant, ...]}` |
| `val.jsonl` | 학습 중 loss 확인용 109건 (종류별 약 5%) |
| `train_meta.jsonl`, `val_meta.jsonl` | 같은 순서의 부가 정보 (type, kind, indicator_ids, locked, 원본 파일·줄 번호) |
| `merge_train_data.py` | 합치는 스크립트. `python -I merge_train_data.py` (시드 42 고정) |

## 구성 (train / val)
| type | 내용 | 원본 | train | val |
|---|---|---|---|---|
| SEED | 시드 | haechan `seed_*.jsonl` | 197 | 10 |
| S3 | 되묻기(다중 턴) | hyeonkyeong `gen_s3.jsonl` | 340 | 18 |
| S4 | 기존 규칙 수정 | hyeonkyeong `gen_s4_s5.jsonl` | 665 | 35 |
| S5 | 거절 | hyeonkyeong `gen_s4_s5.jsonl` | 291 | 15 |
| S6 | 쉬운 설명 | byungjun `S-4_gen_s6_s7.jsonl` | 399 | 21 |
| S7 | 설명(확인 질문 답) | byungjun `S-4_gen_s6_s7.jsonl` | 200 | 10 |

## 합치지 않은 것
- `eval_*.jsonl`: 평가용.
- `dev_set.jsonl`, `pilot_labels.jsonl`: 11/04 회의 전 구버전(Qwen2.5 기준).
- `prompts_s1/s2.jsonl`: 데이터를 만들 때 쓰는 프롬프트. S1·S2 학습 데이터(`gen_s1_s2.jsonl`)는 아직 없어서 포함되지 않았다.
- **평가와 겹쳐 제외한 6건:** S3 중 첫 질문이 평가 H5b-024("배당 많이 주는 회사"), H5b-026("매출이 쑥쑥 크는 회사")와 같은 것 (각 3건). 원본 `gen_s3.jsonl` 에는 남아 있다. 생성 쪽(hyeonkyeong)에 알려야 한다.

## 검증
V-1(`haechan/data/validate_data.py`)로 원본 2,207건 전체 통과, 합친 결과(메타를 다시 붙인 2,201건)도 실패 0.
`train.jsonl`/`val.jsonl` 만 따로 검증기에 넣으면 `locked` 정보가 없어서 V5가 실패한다. 메타를 붙여서 검증해야 한다.

## 학습할 때 주의
- system 프롬프트가 2종이다(JSON 변환용 / 쉬운 설명용). 그대로 둔다.
- Qwen3 채팅 템플릿은 `enable_thinking=False` 로 적용한다(정답에 `<think>` 가 없다). 마지막 assistant 턴만 loss 에 넣을지(`assistant_only_loss`)는 S3 다중 턴 때문에 정해야 한다.
- 시스템 문구는 팀 합의 전 임시일 수 있다(yappang README).

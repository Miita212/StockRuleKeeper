# S-0 생성 입력 준비 / S-1 조립 도구

AI가 학습용 문장을 만들 때 넣는 프롬프트를 만들고(S-0), 만들어진 문장을 정답 JSON과 묶는다(S-1 조립).
**이 폴더의 코드는 생성(LLM 호출)을 하지 않는다.** D6 결론(byungjun): 학습 데이터 생성은 로컬 모델로 하고 외부 LLM(Claude 포함)으로는 하지 않는다.

## 입력으로 쓴 것
| 입력 | 위치 | 쓰임 |
|---|---|---|
| 동의어 사전 H2-a~c | `../synonyms_*.csv` | 프롬프트의 참고 표현, 모호 표현(S2-B) |
| 지표 마스터 H1-a~c | `members/byungjun/data/H1-*_indicator_master_*.json` | 방향·단위·정의·기본값 |
| 되묻기 선택지 H3-a~c | `members/byungjun/data/H3-[abc]_*.json` | 엄격/보통/느슨 값, 되묻기 정답 |
| 되묻기 정책 H3-0 | `members/byungjun/data/H3-0_clarify_policy.md` | 값 없음=되묻기(T1), 모호=지표 되묻기(T2), 값 있음=확정(T4) |
| V-1 검증 코드 | `members/haechan/data/validate_data.py` | 조립 결과 검증 (읽기만 함) |

다른 팀원 폴더의 파일은 읽기만 했고 수정하지 않았다.

## 구성
| 파일 | 내용 |
|---|---|
| `templates/*.txt` | 프롬프트 틀 4종 (S1-A/V 표현 기반, S1-B 시드, S2-A 복수 지표, S2-B 모호 표현) |
| `common.py` | 마스터·H3 읽기, 값을 말 표현으로 바꾸기 (예: 50000억원 → "5조", "5천억" 계열) |
| `build_prompts.py` | 프롬프트 생성 → `out/prompts_s1.jsonl`, `out/prompts_s2.jsonl`, `out/sample_for_review.md` |
| `assemble_s1_s2.py` | 로컬 모델 출력(raw) → 정답 포함 학습 샘플 `gen_s1_s2.jsonl` + 버린 목록 |
| `indicators_ref.json` | 지표 20개의 대표 문장 (`핵심지표20개.xlsx`에서 추출) |

## 프롬프트 모드와 정답
| mode | 프롬프트 수 | 예상 문장 | 문장 | 정답 (코드가 만듦) |
|---|---|---|---|---|
| `no_value` (S1-A) | 60 | 1,200 | 지표 1개, 숫자 없음 | `VALUE_MISSING` 되묻기 + H3 선택지 3개. **지표 15는 `PERIOD_MISSING`** (기간 되묻기, 시드의 정답을 그대로 가져옴) |
| `with_value` (S1-V) | 69 | 630 | 지표 1개, 엄격/보통/느슨 값 포함 | 지표 20개 세트 (말한 지표 source=user, 나머지 default), anchors. **지표 15는 기간(1/3/6/12개월)도 문장에 넣고 정답에 `period_months`** |
| `multi_value` (S2-A) | 60 | 600 | 서로 다른 영역 2~3개 지표, 기본값 포함 | 위와 같은 20개 세트, anchors 2~3개 (지표 15가 있으면 `period_months` 포함) |
| `ambiguous` (S2-B) | 15 | 150 | 모호한 표현 | `AMBIGUOUS_INDICATOR` 되묻기 + 후보 |
| `seed` (S1-B) | 시드 수 | 시드당 10 | H4 시드의 변형 | 시드 정답 JSON을 그대로 (뜻이 같아야 하므로) |

생성 후 합계는 검증 전 약 4,650개다(S1 3,900 + S2 750). 거절 시드 변형은 `refusal_seed` 모드(아래).

## 사용 순서
```
python -I build_prompts.py                       # 1. 프롬프트 만들기
# 2. out/prompts_*.jsonl 의 "prompt" 를 로컬 모델에 넣어 응답을 받는다 (이 폴더에는 실행기 없음)
#    저장 형식: 한 줄 = {"prompt_id": "...", "response": "모델 출력 원문"}  -> raw_outputs.jsonl
python -I assemble_s1_s2.py --raw raw_outputs.jsonl --out ../gen_s1_s2.jsonl
python -I <validate_data.py 경로> --master-dir <byungjun 마스터 폴더> --input ../gen_s1_s2.jsonl   # 3. V-1 검증
```
조립 단계가 걸러내는 것: JSON이 깨진 줄, style 값 이상, 지표 id 불일치, 값 없는 문장에 숫자가 있음, 값 있는 문장에 기준 숫자가 없거나 다른 숫자가 섞임, 중복 문장, 후보가 4개를 넘는 모호 표현.

## 시드 변형 (S1-B)
```
python -I build_prompts.py --seeds ../../../haechan/data/seed_1-7.jsonl ../../../haechan/data/seed_8-13.jsonl ../../../haechan/data/seed_14-20.jsonl
```
- 시드 형식은 haechan 의 `messages` 형태(`type: SEED`, `seed_id`, `kind`, `indicator_ids`)다. 옛 `{text, indicator_ids}` 형태도 읽는다.
- 207개 시드 전부로 프롬프트를 만든다. 191개는 `seed` 모드(S1/S2 변형), **거절 시드 16개는 `refusal_seed` 모드**(S5 변형, 아래). 후보 5개 이상 시드가 있으면 건너뛴다.
- **기간(지표 15)**: 시드의 `period_months`, `PERIOD_MISSING` 을 알고 있다. 변형 문장에 기간 표현("3개월"/"세 달"/"석 달" 등 `common.PERIOD_PHRASES`)이 있어야 하고, 기간 없는 시드의 변형은 기간이 들어가면 안 된다.

## 거절 시드 변형 (`refusal_seed`, 정답 type S5)
- 거절 시드 16개(지원 안 하는 지표 요구 / 종목 추천 요청 / 예측 요청)를 같은 거절 이유로 말만 바꾼다. 정답은 시드의 거절 JSON을 그대로 쓴다. 거절 답 문구가 지표 이름을 담고 있어서(예: ROE) 같은 용어를 가리키는 변형만 유효하다.
- 조립 단계가 걸러내는 것: 시드에 없는 숫자, 시드와 같은 문장, (지표 밖 요구 시드에서) 지원 지표 이름이 들어간 문장.
- 주의: S-3(hyeonkyeong)의 "거절 S5 생성"과 범위가 겹칠 수 있다. 중복 작업이 되지 않게 확인이 필요하다.
- 프롬프트에 "바꾸면 안 되는 뜻"을 사람 말로 적는다 (지표·부등호·숫자·단위·기간, 되묻는 이유). 시드당 변형 수는 `--seed-n` (기본 10, 약 1,900문장).
- 조립 단계가 확인하는 것: 시드의 값/기간 표현(예: "20%", "3개월")이 있는지, 시드에 없는 숫자가 없는지, 시드와 같은 문장이 아닌지. **부등호 방향(초과/이상 등)은 코드로 확인하지 못한다.** H7 사람 검수에서 봐야 한다.
- 정답은 시드의 assistant JSON 그대로이고, system 문구도 시드의 것을 쓴다.
- **평가 세트 격리**: 변형 샘플에 `seed_id` 가 붙는다. 같은 시드의 변형은 학습 또는 평가 한쪽에만 두어야 한다 (V9).

## 확인된 것 / 안 된 것
- 확인됨: 가짜 raw 5줄(테스트용 문구, 학습 데이터 아님)로 조립해서 걸러지는 5건과 통과 5건을 확인했고, 통과분 5건은 `validate_data.py` 를 실패 0으로 통과했다.
- **실제 생성은 한 번도 하지 않았다.** 이 PC에는 GPU 드라이버는 있으나 torch/transformers/ollama 가 없다. 로컬 모델 실행 환경부터 필요하다.
- 완료 기준 "프롬프트 시험 생성 10개를 사람이 확인"은 아직이다. 생성기가 준비된 뒤 `out/sample_for_review.md` 의 프롬프트로 시험 생성해서 확인한다.

## byungjun 변경 반영 (2026-11-04)
- 지표 4·5의 default≠H3 "보통"은 **의도된 예외**로 확정됐다(`normal_equals_default: false`). 경고를 이 경우에는 내지 않는다. 말하지 않은 지표를 채울 때는 마스터 `default`, 되묻기 선택지에는 H3 값을 쓴다.
- 되묻기 message 는 H3 의 지표별 `clarify_message` 를 쓴다(없을 때만 공통 임시 문구).
- 같은 방향 두 부등호 허용(H1 `allowed_operators`)을 반영했다. `with_value` 프롬프트는 "이하/미만", "이상/초과" 중 하나를 쓰게 하고 `op_word` 로 답하게 한다. 조립 단계가 `op_word` 가 문장에 있는지, 두 가지가 섞이지 않았는지 확인한 뒤 정답 부등호를 그에 맞춘다.

## 알려진 문제
1. 후보 지표가 5개 이상인 모호 표현은 H3-0 정책상 **2단계 되묻기(영역 → 지표)** 대화로 만들어야 한다. 단발 샘플로는 만들지 않고 조립 단계에서 버린다. 현재 `validate_data.py` 는 `stage`/영역 후보를 지원하지 않아 haechan 쪽 수정이 먼저 필요하다. 대화 데이터는 S-2(hyeonkyeong) 범위다.
2. 시스템 프롬프트(`assemble_s1_s2.py` 의 `SYSTEM`)는 임시 문구다. 최종 학습 형식은 팀 합의 후 맞춘다.
3. 반대 방향 표현("작은 회사만", "고점 근처가 아닌")은 아직 프롬프트에 쓰지 않는다. 마스터가 반대 방향을 허용하는 지표(5, 14~17)에 한해 별도 설계가 필요하다.

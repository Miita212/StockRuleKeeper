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
| `no_value` (S1-A) | 60 | 1,200 | 지표 1개, 숫자 없음 | `VALUE_MISSING` 되묻기 + H3 선택지 3개 |
| `with_value` (S1-V) | 60 | 600 | 지표 1개, 엄격/보통/느슨 값 포함 | 지표 20개 세트 (말한 지표 source=user, 나머지 default), anchors |
| `multi_value` (S2-A) | 60 | 600 | 서로 다른 영역 2~3개 지표, 기본값 포함 | 위와 같은 20개 세트, anchors 2~3개 |
| `ambiguous` (S2-B) | 15 | 150 | 모호한 표현 | `AMBIGUOUS_INDICATOR` 되묻기 + 후보 |
| `seed` (S1-B) | 시드 수 | - | 시드 변형 (H4가 있을 때 `--seeds`) | 시드의 정답을 그대로 |

생성 후 합계는 검증 전 약 2,550개다(S1 1,800 + S2 750).

## 사용 순서
```
python -I build_prompts.py                       # 1. 프롬프트 만들기
# 2. out/prompts_*.jsonl 의 "prompt" 를 로컬 모델에 넣어 응답을 받는다 (이 폴더에는 실행기 없음)
#    저장 형식: 한 줄 = {"prompt_id": "...", "response": "모델 출력 원문"}  -> raw_outputs.jsonl
python -I assemble_s1_s2.py --raw raw_outputs.jsonl --out ../gen_s1_s2.jsonl
python -I <validate_data.py 경로> --master-dir <byungjun 마스터 폴더> --input ../gen_s1_s2.jsonl   # 3. V-1 검증
```
조립 단계가 걸러내는 것: JSON이 깨진 줄, style 값 이상, 지표 id 불일치, 값 없는 문장에 숫자가 있음, 값 있는 문장에 기준 숫자가 없거나 다른 숫자가 섞임, 중복 문장, 후보가 4개를 넘는 모호 표현.

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

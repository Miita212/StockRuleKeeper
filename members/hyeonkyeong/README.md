# hyeonkyeong

## 담당 역할
LLM 개발 — 데이터 준비 계획표(`data-preparation-plan.xlsx`)의 hyeonkyeong 담당 11개 (H6, H8, H5-a~c, T-a~c, D1, S-2, S-3).

## 이 폴더가 하는 일
`backend/`, `frontend/`는 앱 개발 코드다. 데이터 준비 산출물은 모두 `data/` 안에 있다.

| 작업 | 산출물 | 상태 |
| --- | --- | --- |
| H6 말투·안전 가이드 | `data/tone_safety_guide.md` | 완료 (팀 확인 전) |
| H8 리포트 톤 가이드 | `data/report_tone_guide.md` | 완료 (팀 확인 전) |
| H5-a~c 평가 세트 | `data/eval_1-7.jsonl` (36) / `eval_8-13.jsonl` (36) / `eval_14-20.jsonl` (39) | 완료. 시드 207개·S-4와 겹치는 문장 0 |
| T-a~c 용어 진단 | `data/diag_1-7.csv` (21) / `diag_8-13.csv` (18) / `diag_14-20.csv` (21) | 완료 |
| D1 금융용어사전 | `data/glossary_fsc_notes.md`, `data/scripts/clean_glossary.py` | **미완료**: 공공데이터포털 신청·내려받기 필요 |
| S-2 되묻기 대화(S3) | `data/gen_s3.jsonl` (364) | 완료. V-1 검증 전부 통과 |
| S-3 수정 diff·거절(S4·S5) | `data/gen_s4_s5.jsonl` (1,006) | 완료. V-1 검증 전부 통과 |

- S-2·S-3는 **외부 LLM 없이 템플릿 스크립트**로 만들었다 (D6 결론). 사용자 문장은 yappang 동의어 사전에서 가져왔다.
- H5·T·H6·H8은 학습 데이터가 아니다 (평가·가이드). 학습에 섞지 않는다.

## 실행 방법
모두 `members/hyeonkyeong/data/scripts/`에서 실행한다 (표준 라이브러리만 사용).
```
python -I -X utf8 build_eval.py       # H5 평가 세트 (시드와 같은 문장이 있으면 멈춤)
python -I -X utf8 build_diag.py       # T 진단 문제
python -I -X utf8 gen_s3.py           # S-2 되묻기 대화
python -I -X utf8 gen_s4_s5.py        # S-3 수정 diff + 거절
python -I -X utf8 clean_glossary.py 받은파일.csv   # D1 정제
```
검증 (V-1):
```
python -I -X utf8 ../../haechan/data/validate_data.py --master-dir ../../byungjun/data ^
  --input gen_s3.jsonl gen_s4_s5.jsonl ../../haechan/data/seed_*.jsonl --eval eval_*.jsonl
```
(위 경로는 `data/` 폴더 기준)

## 핵심 함수

| 이름 | 입력 | 출력 | 예시 |
|------|------|------|------|
| `gold_full(anchors, period)` (`gen_common.py`) | `{지표id: 값}`, 기간(개월) | 20개 세트 JSON (말한 지표 source=user, 나머지 default) | `gold_full({1: 50})` |
| `ask_value(i, period)` | 지표 id | VALUE_MISSING 되묻기 JSON (H3 지표별 문구·선택지) | `ask_value(1)` |
| `step(i, 값, stricter)` (`gen_s4_s5.py`) | 지표 id, 현재 값, 엄격 여부 | 새 값 (못 바꾸면 None) | `step(1, 100, True)` → 80 |

## 데이터 형식 (제안 — `docs/interface.md`에는 아직 올리지 않음)
- 시스템 프롬프트: haechan 시드(H4)와 같은 문구를 쓴다 (`gen_common.py`의 `SYSTEM`).
- 평가 세트(H5) 형식: 시드와 같은 칸(`id`, `text`, `output`, `messages`). 확정 정답은 시드처럼 20개 세트.
- **S3 최종 확정 응답**: `gold_full` 20개 세트 + `explain_bubble`(설명 말풍선 문자열).
- **지표 15 기본 항목**: `source=default`일 때는 `period_months`를 붙이지 않는다 (haechan 확인 2026-11-04). 사용자가 말한 지표 15에만 붙는다.
- **S4 입력**: `현재 원칙: {"indicators":[{id, operator, value, unit, source, (locked:true), (period_months)} x20]}` 줄바꿈 `요청: <말>`
- **S4 출력**: `{"changes":[{id, name, before, after, unit}], "skipped_locked":[id...]}` (`skipped_locked`는 있을 때만)
- **S4 규칙 `[제안]`**: ① 잠긴 지표는 바꾸지 않는다 ② '더 엄격하게'는 마스터 `step_stricter`, '더 느슨하게'는 그 반대(되돌림) ③ '전체적으로' 요청은 source=user이면서 잠기지 않은 지표만 바꾼다 ④ 잠긴 지표만 건드리는 요청은 데이터에 넣지 않았다 (`changes`가 비면 V1에 걸림).

## 필요한 라이브러리
없음 (Python 표준 라이브러리). 검증은 haechan의 `validate_data.py`.

## 통합 때 옮길 위치
- 가이드: 팀 문서 폴더 (H6·H8)
- 평가 세트 `eval_*.jsonl`: 학습에서 격리 (V9)
- `gen_s3.jsonl`, `gen_s4_s5.jsonl`: 학습 데이터 합치기 전 H7 검수(10~20%)

## 팀 확인이 필요한 것
1. S4 잠금 규칙 ①~④ — 잠긴 지표만 건드릴 때 응답 모양도 필요. haechan은 `locked`(잠긴 id 목록)와 `skipped_locked`를 쓰는 지금 방식으로 OK
3. S3에서 "되묻기 2번 후 기본값 확정" 대화는 만들지 않았다 (H3-0 §5가 `[제안]`이라서)
4. 검증기 V7 금지 패턴이 H6 3장 목록과 일치하는지 (haechan)

확인 끝난 것 (haechan 2026-11-04): 기업명 사용(E15), "적자 회사" 문장을 평가에서 뺀 것, 파일 크기(1~2MB), 지표 15 기본 항목의 기간 제외.

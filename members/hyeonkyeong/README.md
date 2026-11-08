# hyeonkyeong

> **변경 기록·팀원 적용 방법은 [`CHANGES.md`](CHANGES.md)** (최신: 2026-11-09 의미 검증·PER/PBR 0 버그·거래량 재수집)

## 담당 역할
LLM 개발 — 데이터 준비 계획표(`data-preparation-plan.xlsx`)의 hyeonkyeong 담당 11개 (H6, H8, H5-a~c, T-a~c, D1, S-2, S-3).

## 이 폴더가 하는 일
`backend/`, `frontend/`, `virtual-app/`은 앱 개발 코드다(실행법·API는 아래 [앱](#앱-backend--frontend--virtual-app)). 데이터 준비 산출물은 모두 `data/` 안에 있다.

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

---

## 앱 (backend · frontend · virtual-app)

판정·계산은 코드가 하고, LLM은 말 → 지표 변환(FR-01)과 리포트 문장(FR-03)만 한다. 대상 종목은 반도체 113개.

| 폴더 | 내용 |
| --- | --- |
| `backend/` | FastAPI 서버 + SQLite(`data/stockrule.db`). 한투 11개·DART 9개 지표를 미리 받아 저장하고 판정·시뮬레이션을 계산 |
| `frontend/` | React + TypeScript + Vite(앱인토스 템플릿). Capacitor로 안드로이드 APK로 감싼다 |
| `virtual-app/` | 가상 주식앱(FR-02) 웹 1장. 서버가 `/virtual-app/`으로 띄운다 |

### 실행

```powershell
# 1) 서버 (backend 폴더에서). 키는 .env.example 을 .env 로 복사해 채운다(.env 는 커밋 금지)
python -m venv .venv; ./.venv/Scripts/pip install -r requirements.txt
./.venv/Scripts/python -X utf8 -m uvicorn main:app --host 0.0.0.0 --port 8000

# 2) 화면 (frontend 폴더에서) -> http://localhost:5173
npm install; npx vite

# 3) 가상 주식앱 -> http://localhost:8000/virtual-app/  (에뮬레이터 크롬에서는 http://10.0.2.2:8000/virtual-app/)
```

- 데이터 수집(처음 한 번, 약 1시간): `batch/build_universe.py`(종목 풀) → `batch/collect_data.py`(이어받기 가능, `--force` 재수집).
- 키 없이 보기: `.env`에 `EXTERNAL_MODE=fixture`(가짜 샘플 응답).
- 원칙 변환 모델: `LLM_PROVIDER=anthropic`(Haiku, 기본) 또는 `local`(Ollama의 파인튜닝 Qwen3-8B, `LOCAL_LLM_URL`·`LOCAL_LLM_MODEL`). 리포트는 항상 Haiku.

### 안드로이드 APK

```powershell
# frontend 폴더에서. npm run build 는 ait build 가 붙어 있어 쓰지 않는다
npx vite build; npx cap sync android
cd android; $env:JAVA_HOME="C:\Program Files\Android\Android Studio\jbr"; ./gradlew.bat assembleDebug --no-daemon
# 결과: android/app/build/outputs/apk/debug/app-debug.apk -> adb install -r app-debug.apk
```

- 서버 주소: 에뮬레이터는 `.env.production`의 `http://10.0.2.2:8000`. 실제 폰은 노트북 Wi-Fi IP로 바꿔 다시 빌드하고, 같은 Wi-Fi + 방화벽 8000 허용이 필요하다.

### 테스트 (backend 폴더에서)

| 스크립트 | 확인하는 것 |
| --- | --- |
| `scripts/test_principles.py` | 모델 출력 검증·잠금·저장/버전. 팀 학습 데이터(`byungjun/finetune_merged`) 정답을 모델 출력 대신 넣어 재생. `--live`는 Haiku 실제 호출 |
| `scripts/test_indicators.py` | 지표 20개 계산·판정 문구 |
| `scripts/test_stocks.py` | 종목 목록·추천·판정서·공유 (수집 DB 사용) |
| `scripts/test_simulation.py` | 시뮬레이션 수치 (`--report`는 Haiku 리포트 호출) |
| `scripts/check_external.py [--only kis,dart,llm]` | 외부 API 연결 점검 |

### API (사용자는 `jangyechan` 고정)

| 메서드·경로 | 화면 | 내용 |
| --- | --- | --- |
| `GET /health`, `GET /indicators` | - | 상태, 지표 20개 마스터 |
| `POST /principles/ask` | 01·02-1·02·08 | `{text, base_principle_id \| base_indicators, locked_ids, history}` → `{needs_clarification, clarify{message, options[{label, (indicator_id, operator, value, criterion)}]}, name, indicators(20개), values, explain_bubble, explain_card, warnings}` |
| `POST /principles`, `GET /principles`, `GET·PUT·DELETE /principles/{id}` | 02·06·07·14 | 저장·목록·조회(`?version=`)·수정(새 버전)·삭제 |
| `GET /stocks?principle_id=&q=` | 03 검색 | 반도체 종목을 원칙 충족 개수 순으로 |
| `GET /stocks/recommend?principle_id=` | 03 검색창 아래 | 사용자가 정한 지표를 모두 충족하는 종목(최대 10) |
| `GET /stocks/{code}/verdict?principle_id=` | 04 판정서 | 지표별 기준·실제 값·충족 여부 |
| `GET /virtual/stocks`, `POST /shares`, `GET /shares/latest?after_id=` | 가상 주식앱 | 종목 목록, "공유하기", 본 앱이 2초마다 확인 |
| `POST /simulation` | 11·12·13 | `{principle_id, changes[{id, operator, value}], months: 3\|6\|12, locked_ids, with_report}` → 수정 전/후 수치 + 리포트(07 스키마) |

원칙 = 지표 20개 전부 `[{id, operator, value, unit, source(user|inferred|default), locked, (period_months)}]`. "조건에 맞는 종목"(추천·시뮬레이션)은 `source`가 user/inferred인 지표만 본다(없으면 20개 전부). 판정서 충족 개수는 20개 기준.

### 로컬 모델(Qwen3-8B) 입출력 계약 — 팀 학습 데이터와 같게

`llm/principle.py`의 `ask_local` / `from_trained`. 학습 데이터 형식을 그대로 쓰고, 서버가 화면 형식으로 바꾼다.

| 구분 | 모델에 보내는 것 | 모델이 내는 것 → 서버 처리 |
| --- | --- | --- |
| system | `너는 투자 원칙 점검 앱의 도우미야. 사용자의 말을 지표 20개 기준 JSON으로 바꿔. JSON만 출력하고, 종목 추천이나 수익 예측은 하지 않아.` (글자 그대로) | |
| 새 원칙 | 사용자 말 그대로 | `{indicators: 20개, anchors, (explain_bubble)}` → `source=default`는 버리고 사용자가 정한 것만 적용 |
| 되묻기 답 | 앞선 대화(user·assistant 턴)를 이어서 보낸다. 서버가 직전 되묻기를 기억 | `VALUE_MISSING`(값 선택지) / `AMBIGUOUS_INDICATOR`(지표·영역 후보) / `PERIOD_MISSING`(기간) → `clarify` |
| 원칙 수정 | `현재 원칙: {"indicators":[20개, 잠금은 "locked": true]}` 줄바꿈 `요청: <말>` | `{changes[{id, after}], skipped_locked}` → 바뀐 것만 적용, 잠긴 지표는 안내 |
| 거절 | | `{refusal: true, message}` → 안내 문구만 |

- 단위: 학습 데이터의 시가총액(14)은 **억원**(1조원 = 10000), 서버 원칙은 조원 → 서버가 바꾼다. 나머지는 같다.
- 양방향 지표 5·14·15·16·17은 반대 연산자도 허용(팀 마스터 `allowed_operators`). 반대 방향이면 "이내" 대신 "초과·미만"으로 표시.
- 원칙 이름·설명 카드는 학습 형식에 없어서 코드가 만든다. 기간(`period_months`)은 저장만 하고 계산은 아직 3개월 기준.
- Ollama 옵션: `think: false`, `temperature: 0`, `format: json`. 실제 모델 호출은 모델 파일이 오면 확인한다(미확인).

### 지표 기준

- 기본값·연산자는 팀 지표 마스터(`byungjun/data/H1-*`)를 따른다(2026-11-05: 매출액 증가율 15%, 영업이익 증가율 10%, 기간 수익률 10%로 맞춤).
- 계산 기준과 외부 API 실측: `backend/docs/external-api-notes.md`, 지표 20개 검증 과정: `docs/지표20개_세팅_정리.md`.

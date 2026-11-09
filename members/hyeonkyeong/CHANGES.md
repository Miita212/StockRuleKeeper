# hyeonkyeong 변경 기록 (팀원 적용용)

다른 팀원(또는 팀원의 Claude)이 `git pull` 후 **자기 폴더 `members/<이름>/`의 앱에 같은 변경을 적용**할 때 보는 문서다. 최신이 위.
각 항목은 `무엇 / 왜 / 적용 방법(찾을 코드 → 바꿀 코드) / 실행할 명령 / 확인 방법` 순서다. 다른 사람 폴더는 각자 자기 것만 고친다.

---

## 2026-11-09 · 앱 로컬 모델 = data_v6 3에폭 (해찬 v5 재현), 백엔드 .env를 로컬 모델로

### 1. 어떤 모델이 붙어 있나
- Ollama `qwen3-8b-stockrule` = **data_v6 3에폭**(hyeonkyeong이 ws6에서 학습, 해찬 v5 3에폭과 같은 데이터·설정 → 공식 111문제 점수가 항목마다 1문제 안쪽으로 같음). 결과: [`docs/8B_data_v6_재학습_결과.md`](docs/8B_data_v6_재학습_결과.md).
- 이전 모델(해찬 v3 2에폭)은 `qwen3-8b-stockrule-v3-2ep`로 남겨 둠. 되돌리기: `ollama cp qwen3-8b-stockrule-v3-2ep qwen3-8b-stockrule`.
- 앱에서 확인(에뮬레이터): "적자 기업은 제외할래요" → 영업이익/매출순이익률 고르기 → 100억원 초과 (v3는 자본잠식률로 잘못 바꿨던 문장). "영업이익 500억 넘는 회사 찾아줘"도 이제 거절하지 않고 추출.
- 알려진 약점(해찬 v5와 같음): "부채비율 150% 이하에 영업이익 100억 이상"처럼 지표 두 개 문장에서 영업이익을 빠뜨림. 되묻기 값 단계에서 버튼 대신 직접 "60% 이하"라고 치면 문맥을 잃음 → 시연은 버튼으로.
- 다음: yappang fixed-4(8B·4B 공용)로 8B 학습 중. 결과가 더 좋으면 같은 방법으로 교체 예정.

### 2. 백엔드를 그냥 켜도 로컬 모델을 쓰게
- **문제**: `config.py` 기본값이 `LLM_PROVIDER=anthropic`, `HTTP_TIMEOUT=20`이라 `.env`에 안 적으면 원칙 변환이 Haiku로 가고, 로컬로 바꿔도 20초 타임아웃에 끊길 수 있었다(로컬 변환 13~18초).
- **바꾼 것**: 내 `backend/.env`(git에 안 올라감)에 아래 3줄 추가. `.env.example`에는 시연용 안내 주석만 추가(기본값은 그대로 anthropic — Ollama 없는 PC에서 켜도 동작하게).
```
LLM_PROVIDER=local
LOCAL_LLM_MODEL=qwen3-8b-stockrule
HTTP_TIMEOUT=300
```
- **팀원 적용**: 자기 PC에서 로컬 모델(Ollama `qwen3-8b-stockrule`)로 시연하려면 자기 `backend/.env`에 같은 3줄을 넣는다. Ollama 모델이 없으면 넣지 말 것(원칙 변환이 실패한다).
- **확인**: `cd backend && python -c "import config;print(config.LLM_PROVIDER, config.HTTP_TIMEOUT)"` → `local 300.0`.

---

## 2026-11-09 · 병준 UI 15~17번 반영 (지표 비활성화, 06 연필 아이콘, 03 공지 띠)

- 무엇: 병준 커밋 `43f127b`·`f70d25c`·`4b80340`·`f8becdf`의 백엔드·프론트 변경을 내 폴더로 가져왔다. 내용은 병준 것과 **똑같다**(줄바꿈만 내 파일 형식 CRLF 유지).
- 상세 설명(동작·이유·한계): `members/byungjun/frontend/UI및백엔드수정내역.md` 15·16·17절. 여기서는 반복하지 않는다.
- 가져온 파일 10개:
  - 백엔드: `backend/api/principles.py` (`GET /indicators/defaults` 추가)
  - 프론트 수정: `src/App.css`, `src/api/index.ts`, `src/components/IndicatorCard.tsx`, `src/screens/PrincipleChat.tsx`, `src/screens/S03_StockSearch.tsx`, `src/screens/S06_PrincipleList.tsx`
  - 프론트 새 파일: `src/components/NoticeBar.tsx`, `src/data/deactivate.ts`, `src/assets/icons/pencil.svg`
- 적용 방법(다른 팀원): 내 폴더의 위 6개 파일이 병준의 `9e01c46` 시점과 같았다면(나는 같았음, 줄바꿈 무시 비교) 병준 최신 파일을 그대로 복사하면 된다. 내 것을 고쳐 둔 게 있으면 병준 diff(`git diff 9e01c46 HEAD -- members/byungjun/frontend/src members/byungjun/backend`)만 손으로 옮긴다.
- 실행: **백엔드를 다시 켜야** `/indicators/defaults`가 생긴다. 프론트는 다시 빌드.
- 확인: `curl localhost:8000/indicators/defaults` → `name: 기본값`, 지표 20개(영업이익 `100억원 이상`). 프론트 `vite build` 통과. 화면 동작(꾹 눌러 비활성화 등)은 병준이 헤드리스 Chrome으로 확인한 것이고 내 앱 화면에서는 아직 안 봤다.

---

## 2026-11-09 · 자연어→수치 의미 검증 + 데이터 버그 2개 수정

- 커밋: `[hyeonkyeong] 자연어→수치 의미 검증 추가, 한투 PER·PBR 0을 데이터 없음으로 처리` (이 문서와 같은 커밋)
- 상세 결과·판정 근거: [`backend/scripts/eval_results/README.md`](backend/scripts/eval_results/README.md)
- 적용 대상 확인(11/09): `members/byungjun/backend`, `members/yappang/backend` 둘 다 아래 "찾을 코드"가 **그대로 있음**(`indicators/compute.py` 33행 부근).

### 변경 1. 한투 PER·PBR이 0이면 '데이터 없음' (코드 수정, 적용 필요)
- **증상**: 리노공업·HPSP·아진엑스텍·동운아나텍의 PER·PBR이 0 → "PER 10배 이하", "PBR 1배 미만"을 잘못 통과해 저평가 1순위로 표시됨.
- **원인**: 한투 현재가 API(`inquire-price`)는 PER·PBR 값이 없을 때 `"0.00"`을 준다. `external/kis/quotes.py`의 `_num`이 이를 0.0으로 받고, 판정이 그대로 사용.
- **결정**: 0 이하 PER·PBR은 판정에서 '데이터 없음'(None, 미충족). 음수 PER(적자)·음수 PBR(자본잠식)도 "싸다"로 보지 않는다.
- **파일**: `backend/indicators/compute.py` 함수 `compute_all`

찾을 코드:
```python
    for i, factor in ((10, per_factor), (11, pbr_factor)):
        if i in out and out[i]["value"] is not None:
            out[i] = {"value": out[i]["value"] * factor if factor else None, "approx": True}
```
바꿀 코드:
```python
    for i, factor in ((10, per_factor), (11, pbr_factor)):
        if i in out and out[i]["value"] is not None:
            kis = out[i]["value"]  # 한투는 값이 없을 때 0을 준다 → 0 이하는 '데이터 없음'
            out[i] = {"value": kis * factor if factor and kis > 0 else None, "approx": True}
```
- DB에 저장된 값과 한투에서 바로 받은 값 모두 이 함수를 거치므로 **재수집 불필요**. 서버만 재시작.
- 확인: `python -X utf8 scripts/test_indicators.py` → `OK`. 종목 지표에서 리노공업(058470)의 10·11번 값이 `None`. (반도체 113종목 기준 "PER≤10" 통과 22→16, "PBR<1" 40→35)

### 변경 2. 마지막 일봉이 장중 값이라 거래량 증가 배율이 비정상 (데이터 재수집, 코드 변경 없음)
- **증상**: 거래량 증가 배율(지표 20)이 거의 모든 종목에서 1 미만(중앙값 0.36) → "거래량 터진 종목"이 항상 0종목.
- **원인**: 11/05 수집을 장중에 해서 마지막 일봉(11/05)의 거래량이 하루치가 아님(삼성전자 715만 주, 하루 전체는 2,466만 주). `collect_data.py`는 마지막 저장일부터 다시 받으므로 장 마감 뒤에 돌리면 덮어써진다.
- **적용**: 각자 backend 폴더에서 **장 마감(15:30 KST) 뒤**에
  ```bash
  python -X utf8 batch/collect_data.py --only kis     # 113종목 약 10분, 한투 허용 API(일봉·현재가·배당)만 사용
  ```
- 확인: `prices_daily`의 `MAX(date)`가 직전 거래일, 거래량 증가 배율 중앙값 ≈ 1 (11/09 재수집 후 1.13), "거래량 2배 이상" 통과 0→7.
- **주의(미해결)**: 장중에 수집하면 같은 문제가 다시 생긴다. 시연 전 수집은 장 마감 뒤에 할 것.

### 추가 3. 의미 검증 스크립트 (새 파일, 선택)
- `backend/scripts/eval_meaning.py`: 34문장(8개 분류)을 `POST /principles/ask`로 보내고, 되묻기는 가운데 선택지로 답한 뒤, 최종 원칙으로 반도체 종목을 걸러 통과 수를 기록. **원칙은 저장하지 않음.**
- `backend/scripts/eval_results/`: 판정 기준·결과 해설 `README.md`, 결과 JSON(`eval_v3-2ep.json` 수정 전, `eval_v3-2ep_1109fix.json` 수정 후 = **기준 결과**).
- 다른 팀원 backend에서도 그대로 동작(필요 함수 `services.stocks.list_stocks`, `services.principles.default_indicators` 동일 확인). 복사 후:
  ```bash
  # 서버(8000)를 테스트할 모델로 켠 상태에서, backend 폴더
  python -X utf8 scripts/eval_meaning.py scripts/eval_results/eval_<모델이름>.json
  ```
- 의존성: `httpx`(서버 requirements에 이미 있음).

### 검증 결과 요약 (해찬 v3 2에폭, Ollama `qwen3-8b-stockrule`)
- 수정 후 ✅19 ⚠️4 ❌11 / 34. 모델 출력은 수정 전후 동일(temperature 0).
- ❌는 모두 **모델 쪽**(백엔드 코드로 못 고침): 방향 반대 3(고점 대비 많이 떨어진·많이 오른 건 빼고·작은 회사), 지표 오선택 3(배당수익률→연속 배당, 3개월 20% 상승→거래량 배율, 적자 제외→자본잠식률), 있는 지표 거절 1(영업이익 500억), 다중 조건 누락 2, 되묻기 무한 1(빚 많은 회사), 수정 시 value 누락 1(PER 12배 추가).
- 남은 일: v5 3에폭으로 같은 스크립트 재실행 → `eval_results/README.md` 표에 추가해 비교.

# hyeonkyeong 변경 기록 (팀원 적용용)

다른 팀원(또는 팀원의 Claude)이 `git pull` 후 **자기 폴더 `members/<이름>/`의 앱에 같은 변경을 적용**할 때 보는 문서다. 최신이 위.
각 항목은 `무엇 / 왜 / 적용 방법(찾을 코드 → 바꿀 코드) / 실행할 명령 / 확인 방법` 순서다. 다른 사람 폴더는 각자 자기 것만 고친다.

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

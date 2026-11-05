# 외부 API 연동 노트

작성 기준: 2026-11-04. **검증 상태** 열: `예제` = 한투 공식 예제 코드(github.com/koreainvestment/open-trading-api)에서 확인, `실측` = 실제 호출로 확인, `미확인` = 아직 확인 못 함(확인 요청 목록 참고).
지표 id는 프론트 `src/data/indicators.ts`와 같다(1~9 DART, 10~20 한투).

## 1. 공통
- 모든 외부 호출은 서버에서만. 키는 `backend/.env`(KIS_APP_KEY, KIS_APP_SECRET, KIS_ENV, DART_API_KEY, ANTHROPIC_API_KEY). 값은 코드·로그·오류 메시지·픽스처에 남기지 않는다(`external/http.py`는 오류에 경로만 쓴다).
- `EXTERNAL_MODE=live|fixture`. fixture는 `external/fixtures/*.json`(값은 가짜, 구조는 실제 응답 형태).
- 호출 제어: `config.KIS_MIN_INTERVAL`(기본 0.6초), `DART_MIN_INTERVAL`(0.2초), 타임아웃 20초, 재시도 최대 2회(429·5xx만).
- 한투 허용 목록(`external/kis/client.py`): 토큰, 현재가, 기간별시세, 배당일정, 종목기본정보 5개만. 주문·계좌·종목분석 7종은 없다(11/11 16:00 이후 차단).

## 2. 한투 11개 지표 (시세·배당)
| id | 지표 | 사용 API (경로 / TR ID) | 원천 필드 → 계산 | 상태 |
|---|---|---|---|---|
| 10 | PER | 현재가 `/quotations/inquire-price` FHKST01010100 | `per` | 경로·TR 예제 / 필드명 미확인 |
| 11 | PBR | 〃 | `pbr` | 〃 |
| 14 | 시가총액 | 〃 | `hts_avls`(억원) × 1억 | 〃 (단위 미확인) |
| 16 | 52주 최고가 대비 등락률 | 〃 | `w52_hgpr_vrss_prpr_ctrt` | 〃 |
| 17 | 52주 최저가 대비 상승률 | 〃 | `w52_lwpr_vrss_prpr_ctrt` | 〃 |
| 15 | 기간 수익률 | 기간별시세 `/quotations/inquire-daily-itemchartprice` FHKST03010100 | (종료일 종가 / 시작일 종가 − 1) × 100, 종가 `stck_clpr` | 경로·TR·1회 최대 100건 예제 |
| 18 | 최근 60거래일 변동성 | 〃 | 최근 60거래일 일간수익률의 표준편차 × 100 (연환산 안 함) | 계산식은 내 해석 → 확인 요청 |
| 19 | 최근 20거래일 평균 거래대금 | 〃 | 최근 20거래일 `acml_tr_pbmn`(원) 평균 | 필드명 미확인 |
| 20 | 거래량 증가 배율 | 〃 | 최근 1거래일 거래량 / 직전 20거래일 평균 거래량 | 정의 불명확 → 확인 요청 |
| 12 | 12개월 현금배당수익률 | 배당일정 `/ksdinfo/dividend` HHKDB669102C0 | 최근 12개월 기준일 주당배당금(`per_sto_divi_amt`) 합 / 현재가 × 100 | 경로·TR 예제 / 필드명 미확인 |
| 13 | 연속 현금배당 연수 | 〃 | 연도별 주당배당금 합이 0보다 큰 해를 최근 연도부터 연속으로 센다 | 조회 가능한 과거 범위 미확인 |

- 일봉은 원주가(`FID_ORG_ADJ_PRC=1`)로 받고, 140일 단위로 나눠 호출해 한 번에 100건을 넘지 않게 한다.
- 반도체 종목 선별: 종목기본정보 `/quotations/search-stock-info` CTPF1002R의 `std_idst_clsf_cd_name`(실측: SK하이닉스·DB하이텍 = "반도체 제조업", 삼성전자 = "통신 및 방송 장비 제조업", 한미반도체 = "특수 목적용 기계 제조업") → 자동 선별 + 대표 종목 수동 보강(`batch/build_universe.py`).

### 2-1. 한투 실측 결과 (2026-11-04, 005930·000660, 실전 계좌)
- 현재가(`inquire-price`): `per`, `pbr`, `hts_avls`(억원 단위로 보이며 삼성전자 시총 약 1,277조원과 일치), `w52_hgpr`, `w52_lwpr`, `w52_hgpr_vrss_prpr_ctrt`, `w52_lwpr_vrss_prpr_ctrt` 모두 값이 들어옴.
- 기간별시세: 90일 요청에 60거래일 반환, 정렬해서 사용. `acml_tr_pbmn`(거래대금)·`acml_vol` 사용.
- 배당일정: 응답 필드 `record_date`(YYYYMMDD), `divi_pay_dt`(YYYY/MM/DD 형식), `per_sto_divi_amt`, `divi_kind`(분기/결산 등)를 확인. 삼성전자는 분기배당 포함 32건(8년 조회 시 가장 오래된 기준일 2018-12-31). **분기배당이 따로 나오므로 연간 배당은 연도별 합산**한다. 조회 가능한 최대 과거 범위는 아직 모름(8년까지는 확인).
- 토큰 발급·재사용은 정상. 호출 간격 0.6초에서 수집 2,725건 모두 성공(실패 0).

## 3. DART 9개 지표 (재무제표)
공통: `corpCode.xml`로 종목코드→corp_code 매핑(`corp_codes` 표), `fnlttSinglAcntAll.json`(단일회사 전체 재무제표)을 연결(CFS) 우선, 데이터가 없으면 별도(OFS)로 폴백하고 사용한 기준을 `financials.basis`에 남긴다. 계정은 `account_id`(XBRL) 우선, 이름은 보조. 매핑 실패는 로그에 남기고 지표는 None. 수집 결과는 SQLite에 캐시하고 요청 시점에는 DART를 부르지 않는다. 기준(TTM 등)은 `config.py`와 `indicators/calc_financial.py` 주석 한 곳.

| id | 지표 | 계산식 | 사용 계정(account_id 후보) | 상태 |
|---|---|---|---|---|
| 1 | 부채비율 | 부채총계 / 자본총계 × 100 (가장 최근 분기 재무상태표) | ifrs-full_Liabilities, ifrs-full_Equity | id 미확인 |
| 2 | 차입금의존도 | (단기차입금+유동성장기부채+장기차입금+사채) / 자산총계 × 100 | ifrs-full_CurrentBorrowings, NoncurrentBorrowings, 사채 등 | **id 미확인(회사마다 다름)** |
| 3 | EBITDA/금융비용 | (TTM 영업이익 + TTM 감가상각비·무형자산상각비) / TTM 금융비용 | dart_OperatingIncomeLoss, 현금흐름표 상각비, ifrs-full_FinanceCosts | id 미확인 |
| 4 | 자본잠식률 | (자본금 − 자본총계) / 자본금 × 100, 0 미만이면 0 | ifrs-full_IssuedCapital, ifrs-full_Equity | id 미확인 |
| 5 | 영업이익 | TTM = 직전 사업연도 + 당기 누적 − 전년 동기 누적 | dart_OperatingIncomeLoss | id 미확인 |
| 6 | 연속 영업흑자 연수 | 사업보고서 기준 연간 영업이익 > 0 을 최근 연도부터 거꾸로 센다 | 〃 | 조회 가능 연도 수 미확인 |
| 7 | 매출순이익률 | TTM 당기순이익 / TTM 매출액 × 100 | ifrs-full_ProfitLoss, ifrs-full_Revenue | id 미확인 |
| 8 | 매출액 증가율 | (당기 누적 − 전년 동기 누적) / 전년 동기 누적 × 100 | ifrs-full_Revenue | id 미확인 |
| 9 | 영업이익 증가율 | 〃 (영업이익 기준) | dart_OperatingIncomeLoss | id 미확인 |

- 반도체 업종만 대상(금융업 계정 구조 고려 안 함).
- 보고서 코드: 11013(1분기) 11012(반기) 11014(3분기) 11011(사업). 필드(`thstrm_amount`, `thstrm_add_amount`, `frmtrm_amount`, `frmtrm_add_amount`, `sj_div`)는 내 지식 기준이며 **DART 키로 실측 전**이다.


### 3-1. DART 실측 결과 (2026-11-04, 005930·000660, 사업보고서 2024 / 1분기보고서 2025)
- `fnlttSinglAcntAll.json` 호출 성공, 두 종목 모두 연결(CFS) 기준으로 213~236개 계정. `sj_div`는 BS·CIS(포괄손익, IS 아님)·CF·SCE.
- 사업보고서: `thstrm_amount`=연간 금액, `thstrm_add_amount` 없음. 1분기보고서: 손익은 `thstrm_amount`=당분기, `thstrm_add_amount`=누적, `frmtrm_add_amount`=전년 동기 누적(`frmtrm_amount`는 비어 있음). → TTM·증가율은 "누적" 필드로 계산한다.
- 확인된 account_id: 부채총계 `ifrs-full_Liabilities`, 자본총계 `ifrs-full_Equity`, 자산총계 `ifrs-full_Assets`, 자본금 `ifrs-full_IssuedCapital`, 영업이익 `dart_OperatingIncomeLoss`, 금융비용 `ifrs-full_FinanceCosts`, 당기순이익 `ifrs-full_ProfitLoss`, 매출액 `ifrs-full_Revenue`.
- **차입금은 회사마다 다르다**: SK하이닉스 = `ifrs-full_CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings` + `ifrs-full_LongtermBorrowings`. 삼성전자 = 단기차입금(`-표준계정코드 미사용-`, 이름으로만 구분) + 사채 `ifrs-full_NoncurrentPortionOfNoncurrentBondsIssued` + 장기차입금 `ifrs-full_NoncurrentPortionOfNoncurrentLoansReceived`. → **결정: 계정 id 목록 + 이름("차입금", "사채") 보조로 합산, 매핑 실패는 로그에 남기고 None.**
- **감가상각비·무형자산상각비 계정이 응답에 없다**(두 종목 모두 현금흐름표가 요약형). 따라서 **EBITDA/금융비용(id 3)은 이 API만으로 계산할 수 없다.** **결정(2026-11-04, 품질 기준으로 개발자가 정함): 상각비 계정이 있으면 정확한 EBITDA로 계산하고, 없으면 영업이익÷금융비용으로 대체하되 값에 `approx=true`를 붙여 판정서에 "(근사)"로 표시한다.**
- 일부 계정 행은 SCE처럼 같은 id가 여러 번 나온다 → 계산은 `sj_div`를 BS/CIS로 제한해서 찾는다.

## 4. LLM
- 어댑터 `llm/provider.py`: `complete_json(system, user, sample, provider)`. 원칙 변환(FR-01)은 `LLM_PROVIDER`(anthropic|local), 종합 리포트는 항상 Anthropic.
- Anthropic: `POST https://api.anthropic.com/v1/messages`, 헤더 `x-api-key`·`anthropic-version: 2023-06-01`, 모델 `LLM_MODEL`(기본 `claude-haiku-5-5`). 모델 ID·응답 형식은 공식 문서(docs.claude.com)와 실호출로 확인 필요(키 없음).
- 로컬: Ollama `POST {LOCAL_LLM_URL}/api/chat`(`format: json`, `think: false`, `temperature: 0`). 실제 모델 호출은 모델 파일이 없어 **미확인**.
- 원칙 변환 프롬프트(Haiku): 시스템 프롬프트에 지표표 20개와 규칙(임계값이 불명확하면 추측 말고 되묻기, 20개 지표로만 변환, 잠긴 지표 변경 금지)을 넣고, 출력은 `needs_clarification, clarify, name, anchors, indicators, explain_bubble, explain_card`.
- 원칙 변환(로컬 Qwen3-8B, 2026-11-05): 팀 학습 데이터와 같은 system 문구·입력 형식으로 부르고, 학습 형식 출력(되묻기 `reason`, 수정 `changes`/`skipped_locked`, 거절 `refusal`, 20개 세트)을 `llm/principle.py` `from_trained`가 위 형식으로 바꾼다. 상세는 `members/hyeonkyeong/README.md`의 "로컬 모델 입출력 계약".
- 두 경로 모두 `services/principles.py` `normalize`가 20개 화이트리스트·범위·연산자(양방향 지표 5·14·15·16·17 포함)·잠금 불변을 검증한다. 모델이 `source=default`로 채운 지표는 사용자 조건으로 쓰지 않는다.
- 리포트 프롬프트: `project_details/07_종합리포트_LLM_설계.md`의 시스템 프롬프트·출력 스키마를 그대로 쓴다. 금지 표현: "추천", "사세요", "더 좋아요", "유리해요". 출력 JSON(headline, what_changed, comparison, stock_changes, cautions, think_about) 외 글 금지, 입력에 없는 숫자·원인 금지. 실패 시 재요청 2회 후 템플릿 대체. (구현: 5단계)

## 5. 확인하지 못한 항목 (확인 요청)
1. 한투 호출 한도 수치와 토큰 발급 횟수 제한·만료 처리(실측: 신규 계정으로 보이며 0.12초 간격은 실패, 0.6초는 성공). 공식 문서 확인 후 `config.py` 조정.
2. (해결) 한투 현재가·일봉·배당일정 필드명 실측 완료(2-1절). 남은 확인: 배당 조회 가능 과거 한계, 일봉 조회 가능 과거 한계.
3. 모의투자(`KIS_ENV=mock`)에서 현재가·기간별시세·배당일정·종목기본정보 지원 여부 미확인(현재가·기간별시세는 예제에 모의 TR ID가 있음).
4. 배당일정으로 조회 가능한 과거 범위, 일봉 조회 가능 과거 범위.
5. DART 일일 호출 한도 실측, EBITDA/금융비용(id 3)의 상각비 원천(위 3-1 참고).
6. 60일 변동성(연환산 여부), 거래량 증가 배율(분모 기간)의 정확한 정의.
7. Anthropic: `claude-haiku-5-5`로 실호출 성공(2026-11-04, JSON 응답 확인). 로컬 모델 서빙 방식은 미확인.
8. (해결 2026-11-05) 07 문서 샘플 종목을 반도체 종목으로 교체함(수치는 가짜 그대로).

## 6. 계산 구현에서 내가 정한 기준 (확인 필요, 코드: `indicators/calc_price.py`, `calc_financial.py` 상수·주석)
- **기간 수익률(id 15)**: 기본 3개월(`PERIOD_RETURN_MONTHS`). 원칙에 기간이 따로 없어 정한 값이다. 시뮬레이션에서는 선택한 기간을 쓴다. 로컬 모델이 기간을 되물어 정하면 원칙에 `period_months`로 저장만 하고, 판정 계산은 아직 3개월 그대로다.
- **60일 변동성(id 18)**: 최근 60거래일 일간 수익률의 표준편차(%), 연환산 안 함(UI 샘플 "2% 이하"에 맞춤).
- **거래량 증가 배율(id 20)**: 최근 1거래일 거래량 / 직전 20거래일 평균 거래량.
- **연속 배당 연수(id 13)**: 직전 완료 연도부터 거꾸로 센다. 조회 구간이 8년이라 최대 8년.
- **오늘 값의 52주 고점·저점 대비(16, 17)**: 한투 현재가의 `w52_*_vrss_prpr_ctrt`. 과거 시점(시뮬레이션)은 일봉 종가로 다시 계산.
- **과거 시점의 PER·PBR·시가총액(10, 11, 14)**: 과거 값을 받을 수 없어 "현재 값 × (그날 종가 / 현재 종가)"로 근사하고 `approx`를 붙인다.
- **재무 지표의 과거 시점**: 보고서 공시일(1분기 5/15, 반기 8/14, 3분기 11/14, 사업 다음 해 3/31) 이후에만 해당 보고서를 쓴다.
- 데이터가 없는 지표는 값이 None이고 판정서에 "데이터 없음", 판정은 미충족으로 처리한다.
- **차입금의존도(id 2)**: 차입금·사채 계정이 없는 종목은 무차입으로 보고 0%(근사)로 처리한다(실측: 소형 반도체주 다수가 해당. 단 `기타금융부채`에 차입금이 섞인 회사는 과소 평가될 수 있음).
- **"조건에 맞는 종목"(추천·시뮬레이션)**: 원칙은 항상 20개 지표를 갖지만(사용자가 안 정한 지표는 기본값), 20개를 모두 통과하는 종목은 거의 없다. 그래서 **사용자가 정한 지표(source=user/inferred)를 모두 충족**하는 종목을 "조건에 맞는 종목"으로 본다(정한 지표가 없으면 20개 전부). 판정서의 충족 개수(14/20)는 20개 기준 그대로. 시뮬레이션은 "A에서 사용자가 정한 지표 + 이번에 고친 지표"를 같은 지표 집합으로 A, B에 적용한다.
- **시뮬레이션 기준**: T0 = 오늘 − n개월(3·6·12), 수익률 = 오늘 종가/T0 종가 − 1(배당 제외), 최대 하락 = T0~오늘 종가 기준 고점 대비 최대 낙폭, 종목 풀 = T0 가격이 있는 반도체 종목.
- **종합 리포트**: Haiku 응답이 길어 `max_tokens=4096`이 필요(1500에서는 JSON이 잘림). 검사(스키마·입력에 없는 숫자·금지어) 실패 시 재요청 2회 후 템플릿. 응답 시간은 리포트 포함 약 10~15초라 NFR 10초를 넘을 수 있어 `with_report=false`로 숫자표를 먼저 받을 수 있게 했다.

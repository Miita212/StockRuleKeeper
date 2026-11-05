# 인터페이스 약속

팀원끼리 주고받는 함수 이름과 데이터 형식을 여기에 정해 둡니다. 바꿀 때는 아래 변경 기록에도 남겨 주세요.

## 함수 / 데이터 약속

| 담당자 | 모듈(파일) | 함수 이름 | 입력(이름: 형식) | 출력(형식) | 예시 | 비고 |
|--------|-----------|-----------|------------------|------------|------|------|
|        |           |           |                  |            |      |      |
| (작성 팀원 확인 필요) | stock_indicators/run.py | get_indicators | query: str(종목명 또는 6자리 코드), period_months: int = 3 | `{"symbol", "name", "period_months", "indicators": {1~20: {"id","name","value","unit","as_of","status","note"}}}` | get_indicators("삼성전자", 3) | 지표 20개 한 번에(수십 초). `value`가 None이면 계산 불가(미충족 아님), 사유는 status/note. 금액 지표 5·14·19는 **억원**으로 변환된 값 |
| (작성 팀원 확인 필요) | stock_indicators/run.py | get_indicator | query: str, indicator: int(1~20) 또는 지표 이름, period_months: int = 3 | 위 indicators 값 하나 | get_indicator("삼성전자", 1) | 지표 10·11(PER/PBR)은 KIS 제공값(직전 결산 EPS/BPS) 기준 |

## 변경 기록

| 날짜 | 변경한 사람 | 바뀐 내용 | 이유 | 영향받는 사람 |
|------|------------|-----------|------|---------------|
|      |            |           |      |               |
| 2026-11-05 | hyeonkyeong | stock_indicators의 get_indicators / get_indicator 형식 추가 | 지표 20개 계산 모듈 통합 준비 | 백엔드(hyeonkyeong): 금액 지표는 억원이라 어댑터에서 원으로 변환 필요 |

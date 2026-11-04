"""핵심 지표 20개 목록.

출처: 핵심지표20개.xlsx (2026-11-03). 단위(unit)와 값 범위(lo, hi)는 잠정값이다.
KIS/OpenDART 실제 응답으로 검증하기 전이므로 확정하지 않는다.
LLM이 만든 조건의 indicator는 반드시 이 목록의 code 안에서만 고를 수 있다.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Indicator:
    code: str          # LLM 출력에 쓰는 영문 코드
    name: str          # 한글 이름
    area: str          # 영역(UI 카테고리)
    unit: str          # 잠정 단위
    lo: float          # 잠정 허용 하한 (비현실적 임계값 거르기용)
    hi: float          # 잠정 허용 상한
    needs_period: bool = False  # 기간 파라미터(개월)가 필요한 지표


_ROWS = [
    ("DEBT_RATIO", "부채비율", "재무 건전성", "%", 0, 2000),
    ("BORROWING_DEPENDENCY", "차입금의존도", "재무 건전성", "%", 0, 100),
    ("EBITDA_INTEREST_COVER", "EBITDA/금융비용", "재무 건전성", "배", 0, 1000),
    ("CAPITAL_IMPAIRMENT", "자본잠식률", "재무 건전성", "%", 0, 100),
    ("OPERATING_PROFIT", "영업이익", "수익성", "억원", -100000, 1000000),
    ("CONSECUTIVE_PROFIT_YEARS", "연속 영업흑자 연수", "수익성", "년", 0, 30),
    ("NET_MARGIN", "매출순이익률", "수익성", "%", -100, 100),
    ("REVENUE_GROWTH", "매출액 증가율", "성장성", "%", -100, 1000),
    ("OPERATING_PROFIT_GROWTH", "영업이익 증가율", "성장성", "%", -1000, 10000),
    ("PER", "PER", "가치", "배", 0, 500),
    ("PBR", "PBR", "가치", "배", 0, 50),
    ("DIVIDEND_YIELD_12M", "최근 12개월 현금배당수익률", "배당", "%", 0, 30),
    ("CONSECUTIVE_DIVIDEND_YEARS", "연속 현금배당 연수", "배당", "년", 0, 50),
    ("MARKET_CAP", "시가총액", "규모", "억원", 0, 10000000),
    ("PERIOD_RETURN", "기간 수익률", "주가·거래", "%", -100, 1000, True),
    ("FROM_52W_HIGH", "52주 최고가 대비 등락률", "주가·거래", "%", -100, 0),
    ("FROM_52W_LOW", "52주 최저가 대비 상승률", "주가·거래", "%", 0, 10000),
    ("VOLATILITY_60D", "최근 60거래일 변동성", "주가·거래", "%", 0, 200),
    ("AVG_TRADING_VALUE_20D", "최근 20거래일 평균 거래대금", "주가·거래", "억원", 0, 1000000),
    ("VOLUME_SURGE_RATIO", "거래량 증가 배율", "주가·거래", "배", 0, 1000),
]

INDICATORS = {r[0]: Indicator(*r) for r in _ROWS}
assert len(INDICATORS) == 20


def get(code: str) -> Optional[Indicator]:
    return INDICATORS.get(code)

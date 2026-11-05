"""시세·배당 계열 11개 지표 계산 (한투 데이터).

입력은 우리 내부 스키마(external/kis/quotes.py 참고). 결과는 {지표 id: {"value", "approx"}}.
- as_of가 오늘이 아니면 과거 시점 값을 일봉·배당 이력으로 다시 계산한다.
  PER·PBR·시가총액은 과거 값을 받을 수 없어 "현재 값 × (그날 종가 / 현재 종가)"로 근사한다(approx=True).
계산 기준(바꾸려면 여기 상수):
"""
from datetime import date, timedelta
from statistics import mean, pstdev

PERIOD_RETURN_MONTHS = 3     # 기간 수익률(id 15)의 기본 기간. 시뮬레이션에서는 선택한 기간을 넘긴다.
VOLATILITY_DAYS = 60         # 변동성(id 18): 최근 60거래일 일간 수익률의 표준편차(%), 연환산 안 함
TRADING_VALUE_DAYS = 20      # 거래대금(id 19)
VOLUME_BASE_DAYS = 20        # 거래량 배율(id 20): 최근 1거래일 거래량 / 직전 20거래일 평균
WEEKS_52 = 252               # 52주 ≈ 252거래일


def _upto(daily: list[dict], as_of: date) -> list[dict]:
    d = as_of.isoformat()
    return [r for r in daily if r["date"] <= d and r["close"]]


def _months_ago(d: date, months: int) -> date:
    y, m = divmod(d.year * 12 + d.month - 1 - months, 12)
    return date(y, m + 1, min(d.day, 28))


def compute_price_indicators(daily: list[dict], dividends: list[dict], snapshot: dict | None,
                             as_of: date, period_months: int = PERIOD_RETURN_MONTHS) -> dict:
    out: dict[int, dict] = {}
    rows = _upto(daily, as_of)
    if not rows:
        return out
    close = rows[-1]["close"]

    def put(i, v, approx=False):
        out[i] = {"value": v, "approx": approx}

    # PER·PBR·시가총액(10, 11, 14)
    if snapshot:
        scale, approx = (1.0, False) if as_of >= date.today() else (None, True)
        if scale is None and snapshot.get("price"):
            scale = close / snapshot["price"]
        for i, key in ((10, "per"), (11, "pbr"), (14, "market_cap_won")):
            v = snapshot.get(key)
            put(i, v * scale if v is not None and scale is not None else None, approx)

    # 52주 고점·저점 대비(16, 17): 일봉 종가 기준
    window = rows[-WEEKS_52:]
    hi, lo = max(r["close"] for r in window), min(r["close"] for r in window)
    live = snapshot if snapshot and as_of >= date.today() else None  # 오늘 값은 한투 현재가 응답의 52주 필드를 쓴다
    put(16, live["from_high_pct"] if live and live.get("from_high_pct") is not None else (close / hi - 1) * 100)
    put(17, live["from_low_pct"] if live and live.get("from_low_pct") is not None else (close / lo - 1) * 100)

    # 기간 수익률(15)
    start = [r for r in rows if r["date"] <= _months_ago(as_of, period_months).isoformat()]
    put(15, (close / start[-1]["close"] - 1) * 100 if start else None)

    # 변동성(18)
    recent = rows[-(VOLATILITY_DAYS + 1):]
    rets = [(b["close"] / a["close"] - 1) * 100 for a, b in zip(recent, recent[1:])]
    put(18, pstdev(rets) if len(rets) >= VOLATILITY_DAYS else None)

    # 평균 거래대금(19), 거래량 증가 배율(20)
    vals = [r["value"] for r in rows[-TRADING_VALUE_DAYS:] if r["value"] is not None]
    put(19, mean(vals) if len(vals) == TRADING_VALUE_DAYS else None)
    base = [r["volume"] for r in rows[-(VOLUME_BASE_DAYS + 1):-1] if r["volume"] is not None]
    put(20, rows[-1]["volume"] / mean(base) if len(base) == VOLUME_BASE_DAYS and mean(base) else None)

    # 12개월 배당수익률(12): 최근 12개월 기준일 주당배당금 합 / 종가
    year_ago = (as_of - timedelta(days=365)).isoformat()
    paid = [d["amount_per_share"] or 0 for d in dividends
            if d["record_date"] and year_ago < d["record_date"] <= as_of.isoformat()]
    put(12, sum(paid) / close * 100)

    # 연속 배당 연수(13): 직전 완료 연도부터 거꾸로, 연간 주당배당금 합이 0보다 큰 해를 센다
    by_year: dict[int, float] = {}
    for d in dividends:
        if d["record_date"] and d["record_date"] <= as_of.isoformat():
            y = int(d["record_date"][:4])
            by_year[y] = by_year.get(y, 0) + (d["amount_per_share"] or 0)
    years, y = 0, as_of.year - 1
    while by_year.get(y, 0) > 0:
        years += 1
        y -= 1
    # 배당이 끊겨서 멈춘 게 아니라 조회한 이력이 끝나서 멈췄으면 "N년 이상"이다
    out[13] = {"value": float(years), "approx": False, "at_least": bool(by_year) and y < min(by_year)}
    return out

"""검색한 종목과 판정서에서 한투의 최신 데이터를 API로 받아 계산에 쓴다. DB에는 저장하지 않는다.

- DB 갱신은 개발자가 batch/collect_data.py 를 돌릴 때만 한다(앱을 쓰는 중에는 DB에 쓰지 않는다).
- 한투: 현재가 스냅샷, 일봉(DB 마지막 날짜 이후), 배당을 받는다. DART 재무제표는 DB 값을 쓴다.
- 같은 종목은 LIVE_TTL_SEC 안에는 받은 값을 메모리에서 다시 쓴다.
- 받기에 실패하면 None 을 돌려주고, 호출한 쪽이 DB 값으로 계산한다.
"""
import json
import time
from datetime import date, timedelta

import config
from batch.collect_data import PRICE_DAYS, DIVIDEND_YEARS
from db.database import connect
from external.kis import quotes

_fetched: dict[str, tuple[float, dict]] = {}


def enabled() -> bool:
    return config.EXTERNAL_MODE == "live" and config.LIVE_FETCH


def seed_stocks() -> None:
    """stocks 표가 비어 있을 때만(처음 한 번) 종목 풀 파일(data/semiconductor_universe.json)로 채운다."""
    with connect() as conn:
        if conn.execute("SELECT 1 FROM stocks LIMIT 1").fetchone():
            return
        f = config.ROOT / "data" / "semiconductor_universe.json"
        stocks = json.loads(f.read_text(encoding="utf-8"))["stocks"]
        conn.executemany("INSERT OR REPLACE INTO stocks(code, name, market, industry_name, source) VALUES (?,?,?,?,?)",
                         [(s["code"], s["name"], s.get("market"), s.get("industry_name"), s["source"]) for s in stocks])
        conn.commit()


def fetch_kis(conn, code: str) -> dict | None:
    """{"snapshot", "daily", "dividends"}. 한투 API로 받은 값을 돌려준다(DB에 쓰지 않는다)."""
    if not enabled():
        return None
    hit = _fetched.get(code)
    if hit and time.time() - hit[0] < config.LIVE_TTL_SEC:
        return hit[1]
    try:
        today = date.today()
        count, last = conn.execute("SELECT COUNT(*), MAX(date) FROM prices_daily WHERE code=?", (code,)).fetchone()
        start = today - timedelta(days=PRICE_DAYS) if count < 400 else date.fromisoformat(last)
        data = {
            "daily": quotes.get_daily_prices(code, start, today),
            "snapshot": quotes.get_snapshot(code),
            "dividends": [d for d in quotes.get_dividends(code, today - timedelta(days=365 * DIVIDEND_YEARS), today)
                          if d["record_date"]],
        }
    except Exception as e:  # API 실패 때는 DB 값으로 계산한다
        print(f"[live] 한투 {code} 실패, DB 값 사용: {type(e).__name__}: {e}", flush=True)
        return None
    _fetched[code] = (time.time(), data)
    return data

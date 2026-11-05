"""요청 시점에 한투에서 최신 데이터를 받아 DB에 저장한다. (한투는 API 우선, DART 재무는 DB 값을 쓴다)

- 현재가 스냅샷은 매번, 일봉은 마지막 저장일 이후만, 배당은 DB에 없을 때만 받는다.
- DART 재무제표는 분기마다만 바뀌므로 요청 때 부르지 않는다(batch/collect_data.py 로 DB에 채운다).
- 같은 종목은 LIVE_TTL_SEC 안에는 다시 받지 않는다.
- 받기에 실패하면 DB에 있는 값을 그대로 쓴다.
"""
import json
import threading
import time
from datetime import date, datetime, timedelta

import config
from batch.collect_data import PRICE_DAYS, DIVIDEND_YEARS
from db.database import connect
from external.kis import quotes

_fetched_at: dict[str, float] = {}
_lock = threading.Lock()  # 목록과 추천이 동시에 요청돼도 같은 종목을 두 번 받지 않는다


def enabled() -> bool:
    return config.EXTERNAL_MODE == "live" and config.LIVE_FETCH


def seed_stocks() -> None:
    """stocks 표가 비어 있으면 종목 풀 파일(data/semiconductor_universe.json)로 채운다."""
    with connect() as conn:
        if conn.execute("SELECT 1 FROM stocks LIMIT 1").fetchone():
            return
        f = config.ROOT / "data" / "semiconductor_universe.json"
        stocks = json.loads(f.read_text(encoding="utf-8"))["stocks"]
        conn.executemany("INSERT OR REPLACE INTO stocks(code, name, market, industry_name, source) VALUES (?,?,?,?,?)",
                         [(s["code"], s["name"], s.get("market"), s.get("industry_name"), s["source"]) for s in stocks])
        conn.commit()


def _refresh_kis(conn, code: str) -> None:
    today = date.today()
    count, last = conn.execute("SELECT COUNT(*), MAX(date) FROM prices_daily WHERE code=?", (code,)).fetchone()
    start = today - timedelta(days=PRICE_DAYS) if count < 400 else date.fromisoformat(last)
    rows = quotes.get_daily_prices(code, start, today)
    conn.executemany("INSERT OR REPLACE INTO prices_daily(code,date,close,volume,value) VALUES (?,?,?,?,?)",
                     [(code, r["date"], r["close"], r["volume"], r["value"]) for r in rows])
    snap = quotes.get_snapshot(code)
    conn.execute("INSERT OR REPLACE INTO snapshots(code, fetched_at, json) VALUES (?,?,?)",
                 (code, datetime.now().isoformat(timespec="seconds"), json.dumps(snap)))
    if not conn.execute("SELECT 1 FROM dividends WHERE code=? LIMIT 1", (code,)).fetchone():
        divs = quotes.get_dividends(code, today - timedelta(days=365 * DIVIDEND_YEARS), today)
        conn.executemany(
            "INSERT OR REPLACE INTO dividends(code,record_date,pay_date,amount_per_share,kind) VALUES (?,?,?,?,?)",
            [(code, d["record_date"], d["pay_date"], d["amount_per_share"], d["kind"]) for d in divs if d["record_date"]])


def ensure_fresh(conn, code: str) -> None:
    """종목 하나의 한투 데이터를 API로 받아 DB에 저장한다. 실패하면 DB 값을 그대로 쓴다."""
    if not enabled():
        return
    with _lock:
        if time.time() - _fetched_at.get(code, 0) < config.LIVE_TTL_SEC:
            return
        try:
            _refresh_kis(conn, code)
            conn.commit()
        except Exception as e:  # API 실패 때는 DB 값으로 계속한다
            conn.rollback()
            print(f"[live] 한투 {code} 실패, DB 값 사용: {type(e).__name__}: {e}", flush=True)
        _fetched_at[code] = time.time()

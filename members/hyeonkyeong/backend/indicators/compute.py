"""DB에 저장된 수집 데이터로 종목의 지표 20개를 계산한다(요청 시점에 외부 API를 부르지 않는다)."""
import json
import sqlite3
from datetime import date

from indicators.calc_financial import compute_financial_indicators
from indicators.calc_price import PERIOD_RETURN_MONTHS, compute_price_indicators


def load_inputs(conn: sqlite3.Connection, code: str) -> dict:
    daily = [dict(r) for r in conn.execute(
        "SELECT date, close, volume, value FROM prices_daily WHERE code=? ORDER BY date", (code,))]
    dividends = [dict(r) for r in conn.execute(
        "SELECT record_date, pay_date, amount_per_share, kind FROM dividends WHERE code=?", (code,))]
    snap = conn.execute("SELECT json FROM snapshots WHERE code=? ORDER BY fetched_at DESC LIMIT 1", (code,)).fetchone()
    reports = {(r["year"], r["reprt_code"]): {"basis": r["basis"], "rows": json.loads(r["rows_json"])}
               for r in conn.execute("SELECT year, reprt_code, basis, rows_json FROM financials WHERE code=?", (code,))}
    return {"daily": daily, "dividends": dividends, "snapshot": json.loads(snap["json"]) if snap else None,
            "reports": reports}


def compute_all(conn: sqlite3.Connection, code: str, as_of: date | None = None,
                period_months: int = PERIOD_RETURN_MONTHS, inputs: dict | None = None) -> dict:
    """{지표 id: {"value", "approx"}}. 계산할 수 없는 지표는 value=None 이거나 빠진다."""
    as_of = as_of or date.today()
    d = inputs or load_inputs(conn, code)
    out = compute_price_indicators(d["daily"], d["dividends"], d["snapshot"], as_of, period_months)
    out.update(compute_financial_indicators(d["reports"], as_of, code))
    return out

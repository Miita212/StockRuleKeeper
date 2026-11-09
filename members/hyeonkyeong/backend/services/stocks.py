"""종목 풀(반도체 113개) 조회, 원칙 기준 판정, 추천. 판정은 모두 코드가 한다.

목록·추천은 DB 값만 읽는다(마지막 수집 시점의 값). 종목 검색(q)과 판정서는 한투 API로 받은 최신 값으로 계산하되
DB에는 저장하지 않는다(services/live.py). DB 갱신은 batch/collect_data.py 를 돌릴 때만 한다.
"""
import sqlite3
import time
from datetime import date, datetime

import config
from indicators.compute import compute_all, load_inputs
from indicators.judge import judge_stock
from services import principles as principle_svc
from services.live import fetch_kis

_cache: dict[str, tuple[float, dict]] = {}


def live_inputs(conn: sqlite3.Connection, code: str) -> dict:
    """DB 입력에 한투 최신 값(현재가·최근 일봉·배당)을 덮어쓴 계산 입력. 한투 호출이 실패하면 DB 값 그대로."""
    inputs = load_inputs(conn, code)
    fresh = fetch_kis(conn, code)
    if fresh:
        inputs["snapshot"] = fresh["snapshot"]
        daily = {r["date"]: r for r in inputs["daily"]}
        daily.update({r["date"]: r for r in fresh["daily"]})
        inputs["daily"] = [daily[d] for d in sorted(daily)]
        if fresh["dividends"]:
            inputs["dividends"] = fresh["dividends"]
    return inputs


def actuals(conn: sqlite3.Connection, code: str, inputs: dict | None = None) -> dict:
    """inputs 가 있으면(한투 최신 값) 그걸로 계산하고, 없으면 DB 값으로 계산해 LIVE_TTL_SEC 동안 캐시한다."""
    if inputs is not None:
        return compute_all(conn, code, inputs=inputs)
    hit = _cache.get(code)
    if hit and time.time() - hit[0] < config.LIVE_TTL_SEC:
        return hit[1]
    value = compute_all(conn, code)
    _cache[code] = (time.time(), value)
    return value


def clear_cache() -> None:
    _cache.clear()


def resolve_principle(conn: sqlite3.Connection, principle_id: int | None) -> list[dict]:
    """판정에 쓸 원칙 지표 20개. principle_id가 없으면 가장 최근 원칙, 원칙이 하나도 없으면 기본값."""
    if principle_id is None:
        row = conn.execute("SELECT id FROM principles WHERE user_id=? ORDER BY id DESC LIMIT 1",
                           (config.FIXED_USER_ID,)).fetchone()
        principle_id = row["id"] if row else None
    if principle_id is None:
        return principle_svc.default_indicators()
    p = principle_svc.get(conn, principle_id)
    if not p:
        raise KeyError(principle_id)
    return p["indicators"]


def day_change(conn: sqlite3.Connection, code: str, daily: list[dict] | None = None) -> float:
    """직전 거래일 대비 등락률(%). daily 가 있으면(한투 최신 값 포함) 그걸 쓴다."""
    if daily is None:
        rows = conn.execute("SELECT close FROM prices_daily WHERE code=? ORDER BY date DESC LIMIT 2", (code,)).fetchall()
    else:
        rows = daily[-1:-3:-1]
    return round((rows[0]["close"] / rows[1]["close"] - 1) * 100, 2) if len(rows) == 2 and rows[1]["close"] else 0.0


def price_basis(conn: sqlite3.Connection, code: str, daily: list[dict] | None = None) -> str:
    """등락률이 어느 가격 기준인지: 장중 오늘 값이면 "실시간", 아니면 "11/09 종가"."""
    if daily is None:
        row = conn.execute("SELECT MAX(date) AS d FROM prices_daily WHERE code=?", (code,)).fetchone()
        last = row["d"]
    else:
        last = daily[-1]["date"] if daily else None
    if not last:
        return ""
    now = datetime.now()
    if last == date.today().isoformat() and now.weekday() < 5 and (9, 0) <= (now.hour, now.minute) < (15, 40):
        return "실시간"
    return f"{int(last[5:7])}/{int(last[8:10])} 종가"


def stock_card(conn: sqlite3.Connection, row: sqlite3.Row, principle: list[dict], inputs: dict | None = None) -> dict:
    result = judge_stock(principle, actuals(conn, row["code"], inputs))
    core = principle_svc.core_ids(principle)  # 조건에 맞는 종목 = 사용자가 정한 지표를 모두 충족
    all_pass = all(r["pass"] for r in result["rows"] if r["indicator_id"] in core)
    return {"code": row["code"], "name": row["name"], "passCount": result["pass_count"], "total": result["total"],
            "allPass": all_pass, "changeRate": day_change(conn, row["code"], inputs["daily"] if inputs else None),
            "priceBasis": price_basis(conn, row["code"], inputs["daily"] if inputs else None)}


def list_stocks(conn: sqlite3.Connection, principle: list[dict], q: str = "", only_pass: bool = False,
                limit: int = 200) -> list[dict]:
    rows = conn.execute("SELECT code, name FROM stocks WHERE (name LIKE ? OR code LIKE ?)",
                        (f"%{q}%", f"%{q}%")).fetchall()
    live = q.strip() != ""  # 종목을 검색했을 때만 그 종목들을 한투 최신 값으로 계산한다
    cards = [stock_card(conn, r, principle, live_inputs(conn, r["code"]) if live else None) for r in rows]
    if only_pass:
        cards = [c for c in cards if c["allPass"]]
    cards.sort(key=lambda c: (-c["passCount"], c["name"]))
    return cards[:limit]


def verdict(conn: sqlite3.Connection, code: str, principle: list[dict]) -> dict | None:
    row = conn.execute("SELECT code, name FROM stocks WHERE code=?", (code,)).fetchone()
    if not row:
        return None
    inputs = live_inputs(conn, code)  # 판정서는 항상 한투 최신 값
    result = judge_stock(principle, actuals(conn, code, inputs))
    return {
        "stock": stock_card(conn, row, principle, inputs),
        "rows": [{"indicatorId": r["indicator_id"], "criterion": r["criterion"], "actual": r["actual"],
                  "pass": r["pass"], "hasData": r["has_data"]} for r in result["rows"]],
        "passCount": result["pass_count"], "total": result["total"],
    }

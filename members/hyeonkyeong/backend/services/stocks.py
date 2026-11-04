"""종목 풀(반도체 113개) 조회, 원칙 기준 판정, 추천. 판정은 모두 코드가 한다.

지표 계산은 DB에 저장된 수집 데이터만 읽는다(외부 API 호출 없음). 하루 동안은 종목별 계산 결과를 캐시한다.
"""
import sqlite3
from datetime import date

import config
from indicators.compute import compute_all
from indicators.judge import judge_stock
from services import principles as principle_svc

_cache: dict[str, tuple[str, dict]] = {}


def actuals(conn: sqlite3.Connection, code: str) -> dict:
    today = date.today().isoformat()
    hit = _cache.get(code)
    if hit and hit[0] == today:
        return hit[1]
    value = compute_all(conn, code)
    _cache[code] = (today, value)
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


def day_change(conn: sqlite3.Connection, code: str) -> float:
    """직전 거래일 대비 등락률(%)."""
    rows = conn.execute("SELECT close FROM prices_daily WHERE code=? ORDER BY date DESC LIMIT 2", (code,)).fetchall()
    return round((rows[0]["close"] / rows[1]["close"] - 1) * 100, 2) if len(rows) == 2 and rows[1]["close"] else 0.0


def stock_card(conn: sqlite3.Connection, row: sqlite3.Row, principle: list[dict]) -> dict:
    result = judge_stock(principle, actuals(conn, row["code"]))
    core = principle_svc.core_ids(principle)  # 조건에 맞는 종목 = 사용자가 정한 지표를 모두 충족
    all_pass = all(r["pass"] for r in result["rows"] if r["indicator_id"] in core)
    return {"code": row["code"], "name": row["name"], "passCount": result["pass_count"], "total": result["total"],
            "allPass": all_pass, "changeRate": day_change(conn, row["code"])}


def list_stocks(conn: sqlite3.Connection, principle: list[dict], q: str = "", only_pass: bool = False,
                limit: int = 200) -> list[dict]:
    rows = conn.execute("SELECT code, name FROM stocks WHERE (name LIKE ? OR code LIKE ?)",
                        (f"%{q}%", f"%{q}%")).fetchall()
    cards = [stock_card(conn, r, principle) for r in rows]
    if only_pass:
        cards = [c for c in cards if c["allPass"]]
    cards.sort(key=lambda c: (-c["passCount"], c["name"]))
    return cards[:limit]


def verdict(conn: sqlite3.Connection, code: str, principle: list[dict]) -> dict | None:
    row = conn.execute("SELECT code, name FROM stocks WHERE code=?", (code,)).fetchone()
    if not row:
        return None
    result = judge_stock(principle, actuals(conn, code))
    return {
        "stock": stock_card(conn, row, principle),
        "rows": [{"indicatorId": r["indicator_id"], "criterion": r["criterion"], "actual": r["actual"],
                  "pass": r["pass"], "hasData": r["has_data"]} for r in result["rows"]],
        "passCount": result["pass_count"], "total": result["total"],
    }

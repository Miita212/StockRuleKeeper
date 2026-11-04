"""원칙 시뮬레이션(FR-03): 원칙 A의 수치를 고친 B와 A를, n개월 전 시점의 데이터로 판정하고
그 뒤 오늘까지의 주가 변화를 비교한다. 숫자는 전부 코드가 계산한다(LLM은 문장만 쓴다).

계산 기준(07 설계의 '미정' 항목을 이렇게 정했다 — docs/external-api-notes.md 6절):
- 기준 시점 T0 = 오늘 − n개월. T0에 쓸 수 있던 데이터(일봉·배당·공시된 재무)로 지표를 다시 계산해 A, B를 판정한다.
- 수익률 = 오늘 종가 / T0 종가 − 1 (배당 제외 주가 기준).
- 기간 중 최대 하락 = T0~오늘 종가 기준 고점 대비 최대 낙폭. 평균은 조건에 맞은 종목의 평균.
- 조건에 맞는 종목 = 원칙의 지표를 모두 충족한 종목.
"""
import sqlite3
from datetime import date

from indicators.calc_price import _months_ago
from indicators.compute import compute_all, load_inputs
from indicators.judge import judge_stock
from indicators.master import MASTER, criterion_text
from services import principles as principle_svc
from services.principles import _valid_setting

_t0_cache: dict[tuple[str, str], dict] = {}


def apply_changes(base: list[dict], changes: list[dict]) -> tuple[list[dict], list[dict], list[str]]:
    """원칙 A에 수정(changes)을 적용해 B를 만든다. (B, 실제로 바뀐 항목, 경고)"""
    warnings: list[str] = []
    b = [dict(x) for x in base]
    by_id = {x["id"]: x for x in b}
    applied = []
    for ch in changes:
        ok = _valid_setting(ch, warnings)
        if not ok:
            continue
        cur = by_id[ok["id"]]
        if (cur["operator"], cur["value"]) == (ok["operator"], ok["value"]):
            continue
        applied.append({"id": ok["id"], "indicator": MASTER[ok["id"]]["name"],
                        "before": criterion_text(ok["id"], cur["operator"], cur["value"]),
                        "after": criterion_text(ok["id"], ok["operator"], ok["value"])})
        cur.update(operator=ok["operator"], value=ok["value"])
    return b, applied, warnings


def _path_stats(daily: list[dict], t0: date) -> dict | None:
    rows = [r for r in daily if r["close"]]
    start = [r for r in rows if r["date"] <= t0.isoformat()]
    if not start or not rows or rows[-1]["date"] <= start[-1]["date"]:
        return None
    window = [r for r in rows if r["date"] >= start[-1]["date"]]
    peak, worst = window[0]["close"], 0.0
    for r in window:
        peak = max(peak, r["close"])
        worst = min(worst, r["close"] / peak - 1)
    return {"return_pct": (window[-1]["close"] / window[0]["close"] - 1) * 100, "max_drawdown_pct": worst * 100,
            "start_date": window[0]["date"], "end_date": window[-1]["date"]}


def _avg(xs):
    return sum(xs) / len(xs) if xs else None


def _summary(items: list[dict]) -> dict:
    r = [i["return_pct"] for i in items]
    return {"passed_count": len(items),
            "avg_return_pct": round(_avg(r), 1) if r else None,
            "up_ratio_pct": round(sum(x > 0 for x in r) / len(r) * 100) if r else None,
            "avg_max_drawdown_pct": round(_avg([i["max_drawdown_pct"] for i in items]), 1) if items else None}


def _failed_by(judged: dict, changed_names: set[str]) -> str:
    """B(또는 A)를 통과하지 못한 이유: 코드의 판정 근거를 그대로 쓴다."""
    fails = [r for r in judged["rows"] if not r["pass"]]
    fails.sort(key=lambda r: MASTER[r["indicator_id"]]["name"] not in changed_names)
    r = fails[0]
    return f"{MASTER[r['indicator_id']]['name']} {r['actual']}"


def run(conn: sqlite3.Connection, a: list[dict], changes: list[dict], months: int,
        today: date | None = None) -> dict:
    today = today or date.today()
    t0 = _months_ago(today, months)
    b, applied, warnings = apply_changes(a, changes)
    changed_names = {c["indicator"] for c in applied}
    # 조건 = A에서 사용자가 정한 지표 + 이번에 고친 지표. 같은 지표 집합으로 A(수정 전)와 B(수정 후)를 판정한다.
    required = principle_svc.core_ids(a) | {c["id"] for c in applied}
    a_req = [i for i in a if i["id"] in required]
    b_req = [i for i in b if i["id"] in required]
    stocks = conn.execute("SELECT code, name FROM stocks ORDER BY code").fetchall()

    in_a, in_b, universe = [], [], 0
    judged_b = {}
    for s in stocks:
        inputs = load_inputs(conn, s["code"])
        path = _path_stats(inputs["daily"], t0)
        if not path:
            continue  # T0 시점 가격이 없는 종목은 비교에서 뺀다
        universe += 1
        key = (s["code"], t0.isoformat())
        if key not in _t0_cache:
            _t0_cache[key] = compute_all(conn, s["code"], as_of=t0, period_months=months, inputs=inputs)
        actual = _t0_cache[key]
        ja, jb = judge_stock(a_req, actual), judge_stock(b_req, actual)
        item = {"code": s["code"], "name": s["name"], **path}
        judged_b[s["code"]] = jb
        if ja["all_pass"]:
            in_a.append({**item, "judged": ja})
        if jb["all_pass"]:
            in_b.append({**item, "judged": jb})

    codes_a, codes_b = {i["code"] for i in in_a}, {i["code"] for i in in_b}
    dropped = [i for i in in_a if i["code"] not in codes_b]
    added = [i for i in in_b if i["code"] not in codes_a]

    def examples(items, judged_lookup):
        out = []
        for i in sorted(items, key=lambda x: -abs(x["return_pct"]))[:3]:
            out.append({"name": i["name"], "return_pct": round(i["return_pct"], 1),
                        "failed_by": _failed_by(judged_lookup(i), changed_names) if judged_lookup else ""})
        return out

    return {
        "period_months": months,
        "period": {"start": t0.isoformat(), "end": today.isoformat()},
        "universe": {"name": "반도체 업종", "size": universe},
        "changes": [{k: v for k, v in c.items() if k != "id"} for c in applied],
        "before": _summary(in_a),
        "after": _summary(in_b),
        "dropped_stocks": {"count": len(dropped), "avg_return_pct": round(_avg([i["return_pct"] for i in dropped]), 1) if dropped else None,
                           "examples": examples(dropped, lambda i: judged_b[i["code"]])},
        "added_stocks": {"count": len(added), "avg_return_pct": round(_avg([i["return_pct"] for i in added]), 1) if added else None,
                         "examples": [{"name": i["name"], "return_pct": round(i["return_pct"], 1), "failed_by": ""}
                                      for i in sorted(added, key=lambda x: -abs(x["return_pct"]))[:3]]},
        "data_notes": [
            "기간은 1개 구간만 계산함",
            "수익률은 배당 제외 주가 기준",
            "과거 시점의 PER·PBR·시가총액은 근사값",
        ],
        "warnings": warnings,
    }

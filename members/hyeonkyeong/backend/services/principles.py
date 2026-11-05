"""원칙 서비스: 모델 출력 검증·정규화(코드), 저장·버전 관리.

원칙 = 지표 20개 전부의 [{id, operator, value, unit, source, locked}] (value는 표시 단위).
"""
import json
import sqlite3

import config
from indicators.master import MASTER, RANGES, allowed_operators, criterion_text
from llm.principle import ask_model

GENERIC_CLARIFY = "어떤 기준으로 볼지 조금 더 알려 주세요. 예: '빚 적은 회사', '배당 꾸준한 회사'"


def default_indicators() -> list[dict]:
    return [{"id": i, "operator": m["operator"], "value": m["value"], "unit": m["unit"],
             "source": "default", "locked": False} for i, m in MASTER.items()]


def core_ids(indicators: list[dict]) -> set[int]:
    """"조건에 맞는 종목"을 가를 때 반드시 충족해야 하는 지표.
    사용자가 정한 지표(source=user/inferred)만이다. 기본값으로 채운 지표는 판정서에는 보이지만 조건에는 넣지 않는다.
    사용자가 정한 지표가 하나도 없으면 20개 전부를 조건으로 본다."""
    core = {x["id"] for x in indicators if x.get("source") in ("user", "inferred")}
    return core or {x["id"] for x in indicators}


def with_text(indicators: list[dict]) -> list[dict]:
    """화면용 기준 문구(criterion)를 붙인다."""
    return [{**x, "name": MASTER[x["id"]]["name"], "criterion": criterion_text(x["id"], x["operator"], x["value"])}
            for x in indicators]


def _valid_setting(s: dict, warnings: list[str]) -> dict | None:
    """모델이 낸 지표 한 개를 검증한다. 통과하면 정리된 dict, 아니면 None."""
    try:
        i, op, v = int(s["id"]), s["operator"], float(s["value"])
    except (KeyError, TypeError, ValueError):
        warnings.append(f"형식 오류: {s}")
        return None
    if i not in MASTER:
        warnings.append(f"20개 지표에 없는 id {i}")
        return None
    if op not in allowed_operators(i):
        warnings.append(f"{MASTER[i]['name']}: 허용되지 않는 연산자 {op}")
        return None
    lo, hi = RANGES[i]
    if not lo <= v <= hi:
        warnings.append(f"{MASTER[i]['name']}: 값 {v:g}이(가) 범위({lo}~{hi}) 밖")
        return None
    ok = {"id": i, "operator": op, "value": v, "source": s.get("source") if s.get("source") in ("user", "inferred") else "user"}
    if i == 15 and s.get("period_months"):
        ok["period_months"] = int(s["period_months"])
    return ok


def normalize(raw: dict, base: list[dict] | None, locked_ids: list[int]) -> dict:
    """모델 출력을 검증해 화면·저장에 쓸 결과로 만든다. 잠긴 지표는 이전 값으로 되돌린다."""
    warnings: list[str] = []
    locked = set(locked_ids)
    current = {x["id"]: dict(x) for x in (base or default_indicators())}
    for i in current:
        current[i]["locked"] = i in locked

    changed, blocked = [], []
    for s in raw.get("indicators") or []:
        if s.get("source") == "default":  # 모델이 기본값으로 채운 지표는 사용자 조건이 아니다(코드가 채운다)
            continue
        ok = _valid_setting(s, warnings)
        if not ok:
            continue
        if ok["id"] in locked:
            warnings.append(f"{MASTER[ok['id']]['name']}: 잠긴 지표라 바꾸지 않았어요")
            blocked.append(MASTER[ok["id"]]["name"])
            continue
        current[ok["id"]].update(operator=ok["operator"], value=ok["value"], source=ok["source"])
        if "period_months" in ok:
            current[ok["id"]]["period_months"] = ok["period_months"]
            if ok["period_months"] != 3:
                warnings.append(f"기간 수익률은 지금은 3개월 기준으로 계산해요({ok['period_months']}개월은 저장만 해 둬요)")
        changed.append(ok["id"])
    anchors = [a for a in (raw.get("anchors") or []) if a in MASTER]

    clarify = None
    if raw.get("needs_clarification") or not changed:
        c = raw.get("clarify") or {}
        options = []
        for o in c.get("options") or []:
            if o.get("value") is None:  # 지표·영역·기간 후보처럼 값이 없는 선택지는 이름만 보여 준다
                if o.get("label"):
                    options.append({"label": str(o["label"])})
                continue
            ok = _valid_setting({"id": o.get("indicator_id"), "operator": o.get("operator"), "value": o.get("value")}, warnings)
            if ok and ok["id"] not in locked:
                options.append({"label": str(o.get("label", "")), "indicator_id": ok["id"],
                                "operator": ok["operator"], "value": ok["value"],
                                "criterion": criterion_text(ok["id"], ok["operator"], ok["value"])})
        message = c.get("message") or GENERIC_CLARIFY
        if blocked and not changed:  # 사용자가 잠근 지표를 바꾸려 한 경우
            message = f"{', '.join(dict.fromkeys(blocked))}은(는) 잠겨 있어서 바꿀 수 없어요. 잠금을 풀고 다시 말씀해 주세요."
            options = []
        clarify = {"message": message, "options": options[:3]}
        # 되묻는 중에는 아무 값도 바꾸지 않는다
        return {"needs_clarification": True, "clarify": clarify, "name": "", "anchors": [], "indicators": [],
                "explain_bubble": "", "explain_card": "", "warnings": warnings}

    indicators = [current[i] for i in sorted(current)]
    return {"needs_clarification": False, "clarify": None, "name": (raw.get("name") or "내 원칙")[:30],
            "anchors": anchors or changed, "indicators": indicators,
            "explain_bubble": raw.get("explain_bubble") or "", "explain_card": raw.get("explain_card") or "",
            "warnings": warnings}


def ask(text: str, base: list[dict] | None = None, locked_ids: list[int] | None = None,
        history: list[str] | None = None) -> dict:
    locked_ids = locked_ids or []
    base_map = {x["id"]: x for x in base} if base else None
    raw = ask_model(text, base_map, locked_ids, history)
    return normalize(raw, base, locked_ids)


# --- 저장·조회 (사용자는 jangyechan 고정) ---

def save(conn: sqlite3.Connection, name: str, indicators: list[dict], reason: str = "") -> int:
    cur = conn.execute("INSERT INTO principles(user_id, name) VALUES (?, ?)", (config.FIXED_USER_ID, name))
    conn.execute("INSERT INTO principle_versions(principle_id, version, indicators_json, reason) VALUES (?,?,?,?)",
                 (cur.lastrowid, 1, json.dumps(indicators, ensure_ascii=False), reason))
    return cur.lastrowid


def new_version(conn: sqlite3.Connection, principle_id: int, indicators: list[dict], reason: str = "") -> int:
    row = conn.execute("SELECT current_version FROM principles WHERE id=? AND user_id=?",
                       (principle_id, config.FIXED_USER_ID)).fetchone()
    if not row:
        raise KeyError(principle_id)
    version = row["current_version"] + 1
    conn.execute("INSERT INTO principle_versions(principle_id, version, indicators_json, reason) VALUES (?,?,?,?)",
                 (principle_id, version, json.dumps(indicators, ensure_ascii=False), reason))
    conn.execute("UPDATE principles SET current_version=? WHERE id=?", (version, principle_id))
    return version


def get(conn: sqlite3.Connection, principle_id: int, version: int | None = None) -> dict | None:
    p = conn.execute("SELECT * FROM principles WHERE id=? AND user_id=?", (principle_id, config.FIXED_USER_ID)).fetchone()
    if not p:
        return None
    v = conn.execute("SELECT * FROM principle_versions WHERE principle_id=? AND version=?",
                     (principle_id, version or p["current_version"])).fetchone()
    return {"id": p["id"], "name": p["name"], "version": v["version"], "reason": v["reason"],
            "indicators": json.loads(v["indicators_json"]), "created_at": v["created_at"]}


def list_all(conn: sqlite3.Connection) -> list[dict]:
    ids = [r["id"] for r in conn.execute("SELECT id FROM principles WHERE user_id=? ORDER BY id", (config.FIXED_USER_ID,))]
    return [get(conn, i) for i in ids]


def delete(conn: sqlite3.Connection, principle_id: int) -> None:
    conn.execute("DELETE FROM principle_versions WHERE principle_id=?", (principle_id,))
    conn.execute("DELETE FROM principles WHERE id=? AND user_id=?", (principle_id, config.FIXED_USER_ID))

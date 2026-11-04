"""판정은 LLM이 아니라 코드가 한다: 같은 입력이면 항상 같은 결과.

principle_indicators: [{id, operator, value, ...}]  (value는 표시 단위, 예: 시가총액 1 = 1조원)
actuals: {id: {"value": float|None, "approx": bool}}  (기본 단위)
"""
import operator as op

from indicators.master import MASTER, actual_text, criterion_text

_OPS = {"<=": op.le, ">=": op.ge, "<": op.lt, ">": op.gt}


def judge_indicator(ind: dict, actual: dict | None) -> dict:
    value = actual["value"] if actual else None
    passed = False
    if value is not None:
        passed = _OPS[ind["operator"]](value, ind["value"] * MASTER[ind["id"]]["scale"])
    return {
        "indicator_id": ind["id"],
        "criterion": criterion_text(ind["id"], ind["operator"], ind["value"]),
        "actual": actual_text(ind["id"], value) + (" (근사)" if actual and actual.get("approx") and value is not None else ""),
        "pass": passed,
        "has_data": value is not None,
    }


def judge_stock(principle_indicators: list[dict], actuals: dict) -> dict:
    rows = [judge_indicator(i, actuals.get(i["id"])) for i in principle_indicators]
    return {"rows": rows, "pass_count": sum(r["pass"] for r in rows), "total": len(rows),
            "all_pass": all(r["pass"] for r in rows)}

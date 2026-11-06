"""지표 마스터(20개): id, 이름, 단위, 기본 연산자·기본값. 프론트 src/data/indicators.ts 와 id가 같다.

원칙에 저장되는 값은 표시 단위 기준이다(예: 시가총액 1 = 1조원).
실제 값(actual)은 기본 단위(원, %, 배, 년)로 계산하고, 판정할 때 scale을 곱해 맞춘다.
"""
import json
from pathlib import Path

MASTER = {m["id"]: m for m in json.loads((Path(__file__).parent / "master.json").read_text(encoding="utf-8"))}
OPERATOR_WORDS = {"<=": "이하", ">=": "이상", "<": "미만", ">": "초과"}


def _num(x: float) -> str:
    return f"{x:,.0f}" if abs(x) >= 100 or x == int(x) else f"{x:,.1f}"


def criterion_text(ind_id: int, operator: str, value: float) -> str:
    """기준을 화면에 보이는 말로: 100% 이하, 1조원 이상, 흑자, -20% 이내."""
    m = MASTER[ind_id]
    if m["word"] == "흑자":
        return "흑자" if operator == ">" and value == 0 else f"{_num(value)}{m['unit']} {OPERATOR_WORDS[operator]}"
    # "이내"는 기본 방향일 때만(52주 저점 대비 > 30 은 "30% 초과")
    word = m["word"] if m["word"] and same_direction(ind_id, operator) else OPERATOR_WORDS[operator]
    return f"{_num(value)}{m['unit']} {word}"


def actual_text(ind_id: int, actual: float | None) -> str:
    """실제 값을 화면에 보이는 말로. actual은 기본 단위(원, %, 배, 년)."""
    if actual is None:
        return "데이터 없음"
    m = MASTER[ind_id]
    if ind_id == 5:
        return "흑자" if actual > 0 else "적자"
    shown = actual / m["scale"]
    sign = "+" if ind_id in (15, 17) and shown > 0 else ""
    return f"{sign}{_num(shown)}{m['unit']}"


# 허용 값 범위(표시 단위). 모델이 범위 밖 값을 내면 코드가 거절한다.
RANGES = {1: (0, 1000), 2: (0, 100), 3: (0, 100), 4: (0, 100), 5: (0, 100000), 6: (0, 30), 7: (-100, 100),
          8: (-100, 1000), 9: (-100, 10000), 10: (0, 200), 11: (0, 50), 12: (0, 30), 13: (0, 30), 14: (0, 1000),
          15: (-100, 1000), 16: (-100, 0), 17: (0, 1000), 18: (0, 20), 19: (0, 100000), 20: (0, 100)}


# 양방향을 허용하는 지표(팀 지표 마스터 byungjun/data/H1-*의 allowed_operators와 같게).
# 예: "시총 1조 미만 소형주", "저점에서 30% 넘게 오른 종목". 나머지는 방향을 뒤집으면 막는다(빚 적은 -> 부채비율 이상).
BOTH_WAYS = {5, 14, 15, 16, 17}


def same_direction(ind_id: int, operator: str) -> bool:
    return (operator in ("<=", "<")) == (MASTER[ind_id]["operator"] in ("<=", "<"))


def allowed_operators(ind_id: int) -> tuple[str, ...]:
    """지표마다 허용하는 연산자."""
    if ind_id in BOTH_WAYS:
        return ("<=", "<", ">=", ">")
    return ("<=", "<") if MASTER[ind_id]["operator"] in ("<=", "<") else (">=", ">")
